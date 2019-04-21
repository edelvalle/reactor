import logging

from asgiref.sync import async_to_sync
from django.db.transaction import atomic
from channels.generic.websocket import JsonWebsocketConsumer

from .component import ComponentHerarchy

log = logging.getLogger('reactor')


class ReactorConsumer(JsonWebsocketConsumer):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subcriptions = set()

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

    def update_subscriptions(self, *args, **kwargs):
        log.debug(f'>> UPDATE SUBCRIPTIONS')
        all_subcriptions = self.root_component.subscriptions
        for room in all_subcriptions - self.subcriptions:
            self.subscribe(room)
        for room in self.subcriptions - all_subcriptions:
            self.unsubscribe(room)

    # Channel events

    def connect(self):
        super().connect()
        self.scope['channel_name'] = self.channel_name
        self.root_component = ComponentHerarchy(context=self.scope)
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

    def receive_join(self, tag_name, state):
        component = self.root_component.get_or_create(tag_name, **state)
        html = component.render()
        self.render({'id': component.id, 'html': html})

    def receive_user_event(self, name, state):
        component_found, html = self.root_component.dispatch_user_event(
            name, state)
        if component_found:
            self.render({'id': state['id'], 'html': html})
        else:
            self.remove({
                'type': 'remove',
                'id': state['id'],
            })

    def receive_leave(self, id, **kwargs):
        if self.root_component.pop(id, None):
            self.update_subscriptions()

    # Internal event

    def update(self, event):
        log.debug(f'>>> UPDATE {event}')
        for event in self.root_component.propagate_update(event['origin']):
            self.render(event)

    # Broadcasters

    def render(self, event):
        if event['html'] is not None:
            if event['html']:
                log.debug(f"<<< RENDER {event['id']}")
                self.send_json(dict(event, type='render'))
            else:
                self.remove(event)

    def remove(self, event):
        log.debug(f"<<< REMOVE {event['id']}")
        self.receive_leave(**event)
        self.send_json(dict(event, type='remove'))
