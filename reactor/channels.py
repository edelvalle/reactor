from functools import reduce
from collections import defaultdict
import logging

from asgiref.sync import async_to_sync
from django.db.transaction import atomic
from channels.generic.websocket import JsonWebsocketConsumer

from .component import Component

log = logging.getLogger('reactor')


class ReactorConsumer(JsonWebsocketConsumer):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.components = defaultdict(dict)
        self.subcriptions = set()

    @property
    def all_components(self):
        for components_of_a_type in self.components.values():
            for component in components_of_a_type.values():
                yield component

    @property
    def all_components_subscriptions(self):
        return reduce(
            lambda x, y: x.union(y),
            [c.subscriptions for c in self.all_components],
            set()
        )

    # Group operations

    def subscribe(self, room_name):
        log.debug(f':: SUBSCRIBE {self.channel_name} {room_name}')
        async_to_sync(self.channel_layer.group_add)(
            room_name,
            self.channel_name
        )
        self.subcriptions.add(room_name)

    def unsubscribe(self, room_name):
        log.debug(f':: UNSUBSCRIBE {self.channel_name} {room_name}')
        async_to_sync(self.channel_layer.group_discard)(
            room_name,
            self.channel_name
        )
        self.subcriptions.discard(room_name)

    def update_subscriptions(self):
        all_subcriptions = self.all_components_subscriptions
        for room in all_subcriptions - self.subcriptions:
            self.subscribe(room)
        for room in self.subcriptions - all_subcriptions:
            self.unsubscribe(room)

    # Channel events

    def connect(self):
        super().connect()
        self.scope['channel_name'] = self.channel_name
        log.debug(f':: CONNECT {self.channel_name}')

    def disconnect(self, close_code):
        while self.subcriptions:
            self.unsubscribe(self.subcriptions.pop())
        log.debug(f':: DISCONNECT {self.channel_name}')

    # Dispatching

    @atomic
    def receive_json(self, command):
        name = command['command']
        payload = command['payload']
        log.debug(f'>>> {name.upper()} {payload}')
        getattr(self, f'receive_{name}')(**payload)

    def receive_join(self, tag_name, state, echo_render=False):
        component = (
            self.components[tag_name].get(state['id']) or
            Component.build(tag_name, context=self.scope, id=state['id'])
        )
        component.mount(**state)
        self.components[tag_name][component.id] = component
        self.update_subscriptions()
        if echo_render:
            component.send_render()

    def receive_user_event(self, tag_name, name, state):
        component = self.components[tag_name].get(state['id'])
        if component:
            component.dispatch(name, state)
        else:
            self.remove({
                'type': 'remove',
                'id': state['id'],
                'tag_name': tag_name
            })

    def receive_leave(self, id, tag_name, **kwargs):
        if self.components[tag_name].pop(id, None):
            self.update_subscriptions()

    # Internal event

    def update(self, event):
        log.debug(f'>>> UPDATE {event}')
        origin = event['origin']
        for component in self.all_components:
            if origin in component.subscriptions:
                component.refresh()
                component.send_render()
        self.update_subscriptions()

    # Broadcasters

    def render(self, event):
        log.debug(f"<<< RENDER {event['id']}")
        self.send_json(event)

    def remove(self, event):
        log.debug(f"<<< REMOVE {event['id']}")
        self.receive_leave(**event)
        self.send_json(event)
