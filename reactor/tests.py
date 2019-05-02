import json

import websocket
from pyquery import PyQuery as q


class JsonWebSocket(websocket.WebSocket):
    def send_json(self, data):
        return self.send(json.dumps(data))

    def receive_json(self, *args, **kwargs):
        return json.loads(self.recv(*args, **kwargs))


class ClientComponent:
    def __init__(self, tag_name, **state):
        self.tag_name = tag_name
        self.state = state
        self.last_received_html = ''

    def send_join(self, ws: JsonWebSocket):
        ws.send_json({
            'command': 'join',
            'payload': {
                'tag_name': self.tag_name,
                'state': self.state,
            },
        })

    def send_user_event(self, _ws: JsonWebSocket, _name, **kwargs):
        _ws.send_json({
            'command': 'user_event',
            'payload': {
                'name': _name,
                'state': dict(kwargs, id=self.state['id'])
            }
        })

    def assert_render(self, ws: JsonWebSocket):
        response = ws.receive_json()
        assert response['type'] == 'render'
        assert response['id'] == self.state['id']
        html = []
        cursor = 0
        for diff in response['html_diff']:
            if isinstance(diff, str):
                html.append(diff)
            elif diff < 0:
                cursor -= diff
            else:
                html.append(self.last_received_html[cursor:cursor + diff])
                cursor += diff
        self.last_received_html = ''.join(html)
        return q(self.last_received_html)

    def assert_remove(self, ws: JsonWebSocket):
        response = ws.receive_json()
        assert response['type'] == 'remove'
        assert response['id'] == self.state['id']

    def __str__(self):
        return f'<{self.tag_name} {self.state}>'

    __repr__ = __str__
