import difflib
from uuid import uuid4
from functools import reduce

from django.http import HttpRequest
from django.contrib.auth.models import AnonymousUser
from django.shortcuts import resolve_url
from django.template.loader import get_template, select_template
from django.utils.safestring import mark_safe
from django.utils.functional import cached_property

try:
    from hmin.base import html_minify
except ImportError:
    def html_minify(html):
        return html

from . import settings
from .utils import send_to_channel, get_model


class RootComponent(dict):

    def __init__(self, request):
        super().__init__()
        self._request = request

    @cached_property
    def _channel_name(self):
        return self._request.get('channel_name')

    def get_or_create(self, _name, _parent_id=None, id=None, **state):
        id = str(id or '')
        kwargs = dict(
            request=self._request,
            id=id,
            _root_component=self,
            _parent_id=_parent_id,
            **state
        )
        component: Component = self.get(id)
        if component:
            component.__init__(**kwargs)
        else:
            component = self[id] = Component._build(_name, **kwargs)
        return component

    def pop(self, id, default=None):
        return super().pop(id, default)

    def dispatch_user_event(self, id, name, args):
        component: Component = self.get(id)
        if component:
            return component._dispatch(name, args)
        else:
            send_to_channel(self._channel_name, 'remove', id=id)

    def propagate_update(self, event):
        origin = event['origin']
        for component in list(self.values()):
            if origin in component._subscriptions:
                component = component._clone()
                self[component.id] = component
                html_diff = component._render_diff()
                yield {'id': component.id, 'html_diff': html_diff}


class Component:
    template_name = ''
    template = None
    extends = 'div'
    _all = {}

    def __init_subclass__(cls, name=None, public=True):
        if public:
            name = name or cls.__name__
            name = ''.join([('-' + c if c.isupper() else c) for c in name])
            name = name.strip('-').lower()
            cls._all[name] = cls
            cls._tag_name = name

        cls._models = {}
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if (not attr_name.startswith('_')
                    and attr_name.islower()
                    and callable(attr)
                    and not getattr(attr, 'private', False)):
                cls._models[attr_name] = get_model(attr, ignore=['self'])

        cls._constructor_model = get_model(cls)
        cls._constructor_params = set(
            cls._constructor_model.schema()['properties']
        )
        return super().__init_subclass__()

    @classmethod
    def _build(
        cls,
        _tag_name,
        request,
        id: str = None,
        _parent_id=None,
        _root_component=None,
        **kwargs
    ):
        klass = cls._all[_tag_name]
        kwargs = dict(klass._constructor_model.parse_obj(kwargs), id=id)
        return klass(
            request=request,
            _parent_id=_parent_id,
            _root_component=_root_component,
            **kwargs
        )

    def __init__(
        self,
        request,
        id: str = None,
        _parent_id: str = None,
        _root_component: RootComponent = None,
        _last_sent_html: list = None,
        **kwargs
    ):
        self.request = request
        self.id = id or uuid4().hex
        self._subscriptions = set()
        self._parent_id = _parent_id
        self._destroy_sent = False
        self._is_frozen = False
        self._redirected_to = None
        self._last_sent_html = _last_sent_html or []
        if _root_component is None:
            _root_component = RootComponent(request)
        self._root_component = _root_component

    @cached_property
    def user(self):
        return (
            getattr(self.request, 'user', None) or
            self.request.get('user') or
            AnonymousUser()
        )

    def _clone(self):
        return type(self)(
            request=self.request,
            _parent_id=self._parent_id,
            _root_component=self._root_component,
            _last_sent_html=self._last_sent_html,
            **self.state
        )

    @property
    def state_json(self):
        return self._constructor_model(**self.state).json()

    @property
    def state(self):
        state = {
            name: value
            for name, value in vars(self).items()
            if name in self._constructor_params
        }
        return state | {'id': self.id}

    def _subscribe(self, *room_names):
        for room_name in room_names:
            if room_name not in self._subscriptions:
                self._subscriptions.add(room_name)
                send_to_channel(
                    self._channel_name,
                    'subscribe',
                    room_name=room_name
                )

    def _unsubscribe(self, room_name):
        self._subscriptions.discard(room_name)

    @cached_property
    def _channel_name(self):
        if isinstance(self.request, dict):
            return self.request.get('channel_name')

    def _dispatch(self, name, args=None):
        model = self._models[name]
        getattr(self, name)(**dict(model.parse_obj(args or {})))
        return self._render_diff()

    # State persistence & front-end communication

    def freeze(self):
        self._is_frozen = True

    def destroy(self):
        self._destroy_sent = True
        send_to_channel(self._channel_name, 'remove', id=self.id)

    def _send_redirect(self, url,  *args, **kwargs):
        url = resolve_url(url, *args, **kwargs)
        if self._channel_name:
            send_to_channel(self._channel_name, 'push_state', url=url)
            self.freeze()
        else:
            self._redirected_to = url

    def _send_replace_state(self, url, _title=None, *args, **kwargs):
        url = resolve_url(url, *args, **kwargs)
        if self._channel_name:
            send_to_channel(
                self._channel_name, 'replace_state',
                title=_title, url=url
            )

    def _send_parent(self, _name, **kwargs):
        if self._parent_id:
            self._send(_name, id=self._parent_id, **kwargs)

    def _send(self, _name, id=None, **kwargs):
        send_to_channel(
            self._channel_name,
            'send_component',
            name=_name,
            state=dict(kwargs, id=id or self.id),
        )

    def _render_diff(self):
        html = self._render().split()
        if html and self._last_sent_html != html:
            if settings.USE_HTML_DIFF:
                diff = []
                for x in difflib.ndiff(self._last_sent_html, html):
                    indicator = x[0]
                    if indicator == ' ':
                        diff.append(1)
                    elif indicator == '+':
                        diff.append(x[2:])
                    elif indicator == '-':
                        diff.append(-1)

                if diff:
                    diff = reduce(compress_diff, diff[1:], diff[:1])
            else:
                diff = html
            self._last_sent_html = html
            return diff

    def _render(self):
        if self._is_frozen:
            html = self._last_sent_html
        elif self._destroy_sent:
            html = ''
        elif self._redirected_to:
            html = (
                f'<meta'
                f' http-equiv="refresh"'
                f' content="0; url={self._redirected_to}"'
                f'>'
            )
        else:
            if isinstance(self.request, HttpRequest):
                request = self.request
            else:
                request = None
            template = self._get_template()
            html = template.render(self._get_context(), request=request).strip()

        if settings.USE_HMIN:
            html = html_minify(html)

        return mark_safe(html)

    def _get_template(self):
        if not self.template:
            if isinstance(self.template_name, (list, tuple)):
                self.template = select_template(self.template_name)
            else:
                self.template = get_template(self.template_name)
        return self.template

    def _get_context(self):
        return dict(
            {
                attr: getattr(self, attr)
                for attr in dir(self)
                if not attr.startswith('_')
            },
            this=self,
        )


class AuthComponent(Component, public=False):

    def __init__(self, *args, **kwargs):
        super().__(*args, **kwargs)
        if not self.user.is_authenticated:
            self.destroy()


class StaffComponent(AuthComponent, public=False):
    def mount(self, *args, **kwargs):
        if super().mount() and self.user.is_staff:
            return True
        else:
            self.destroy()


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
