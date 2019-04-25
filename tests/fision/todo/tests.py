import json
import websocket
from pyquery import PyQuery as q

from django.test import TestCase, Client
from django.urls import path
from channels.routing import URLRouter

from reactor.channels import ReactorConsumer
from channels.testing import ChannelsLiveServerTestCase

from .models import Item

application = URLRouter([
    path("reactor", ReactorConsumer),
])


class JsonWebsocket(websocket.WebSocket):
    def send_json(self, data):
        return self.send(json.dumps(data))

    def receive_json(self, *args, **kwargs):
        return json.loads(self.recv(*args, **kwargs))


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

    def test_render_and_join(self):
        assert Item.objects.count() == 0

        html_response = self.client.get('/')
        assert html_response.status_code == 200

        ws = JsonWebsocket()
        ws.connect(f'{self.live_server_ws_url}/reactor')

        state = {'id': 'someid', 'showing': 'all'}
        ws.send_json({
                'command': 'join',
                'payload': {
                    'tag_name': 'x-todo-list',
                    'state': state,
                },
            }
        )

        # Check render is received for same id and same state
        doc = self.assert_render(ws, 'someid')
        todo_list = doc('#someid')
        assert todo_list.attr['id'] == 'someid'
        assert json.loads(todo_list.attr['state']) == state

        # Add new item
        self.send_user_event(
            ws, 'add',
            {'id': 'someid', 'new_item': 'First task'}
        )

        # There was an item crated and rendered
        doc = self.assert_render(ws, 'someid')
        assert Item.objects.count() == 1
        assert len(doc('x-todo-item')) == 1
        todo_item_id = doc('x-todo-item')[0].get('id')
        todo_item_label = doc('x-todo-item label')[0]
        assert todo_item_label.text == 'First task'

        item = Item.objects.first()
        assert str(item.id) == todo_item_id
        assert item.text == 'First task'

        # Click title to edit it
        assert len(doc('x-todo-item li.editing')) == 0, 'Not in read mode'
        self.send_user_event(ws, 'toggle_editing', {'id': todo_item_id})
        doc = self.assert_render(ws, todo_item_id)
        assert len(doc('x-todo-item li.editing')) == 1, 'Not in edition mode'

        # Edit item with a new text
        self.send_user_event(
            ws, 'save',
            {'id': todo_item_id, 'text': 'Edited task'}
        )
        doc = self.assert_render(ws, todo_item_id)
        assert len(doc('x-todo-item li.editing')) == 0, 'Not in read mode'
        todo_item_label = doc('x-todo-item label')[0]
        assert todo_item_label.text == 'Edited task'
        item.refresh_from_db()
        assert item.text == 'Edited task'

        # Mark item as completed
        assert len(doc('x-todo-item li.completed')) == 0
        self.send_user_event(
            ws, 'completed',
            {'id': todo_item_id, 'completed': True}
        )
        doc = self.assert_render(ws, todo_item_id)
        assert len(doc('x-todo-item li.completed')) == 1
        # Counter was rendered as 0
        doc = self.assert_render(ws, 'someid-counter')
        assert doc('strong')[0].text == '0'

        # Switch to "only active tasks" filtering
        self.send_user_event(ws, 'show', {'id': 'someid', 'showing': 'active'})
        doc = self.assert_render(ws, 'someid')
        assert len(doc('x-todo-item li.hidden')) == 1

        # Switch to "only done tasks" filtering
        self.send_user_event(
            ws, 'show',
            {'id': 'someid', 'showing': 'completed'}
        )
        doc = self.assert_render(ws, 'someid')
        assert len(doc('x-todo-item')) == 1
        assert len(doc('x-todo-item li.hidden')) == 0

        # Switch to "all tasks" filtering
        self.send_user_event(ws, 'show', {'id': 'someid', 'showing': 'all'})
        doc = self.assert_render(ws, 'someid')
        assert len(doc('x-todo-item')) == 1
        assert len(doc('x-todo-item li.hidden')) == 0

        # Add another task
        self.send_user_event(
            ws, 'add',
            {'id': 'someid', 'new_item': 'Another task'}
        )
        doc = self.assert_render(ws, 'someid')
        assert len(doc('x-todo-item')) == 2
        assert len(doc('x-todo-item li.completed')) == 1

        # Remove completed tasks removes just one task
        self.send_user_event(ws, 'clear_completed', {'id': 'someid'})
        doc = self.assert_render(ws, 'someid')
        self.assert_remove(ws, todo_item_id)
        self.assert_remove(ws, todo_item_id)
        assert len(doc('x-todo-item')) == 1
        assert len(doc('x-todo-item li.completed')) == 0

        ws.close()

    def assert_render(self, ws, component_id):
        response = ws.receive_json()
        assert response['type'] == 'render'
        assert response['id'] == component_id
        return q(response['html'])

    def assert_remove(self, ws, component_id):
        response = ws.receive_json()
        assert response['type'] == 'remove'
        assert response['id'] == component_id

    def send_user_event(self, ws, name, state):
        ws.send_json({
            'command': 'user_event',
            'payload': {
                'name': name,
                'state': state,
            }
        })
