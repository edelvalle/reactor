import json
from uuid import uuid4
from contextlib import asynccontextmanager


from pyquery import PyQuery as q

from django.contrib.auth.models import AnonymousUser
from channels.testing import WebsocketCommunicator

from .channels import ReactorConsumer


class ReactorCommunicator(WebsocketCommunicator):
    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scope['user'] = user or AnonymousUser()
        self._components = {}
        self.redirected_to = None
        self.loop_timeout = None

    def add_component(self, *args, **kwargs):
        component = Component(*args, **kwargs)
        self._components[component.id] = component
        return component.id

    def __getitem__(self, _id):
        return self._components[_id]

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

    async def loop_over_messages(self, reset_timeout=False):
        if reset_timeout or not self.loop_timeout:
            self.loop_timeout = 0.1
            while await self.receive_nothing(timeout=self.loop_timeout):
                self.loop_timeout *= 2
            print('LOOP TIMEOUT', self.loop_timeout)

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
        self.removed = False

    @property
    def id(self):
        return self.state['id']

    @property
    def doc(self):
        return q(self.last_received_html)

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

        state = self.doc.attr['state']
        if state:
            self.state = json.loads(state)

    def apply_remove(self):
        self.removed = True

    def __str__(self):
        return f'<{self.tag_name} {self.state}>'

    __repr__ = __str__
