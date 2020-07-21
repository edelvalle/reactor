import logging
import difflib
from uuid import uuid4
import json
from functools import wraps, reduce

from asgiref.sync import async_to_sync

from django.shortcuts import resolve_url
from django.template import Context
from django.utils.html import escape
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.utils.functional import cached_property

from channels.layers import get_channel_layer

from . import settings
from .json import Encoder

log = logging.getLogger('reactor')


class ComponentHerarchy(dict):

    def __init__(self, context):
        super().__init__()
        self._context = context

    def get_or_create(self, _name, id=None, **state):
        id = str(id or '')
        component = self.get(id)  # type: Component
        if component:
            component.refresh(**state)
        else:
            component = Component.build(_name, context=self._context, id=id)
            component.mount(**state)
            self[component.id] = component
        return component

    def look_up(self, id):
        component = self.get(id)
        if component:
            return component
        else:
            for component in list(self.values()):
                component = component._children.look_up(id)
                if component:
                    return component

    def pop(self, id, default=None):
        component = super().pop(id, default)
        if component:
            return component
        else:
            for component in list(self.values()):
                component = component._children.pop(id, default=default)
                if component:
                    return component

    def dispatch_user_event(self, name, state):
        component = self.look_up(state['id'])
        if component:
            return True, component.dispatch(name, state)
        return False, None

    def propagate_update(self, event):
        origin = event['origin']
        for component in list(self.values()):
            if origin in component.subscriptions:
                component.update(**event)
                html_diff = component.render_diff()
                yield {'id': component.id, 'html_diff': html_diff}
            else:
                yield from component._children.propagate_update(event)


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
        return super().__init_subclass__()

    def __str__(self):
        state = escape(json.dumps(self.serialize(), cls=Encoder))
        return mark_safe(
            f'is="{self._tag_name}" '
            f'id="{self.id}" '
            f'state="{state}"'
        )

    # Constructors

    @classmethod
    def build(cls, tag_name, *args, **kwargs):
        return cls._all[tag_name](*args, **kwargs)

    def __init__(self, context, id=None):
        self._context = context
        self._destroy_sent = False
        self._is_frozen = False
        self._redirected_to = None
        self._last_sent_html = []
        self._children = ComponentHerarchy(context=context)
        self.subscriptions = set()
        self.id = str(id or uuid4())

    # User events

    def subscribe(self, *room_names):
        for room_name in room_names:
            if room_name not in self.subscriptions:
                self.subscriptions.add(room_name)
                send_to_channel(
                    self._channel_name,
                    'subscribe',
                    room_name=room_name
                )

    def unsubscribe(self, room_name):
        self.subscriptions.discard(room_name)

    @cached_property
    def _channel_name(self):
        return self._context.get('channel_name')

    def dispatch(self, name, args=None):
        getattr(self, f'receive_{name}')(**(args or {}))
        return self.render_diff()

    # State persistence & front-end communication

    def freeze(self):
        self._is_frozen = True

    def update(self, **kwargs):
        """Entrypoint for broadcast events"""
        return self.refresh()

    def refresh(self, **state):
        self.mount(**dict(self.serialize(), **state))

    def mount(self, **state):
        """
        Override so given an initial state be able to  re-create or update the
        component state
        """
        pass

    def serialize(self):
        """
        Override to send this state to the front-end and calling `mount` for
        state recreation
        """
        return {'id': self.id}

    # Redirects & rendering

    def send_destroy(self):
        self._destroy_sent = True
        send_to_channel(self._channel_name, 'remove', id=self.id)

    def send_redirect(self, url,  *args, **kwargs):
        push_state = kwargs.pop('push_state', True)
        url = resolve_url(url, *args, **kwargs)
        if self._channel_name:
            if push_state:
                action = 'push_state'
            else:
                action = 'redirect'
            send_to_channel(self._channel_name, action, url=url)
            self.freeze()
        else:
            self._redirected_to = url

    def send(self, _name, id=None, **kwargs):
        send_to_channel(
            self._channel_name,
            'send_component',
            name=_name,
            state=dict(kwargs, id=id or self.id),
        )

    def render_diff(self):
        html = self.render()
        html = html.splitlines()
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

    def render(self):
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
            if self.template:
                html = self.template.render(Context({'this': self}))
            else:
                html = render_to_string(self.template_name, {'this': self})
            html = html.strip()
        return mark_safe(html)


class AuthComponent(Component, public=False):

    def mount(self, *args, **kwargs):
        if self.user.is_authenticated:
            # Listen to user logout and refresh
            return True
        else:
            self.send_redirect_to_login()

    def send_redirect_to_login(self):
        self.send_redirect(settings.LOGIN_URL)

    @cached_property
    def user(self):
        return self._context['user']


class StaffComponent(AuthComponent, public=False):
    def mount(self, *args, **kwargs):
        if super().mount() and self.user.is_staff:
            return True
        else:
            self.send_redirect(settings.LOGIN_URL)


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


def broadcast(*names, **kwargs):
    for name in names:
        log.debug(f'<-> {name}')
        send_to_group(name, 'update', **kwargs)


def on_commit(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        from django.db.transaction import on_commit
        on_commit(lambda: f(*args, **kwargs))
    return wrapper


def send_to_channel(_channel_name, type, **kwargs):
    if _channel_name:
        @on_commit
        def send_message():
            async_to_sync(get_channel_layer().send)(
                _channel_name, dict(type=type, **kwargs)
            )
        send_message()


def send_to_group(_whom, type, **kwargs):
    if _whom:
        @on_commit
        def send_message():
            async_to_sync(get_channel_layer().group_send)(
                _whom, dict(type=type, origin=_whom, **kwargs)
            )
        send_message()
