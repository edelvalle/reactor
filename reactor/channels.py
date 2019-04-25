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

    def subscribe(self, event):
        room_name = event['room_name']
        if room_name not in self.subcriptions:
            log.debug(f':: SUBSCRIBE {self.channel_name} {room_name}')
            async_to_sync(self.channel_layer.group_add)(
                room_name,
                self.channel_name
            )
            self.subcriptions.add(room_name)

    def unsubscribe(self, event):
        room_name = event['room_name']
        if room_name in self.subcriptions:
            log.debug(f':: UNSUBSCRIBE {self.channel_name} {room_name}')
            async_to_sync(self.channel_layer.group_discard)(
                room_name,
                self.channel_name
            )
            self.subcriptions.discard(room_name)

    # Channel events

    def connect(self):
        super().connect()
        self.scope['channel_name'] = self.channel_name
        self.root_component = ComponentHerarchy(context=self.scope)
        log.debug(f':: CONNECT {self.channel_name}')

    def disconnect(self, close_code):
        for room in list(self.subcriptions):
            self.unsubscribe({'room_name': room})
        log.debug(f':: DISCONNECT {self.channel_name}')

    # Dispatching

    @atomic
    def receive_json(self, request):
        name = request['command']
        payload = request['payload']
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
        self.root_component.pop(id)

    # Internal event

    def update(self, event):
        log.debug(f'>>> UPDATE {event}')
        origin = event['origin']
        no_one_responded_to_this_update = True
        for event in self.root_component.propagate_update(origin):
            self.render(event)
            no_one_responded_to_this_update = False

        if no_one_responded_to_this_update:
            self.unsubscribe({'room_name': origin})

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
