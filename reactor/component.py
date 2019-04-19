from uuid import uuid4
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.template.loader import render_to_string
from django.template.context import Context
from django.utils.safestring import mark_safe
from django.utils.functional import cached_property
from django.db.transaction import on_commit


class Component:
    template_name = ''
    _all = {}

    def __init_subclass__(cls, name=None):
        name = name or cls.__name__
        name = ''.join([('-' + c if c.isupper() else c) for c in name])
        name = name.strip('-').lower()
        cls._all[name] = cls
        cls._tag_name = name
        return super().__init_subclass__()

    def __init__(self, context, id=None):
        self._context = context
        self._destroy_sent = False
        self._last_sent_html = ''
        self.subscriptions = set()
        self.id = id or str(uuid4())

    @cached_property
    def _channel_name(self):
        return self._context.get('channel_name')

    @classmethod
    def build(cls, tag_name, *args, **kwargs):
        return cls._all[tag_name](*args, **kwargs)

    def dispatch(self, name, args=None):
        getattr(self, f'receive_{name}')(**(args or {}))
        self.send_render()

    # State persistence & front-end communication
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
        return dict(id=self.id)

    def refresh(self):
        self.mount(**self.serialize())

    def send_render(self):
        if not self._destroy_sent:
            html = self.render()
            if self._last_sent_html != html and self._channel_name:
                self._last_sent_html = html
                send_to_channel(
                    self._channel_name,
                    'render',
                    id=self.id,
                    html=html,
                )

    def send_destroy(self):
        self._destroy_sent = True
        if self._channel_name:
            send_to_channel(
                self._channel_name,
                'remove',
                id=self.id,
                tag_name=self._tag_name
            )

    def render(self):
        if self._destroy_sent:
            return ''
        else:
            context = Context(self._context).update({'this': self})
            return mark_safe(
                render_to_string(self.template_name, context).strip()
            )


def send_to_channel(_channel_name, type, **kwargs):
    on_commit(
        lambda: async_to_sync(get_channel_layer().send)(
            _channel_name, dict(type=type, **kwargs)
        )
    )


def send_to_group(_whom, type, **kwargs):
    on_commit(
        lambda: async_to_sync(get_channel_layer().group_send)(
            _whom, dict(type=type, origin=_whom, **kwargs)
        )
    )
