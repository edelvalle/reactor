import json
from uuid import uuid4
from contextlib import asynccontextmanager

from pyquery import PyQuery as q

from django.contrib.auth.models import AnonymousUser
from django.core.serializers.json import DjangoJSONEncoder
from channels.testing import WebsocketCommunicator

from .channels import ReactorConsumer


class ReactorCommunicator(WebsocketCommunicator):
    MAX_WAIT = 2  # seconds

    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scope['user'] = user or AnonymousUser()
        self._component_types = {}
        self._components = {}
        self.redirected_to = None
        self.loop_timeout = None

    async def connect(self, *args, **kwargs):
        connected, subprotocol = await super().connect(*args, **kwargs)
        if connected:
            response = await self.receive_json_from()
            assert response['type'] == 'components'
            self._component_types = response['component_types']
        return connected, subprotocol

    async def auto_join(self, response):
        doc = q(response.content)
        for component in doc('[id][state]'):
            tag_name = component.get('is') or component.tag
            assert tag_name in self._component_types
            state = json.loads(component.get('state'))
            component_id = self.add_component(tag_name, state)
            await self.send_join(component_id)

    def add_component(self, tag_name: str, *args, **kwargs):
        assert tag_name in self._component_types
        component = Component(tag_name, *args, **kwargs)
        self._components[component.id] = component
        return component.id

    def __getitem__(self, _id):
        return self._components[_id]

    def get_by_name(self, name):
        for component in self._components.values():
            if component.tag_name == name:
                return component

    async def send_join(self, component_id):
        component = self._components[component_id]
        await self.send_json_to({
            'command': 'join',
            'payload': {
                'tag_name': component.tag_name,
                'state': component.state,
            },
        })
        await self.loop_over_messages()
        return component.doc

    async def send(self, _id, _name, **state):
        assert _id in self._components
        await self.send_json_to({
            'command': 'user_event',
            'payload': {
                'name': _name,
                'state': dict(state, id=_id)
            }
        })
        await self.loop_over_messages(reset_timeout=True)
        return self._components[_id].doc

    async def send_json_to(self, data):
        await self.send_to(text_data=json.dumps(data, cls=DjangoJSONEncoder))

    async def loop_over_messages(self, reset_timeout=False):
        if reset_timeout or not self.loop_timeout:
            self.loop_timeout = 0.1
            while await self.receive_nothing(timeout=self.loop_timeout):
                self.loop_timeout *= 2
                if self.loop_timeout > self.MAX_WAIT:
                    break

        while not await self.receive_nothing(timeout=self.loop_timeout):
            response = await self.receive_json_from()
            if response['type'] in ('redirect', 'push_state'):
                self.redirected_to = response['url']
            else:
                component = self._components[response['id']]
                if response['type'] == 'render':
                    component.apply_diff(response['html_diff'])
                elif response['type'] == 'remove':
                    component.apply_remove()


@asynccontextmanager
async def reactor(consumer=ReactorConsumer, path='/reactor', user=None):
    comm = ReactorCommunicator(application=consumer, path=path, user=user)
    connected, subprotocol = await comm.connect()
    assert connected
    try:
        yield comm
    finally:
        await comm.disconnect()


class Component:
    def __init__(self, tag_name: str, state: dict = None):
        state = state or {}
        state.setdefault('id', str(uuid4()))
        self.tag_name = tag_name
        self.state = state
        self.last_received_html = ''
        self.doc = None
        self.removed = False

    @property
    def id(self):
        return self.state['id']

    def apply_diff(self, html_diff):
        html = []
        cursor = 0
        for diff in html_diff:
            if isinstance(diff, str):
                html.append(diff)
            elif diff < 0:
                cursor -= diff
            else:
                html.append(self.last_received_html[cursor:cursor + diff])
                cursor += diff
        self.last_received_html = ''.join(html)
        self.doc = q(self.last_received_html)

        state = self.doc.attr['state']
        if state:
            self.state = json.loads(state)

    def apply_remove(self):
        self.removed = True

    def __str__(self):
        return f'<{self.tag_name} {self.state}>'

    __repr__ = __str__
