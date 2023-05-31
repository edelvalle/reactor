import difflib
import typing as t
from asyncio import iscoroutine, iscoroutinefunction
from functools import reduce
from uuid import uuid4

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async as db
from channels.layers import BaseChannelLayer
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.db import models
from django.http import HttpRequest
from django.shortcuts import resolve_url  # type: ignore
from django.template import loader
from django.utils.html import format_html
from django.utils.safestring import SafeString, SafeText, mark_safe
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


class Template(t.Protocol):
    def render(
        self,
        context: Context | dict[str, t.Any] | None = ...,
        request: HttpRequest | None = ...,
    ) -> SafeString:
        ...


class Repo(t.Protocol):
    pass


__all__ = ("Component", "broadcast")


def broadcast(channel: str, **kwargs: t.Any):
    utils.send_to(channel, type="notification", kwargs=kwargs)


class ReactorMeta:
    _last_sent_html: list[str]

    def __init__(
        self,
        channel_name: str | None = None,
        channel_layer: BaseChannelLayer | None = None,
        parent_id: str | None = None,
    ):
        self.channel_name = channel_name
        self.channel_layer = channel_layer
        self.parent_id = parent_id
        self._destroyed = False
        self._is_frozen = False
        self._redirected_to = None
        self._last_sent_html = []

    async def destroy(self, component_id: str):
        if not self._destroyed:
            self._destroyed = True
            await self.send("remove", id=component_id)

    def freeze(self):
        self._is_frozen = True

    async def redirect_to(self, to: t.Any, **kwargs: t.Any):
        await self._redirect(to, kwargs)

    async def replace_to(self, to: RedirectDestination, **kwargs: t.Any):
        await self._redirect(to, kwargs, replace=True)

    async def push_to(self, to: RedirectDestination, **kwargs: t.Any):
        await self._push(to, kwargs)

    async def send_render(self, component_id: str):
        await self.send("render", id=component_id)

    async def _redirect(
        self,
        to: RedirectDestination,
        kwargs: t.Any,
        replace: bool = False,
    ):
        url = resolve_url(to, **kwargs)
        self._redirected_to = url
        if self.channel_name:
            self.freeze()
            await self.send("redirect_to", url=url, replace=replace)

    async def _push(self, to: RedirectDestination, kwargs: Context):
        url = resolve_url(to, **kwargs)
        self._redirected_to = url
        if self.channel_name:
            self.freeze()
            await self.send("push_page", url=url)

    async def render_diff(
        self, component: "Component", repo: Repo
    ) -> HTMLDiff | None:
        html = await db(self.render)(component, repo)
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
                template = component._get_template()
                context = self._get_context(component, repo)
                html = template.render(context).strip()
                html = html_minify(html)

            if key and component._cache_touch:
                settings.cache.set(key, html, component._cache_time)

        if html:
            return mark_safe(html)

    async def send(self, _command: str, **kwargs: t.Any):
        if self.channel_name:
            await self.send_to(self.channel_name, _command, **kwargs)

    async def send_to(self, _channel: str, _command: str, **kwargs: t.Any):
        if self.channel_layer:
            await self.channel_layer.send(
                _channel,
                {
                    "type": "message_from_component",
                    "command": _command,
                    "kwargs": kwargs,
                },
            )

    def _get_context(
        self,
        component: "Component",
        repo: Repo,
    ) -> Context:
        context = {}

        for attr_name in dir(component):
            if not attr_name.startswith("_") or not attr_name.startswith(
                settings.RECEIVER_PREFIX
            ):
                attr = getattr(component, attr_name)
                if iscoroutine(attr) or iscoroutinefunction(attr):
                    attr = async_to_sync(attr)
                context[attr_name] = attr

        return dict(
            context,
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
    _template_engine: Template
    _fqn: str
    _tag_name: str
    _url_params: t.Mapping[str, str] = {}  # local_attr_name -> url_param_name

    # HTML tag that this component extends
    _extends = "div"

    # fields to exclude from the component state during serialization
    _exclude_fields = {"user", "reactor"}

    # Cache: the render of the component can be cached if you define a cache key
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

            # Compote a valid HTML tag from the component name
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
        channel_layer: BaseChannelLayer | None = None,
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
                channel_layer=channel_layer,
                parent_id=parent_id,
            ),
            user=user,
            **state,
        )
        return instance

    @classmethod
    async def _rebuild(
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
        await instance.joined()
        return instance

    @classmethod
    def _get_template(cls) -> Template:
        if settings.DEBUG:
            return cls._load_template()
        else:
            if (template := getattr(cls, "_template_engine", None)) is None:
                template = cls._load_template()
                setattr(cls, "_template_engine", template)
            return template

    @classmethod
    def _load_template(cls) -> Template:
        if isinstance(cls._template_name, (list, tuple)):
            return loader.select_template(cls._template_name)
        else:
            return loader.get_template(cls._template_name)

    # State
    id: str = Field(default_factory=lambda: f"rx-{uuid4()}")
    user: User
    reactor: ReactorMeta

    @classmethod
    def new(cls, **kwargs: t.Any):
        return cls(**kwargs)

    async def joined(self):
        ...

    async def mutation(self, channel: str, instance: t.Any, action: Action.T):
        ...

    async def notification(self, channel: str, **kwargs: t.Any):
        ...

    async def destroy(self):
        await self.reactor.destroy(self.id)

    async def send_render(self):
        await self.reactor.send_render(self.id)

    def render(self, repo: Repo):
        return self.reactor.render(self, repo)

    def render_diff(self, repo: Repo):
        return self.reactor.render_diff(self, repo)

    async def focus_on(self, selector: str):
        await self.reactor.send("focus_on", selector=selector)


class ComponentNotFound(LookupError):
    pass
