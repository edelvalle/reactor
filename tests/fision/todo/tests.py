import websocket
import json
from django.test import TestCase, Client

from channels.testing import ChannelsLiveServerTestCase

from .models import Item


class TestNormalRendering(TestCase):

    def setUp(self):
        Item.objects.create(text='First task')
        Item.objects.create(text='Second task')
        self.c = Client()

    def test_everything_two_tasks_are_rendered(self):
        response = self.c.get('/')
        assert response.status_code == 200
        self.assertContains(response, 'First task')
        self.assertContains(response, 'Second task')


class LiveTesting(ChannelsLiveServerTestCase):
    def test_how_it_works(self):
        assert Item.objects.count() == 0
        host = self.live_server_url[len('http://'):]
        ws = websocket.WebSocket()
        ws.connect(f'ws://{host}/reactor')
        ws.send(json.dumps({
            'command': 'join',
            'payload': {
                'tag_name': 'x-todo-list',
                'state': {'id': 'someid', 'showing': 'all'},
                'echo_render': True,
            }
        }))
        response = json.loads(ws.recv())
        assert response['type'] == 'render'
        assert response['id'] == 'someid'
        assert 'html' in response
        assert 'left' not in response['html']

        ws.send(json.dumps({
            'command': 'user_event',
            'payload': {
                'tag_name': 'x-todo-list',
                'name': 'add',
                'state': {'id': 'someid', 'new_item': 'First task'},
            }
        }))
        response = json.loads(ws.recv())
        task = Item.objects.first()  # type: Item
        assert task
        assert not task.completed
        assert response['type'] == 'render'
        assert response['id'] == 'someid'
        assert 'First task' in response['html']
        assert 'checked' not in response['html']
        task_state = {
            'id': str(task.id),
            'editing': False,
            'showing': 'all',
        }
        assert (
            json.dumps(task_state).replace('"', '&quot;') in response['html']
        )

        ws.send(json.dumps({
            'command': 'join',
            'payload': {
                'tag_name': 'x-todo-item',
                'state': task_state,
            }
        }))

        # Mark task as completed
        ws.send(json.dumps({
            'command': 'user_event',
            'payload': {
                'tag_name': 'x-todo-item',
                'name': 'completed',
                'state': dict(task_state, completed=True),
            }
        }))

        response = json.loads(ws.recv())
        task.refresh_from_db()
        assert task.completed
        assert response['type'] == 'render'
        assert response['id'] == str(task.id)
        assert 'checked' in response['html']
