from uuid import uuid4

from asgiref.sync import async_to_sync
from django.template.loader import render_to_string
from django.template.context import Context
from django.utils.safestring import mark_safe
from django.utils.functional import cached_property
from django.db.transaction import on_commit
from channels.layers import get_channel_layer


class ComponentHerarchy(dict):

    def __init__(self, context):
        super().__init__()
        self._context = context

    def get_or_create(self, _name, id=None, **state):
        id = str(id or '')
        component = (
            self.get(id) or
            Component.build(_name, context=self._context, id=id)
        )
        component.mount(**state)
        self[component.id] = component
        return component

    def look_up(self, id):
        component = self.get(id)
        if component:
            return component
        else:
            for component in self.values():
                component = component._children.look_up(id)
                if component:
                    return component

    @property
    def subscriptions(self):
        return set().union(*[c.subscriptions for c in self.all])

    @property
    def all(self):
        for component in self.values():
            yield component
            yield from component._children.all

    def dispatch_user_event(self, name, state):
        component = self.look_up(state['id'])
        if component:
            return True, component.dispatch(name, state)
        return False, None

    def propagate_update(self, origin):
        for component in self.values():
            if origin in component.subscriptions:
                html = component.refresh()
                yield {'id': component.id, 'html': html}
                continue
            yield from component._children.propagate_update(origin)


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

    # Constructors

    @classmethod
    def build(cls, tag_name, *args, **kwargs):
        return cls._all[tag_name](*args, **kwargs)

    def __init__(self, context, id=None):
        self._context = context
        self._destroy_sent = False
        self._last_sent_html = ''
        self._children = ComponentHerarchy(context=context)
        self._old_subcriptions = set()
        self.subscriptions = set()
        self.id = str(id or uuid4())

    # User events

    @cached_property
    def _channel_name(self):
        return self._context.get('channel_name')

    def dispatch(self, name, args=None):
        getattr(self, f'receive_{name}')(**(args or {}))
        return self.render()

    # State persistence & front-end communication

    def refresh(self):
        self.mount(**self.serialize())
        return self.render()

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

    def send_destroy(self):
        self._destroy_sent = True
        if self._channel_name:
            send_to_channel(
                self._channel_name,
                'remove',
                id=self.id,
            )

    def render(self, in_template=False):
        if self._destroy_sent:
            html = ''
        else:
            context = Context(self._context).update({'this': self})
            html = mark_safe(
                render_to_string(self.template_name, context).strip()
            )

        if in_template or self._last_sent_html != html:
            self._last_sent_html = html
            self.send_update_subscriptions()
            return html

    def send_update_subscriptions(self):
        if self._channel_name and self._old_subcriptions != self.subscriptions:
            self._old_subcriptions = set(self.subscriptions)
            send_to_channel(self._channel_name, 'update_subscriptions')


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
