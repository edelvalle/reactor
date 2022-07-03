import difflib
import typing as t
from functools import reduce
from uuid import uuid4

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.db import models
from django.shortcuts import resolve_url  # type: ignore
from django.template import loader
from django.template.base import Template
from django.utils.html import format_html
from django.utils.safestring import SafeText, mark_safe
from pydantic import BaseModel, validate_arguments
from pydantic.fields import Field

from . import serializer, settings, utils
from .auto_broadcast import Action

if settings.USE_HMIN:
    try:
        from hmin.base import html_minify  # type: ignore
    except ImportError as e:
        raise ImportError(
            "If you enable REACTOR['USE_HMIN'] you need to install django-hmin"
        ) from e
else:

    def html_minify(html: str) -> str:
        return html


ComponentState = Context = MessagePayload = dict[str, t.Any]
RedirectDestination = t.Callable[(...), t.Any] | models.Model | str
HTMLDiff = list[str | int]
User = AnonymousUser | AbstractBaseUser


class Repo(t.Protocol):
    pass


__all__ = ("Component", "broadcast")


def broadcast(channel: str, **kwargs: t.Any):
    utils.send_to(channel, type="notification", kwargs=kwargs)


class ReactorMeta:
    _last_sent_html: list[str]

    def __init__(
        self, channel_name: str | None = None, parent_id: str | None = None
    ):
        self.channel_name = channel_name
        self.parent_id = parent_id
        self._destroyed = False
        self._is_frozen = False
        self._redirected_to = None
        self._last_sent_html = []
        self._template = None
        self._messages_to_send: list[tuple[str, str, MessagePayload]] = []

    def destroy(self, component_id: str):
        if not self._destroyed:
            self._destroyed = True
            self.send("remove", id=component_id)

    def freeze(self):
        self._is_frozen = True

    def redirect_to(self, to: t.Any, **kwargs: t.Any):
        self._redirect(to, kwargs)

    def replace_to(self, to: RedirectDestination, **kwargs: t.Any):
        self._redirect(to, kwargs, replace=True)

    def push_to(self, to: RedirectDestination, **kwargs: t.Any):
        self._push(to, kwargs)

    def _redirect(
        self,
        to: RedirectDestination,
        kwargs: t.Any,
        replace: bool = False,
    ):
        url = resolve_url(to, **kwargs)
        self._redirected_to = url
        if self.channel_name:
            self.freeze()
            self.send("redirect_to", url=url, replace=replace)

    def _push(self, to: RedirectDestination, kwargs: Context):
        url = resolve_url(to, **kwargs)
        self._redirected_to = url
        if self.channel_name:
            self.freeze()
            self.send("push_page", url=url)

    def render_diff(
        self, component: "Component", repo: Repo
    ) -> HTMLDiff | None:
        html = self.render(component, repo)
        if html and self._last_sent_html != (html := html.split(" ")):
            if settings.USE_HTML_DIFF:
                diff: HTMLDiff = []
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
                diff = html  # type: ignore
            self._last_sent_html = html
            return diff

    def render(self, component: "Component", repo: Repo) -> None | SafeText:
        html = None
        if not self.channel_name and self._redirected_to:
            html = format_html(
                '<meta http-equiv="refresh" content="0; url={url}">',
                url=self._redirected_to,
            )
        elif not (self._is_frozen or self._redirected_to):
            key = component._cache_key
            key = key and f"{component._fqn}:{key}"

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

    def _get_template(self, template_name: list[str] | str) -> Template:
        if not self._template:
            if isinstance(template_name, (list, tuple)):
                self._template = loader.select_template(template_name)
            else:
                self._template = loader.get_template(template_name)
        return self._template

    def send(self, _topic: str, **kwargs: t.Any):
        if self.channel_name:
            self.send_to(self.channel_name, _topic, **kwargs)

    def send_to(self, _channel: str, _topic: str, **kwargs: t.Any):
        self._messages_to_send.append((_channel, _topic, kwargs))

    def _get_context(
        self,
        component: "Component",
        repo: Repo,
    ) -> Context:
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


def compress_diff(diff: HTMLDiff, diff_item: str | int) -> HTMLDiff:
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
    __name__: str

    _all: dict[str, t.Type["Component"]] = {}
    _urls = {}
    _name: str = ...  # type: ignore
    _template_name: str = ...  # type: ignore
    _fqn: str
    _tag_name: str
    _url_params: t.Mapping[str, str] = {}  # local_attr_name -> url_param_name

    # HTML tag that this component extends
    _extends = "div"

    # fields to exclude from the component state during serialization
    _exclude_fields = {"user", "reactor"}

    # Cache: the render of the componet can be cached if you define a cache key
    _cache_key: str | None = None
    # expiration time of the cache
    _cache_time = 300
    # if True will refresh the cache on each render
    _cache_touch = True

    # Subscriptions: you can define here which channels this component is
    # subscribed to
    _subscriptions: set[str] = set()

    class Config:
        arbitrary_types_allowed = True
        validate_assignment = True
        json_encoders = {  # type: ignore
            models.Model: lambda x: serializer.encode(x),  # type: ignore
            models.QuerySet: lambda qs: [x.pk for x in qs],  # type: ignore
        }

    def __init_subclass__(
        cls: t.Type["Component"], name: str | None = None, public: bool = True
    ) -> t.Type["Component"]:

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

        return super().__init_subclass__()  # type: ignore

    @classmethod
    def _new(
        cls,
        _component_name: str,
        state: ComponentState,
        user: User,
        channel_name: str | None = None,
        parent_id: str | None = None,
    ) -> "Component":
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
            user=user,
            **state,
        )
        return instance

    @classmethod
    def _rebuild(
        cls,
        _component_name: str,
        state: ComponentState,
        user: User,
        channel_name: str | None = None,
        parent_id: str | None = None,
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
    user: User
    reactor: ReactorMeta

    @classmethod
    def new(cls, **kwargs: t.Any):
        return cls(**kwargs)

    def joined(self):
        ...

    def mutation(self, channel: str, instance: models.Model, action: Action.T):
        ...

    def notification(self, channel: str, **kwargs: t.Any):
        ...

    def destroy(self):
        self.reactor.destroy(self.id)

    def render(self, repo: Repo):
        return self.reactor.render(self, repo)

    def render_diff(self, repo: Repo):
        return self.reactor.render_diff(self, repo)

    def focus_on(self, selector: str):
        return self.reactor.send("focus_on", selector=selector)


class ComponentNotFound(LookupError):
    pass
