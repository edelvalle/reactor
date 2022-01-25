import difflib
import typing as t
from functools import reduce
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import models
from django.shortcuts import resolve_url
from django.template import loader
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from pydantic import BaseModel, validate_arguments
from pydantic.fields import Field

from . import serializer, settings, utils

if settings.USE_HMIN:
    try:
        from hmin.base import html_minify
    except ImportError as e:
        raise ImportError(
            "If you enable REACTOR['USE_HMIN'] you need to install django-hmin"
        ) from e
else:

    def html_minify(html):
        return html


__all__ = ("Component", "broadcast")


def broadcast(channel, **kwargs):
    utils.send_to(channel, type="notification", kwargs=kwargs)


class ReactorMeta:
    def __init__(self, channel_name=None, parent_id=None):
        self.channel_name = channel_name
        self.parent_id = parent_id
        self._destroyed = False
        self._is_frozen = False
        self._redirected_to = None
        self._last_sent_html = []
        self._template = None
        self._messages_to_send: list[tuple(str, str, dict)] = []

    def destroy(self, component_id: str):
        if not self._destroyed:
            self._destroyed = True
            self.send("remove", id=component_id)

    def freeze(self):
        self._is_frozen = True

    def redirect_to(self, to, **kwargs):
        self._redirect(to, kwargs)

    def replace_to(self, to, **kwargs):
        self._redirect(to, kwargs, replace=True)

    def push_to(self, to, **kwargs):
        self._push(to, kwargs)

    def _redirect(self, to, kwargs, replace: bool = False):
        url = resolve_url(to, **kwargs)
        self._redirected_to = url
        if self.channel_name:
            self.freeze()
            self.send("redirect_to", url=url, replace=replace)

    def _push(self, to, kwargs):
        url = resolve_url(to, **kwargs)
        self._redirected_to = url
        if self.channel_name:
            self.freeze()
            self.send("push_page", url=url)

    def render_diff(self, component, repository):
        html = self.render(component, repository)
        if html and self._last_sent_html != (html := html.split(" ")):
            if settings.USE_HTML_DIFF:
                diff = []
                for x in difflib.ndiff(self._last_sent_html, html):
                    indicator = x[0]
                    if indicator == " ":
                        diff.append(1)
                    elif indicator == "+":
                        diff.append(x[2:])
                    elif indicator == "-":
                        diff.append(-1)

                if diff:
                    diff = reduce(compress_diff, diff[1:], diff[:1])
            else:
                diff = html
            self._last_sent_html = html
            return diff

    def render(self, component, repo):
        html = None
        if not self.channel_name and self._redirected_to:
            html = format_html(
                '<meta http-equiv="refresh" content="0; url={url}">',
                url=self._redirected_to,
            )
        elif not (self._is_frozen or self._redirected_to):
            key = component._cache_key
            key = key and f"{component._fdn}:{key}"

            if key is not None:
                html = settings.cache.get(key)

            if html is None:
                template = self._get_template(component._template_name)
                context = self._get_context(component, repo)
                html = template.render(context).strip()
                html = html_minify(html)

            if key and component._cache_touch:
                settings.cache.set(key, html, component._cache_time)

        if html:
            return mark_safe(html)

    def _get_template(self, template_name):
        if not self._template:
            if isinstance(template_name, (list, tuple)):
                self._template = loader.select_template(template_name)
            else:
                self._template = loader.get_template(template_name)
        return self._template

    def send(self, _topic, **kwargs):
        if self.channel_name:
            self.send_to(self.channel_name, _topic, **kwargs)

    def send_to(self, _channel, _topic, **kwargs):
        self._messages_to_send.append((_channel, _topic, kwargs))

    def _get_context(self, component, repo):
        return dict(
            {
                attr: getattr(component, attr)
                for attr in dir(component)
                if not attr.startswith("_")
                or not attr.startswith(settings.RECEIVER_PREFIX)
            },
            this=component,
            reactor_repository=repo,
        )


def compress_diff(diff, diff_item):
    if isinstance(diff_item, str) or isinstance(diff[-1], str):
        diff.append(diff_item)
    else:
        same_sign = not (diff[-1] > 0) ^ (diff_item > 0)
        if same_sign:
            diff[-1] += diff_item
        else:
            diff.append(diff_item)
    return diff


class Component(BaseModel):
    _all = {}
    _urls = {}
    _name = ...
    _template_name = ...

    # HTML tag that this component extends
    _extends = "div"

    # fields to exclude from the component state during serialization
    _exclude_fields = {"user", "reactor"}

    # Cache: the render of the componet can be cached if you define a cache key
    _cache_key: str = None
    # expiration time of the cache
    _cache_time = 300
    # if True will refresh the cache on each render
    _cache_touch = True

    # Subscriptions: you can define here which channels this component is
    # subscribed to
    _subscriptions = set()

    class Config:
        arbitrary_types_allowed = True
        keep_untouched = (cached_property, ReactorMeta)
        json_encoders = {
            models.Model: lambda x: serializer.encode(x),
            models.QuerySet: lambda qs: [x.pk for x in qs],
        }

    def __init_subclass__(cls, name=None, public=True):
        if public:
            name = name or cls.__name__
            cls._all[name] = cls
            # Component name
            cls._name = name
            # Fully qualified name
            cls._fqn = f"{cls.__module__}.{name}"

            # Compote a valid HTML tag from the componet name
            name = "".join([("-" + c if c.isupper() else c) for c in name])
            name = name.strip("-").lower()
            cls._tag_name = "x-" + name

        for attr_name in vars(cls):
            attr = getattr(cls, attr_name)
            if (
                not attr_name.startswith("_")
                and attr_name.islower()
                and attr_name.startswith(settings.RECEIVER_PREFIX)
                and callable(attr)
            ):
                setattr(
                    cls,
                    attr_name,
                    validate_arguments(
                        config={"arbitrary_types_allowed": True}
                    )(attr),
                )

        return super().__init_subclass__()

    @classmethod
    def _new(
        cls,
        _component_name,
        state,
        user=None,
        channel_name=None,
        parent_id=None,
    ):
        if _component_name not in cls._all:
            raise ComponentNotFound(
                f"Could not find requested component '{_component_name}'. "
                f"Did you load the component?"
            )

        # TODO: rename state to initial_state
        instance = cls._all[_component_name].new(
            reactor=ReactorMeta(
                channel_name=channel_name,
                parent_id=parent_id,
            ),
            user=user or AnonymousUser(),
            **state,
        )
        return instance

    @classmethod
    def _rebuild(
        cls,
        _component_name,
        state,
        user=None,
        channel_name=None,
        parent_id=None,
    ):
        if _component_name not in cls._all:
            raise ComponentNotFound(
                f"Could not find requested component '{_component_name}'. "
                f"Did you load the component?"
            )

        # TODO: rename state to initial_state
        instance = cls._all[_component_name](
            user=user or AnonymousUser(),
            reactor=ReactorMeta(
                channel_name=channel_name,
                parent_id=parent_id,
            ),
            **state,
        )
        instance.joined()
        return instance

    # State
    id: str = Field(default_factory=lambda: f"rx-{uuid4()}")
    user: t.Union[AnonymousUser, get_user_model()]
    reactor: ReactorMeta

    @classmethod
    def new(cls, **kwargs):
        return cls(**kwargs)

    def joined(self):
        ...

    def mutation(self, channel, instance, action):
        ...

    def notification(self, channel, **kwargs):
        ...

    def destroy(self):
        self.reactor.destroy(self.id)

    def render(self, repo):
        return self.reactor.render(self, repo)

    def render_diff(self, repo):
        return self.reactor.render_diff(self, repo)

    def focus_on(self, selector: str):
        return self.reactor.send("focus_on", selector=selector)


class ComponentNotFound(LookupError):
    pass
