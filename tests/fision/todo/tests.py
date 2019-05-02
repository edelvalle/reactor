import json

from django.test import TestCase, Client
from django.urls import path

from channels.routing import URLRouter
from channels.testing import ChannelsLiveServerTestCase

from reactor.channels import ReactorConsumer
from reactor.tests import ClientComponent, JsonWebSocket

from .models import Item

application = URLRouter([
    path("reactor", ReactorConsumer),
])


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

        ws = JsonWebSocket()
        ws.connect(f'{self.live_server_ws_url}/reactor')

        x_list = ClientComponent('x-todo-list', id='someid', showing='all')
        x_list.send_join(ws)

        # Check render is received for same id and same state
        doc = x_list.assert_render(ws)
        todo_list = doc('#someid')
        assert json.loads(todo_list.attr['state']) == x_list.state

        # Add new item
        x_list.send_user_event(ws, 'add', new_item='First task')

        # There was an item crated and rendered
        doc = x_list.assert_render(ws)
        assert Item.objects.count() == 1
        assert len(doc('x-todo-item')) == 1
        todo_item_id = doc('x-todo-item')[0].get('id')
        todo_item_label = doc('x-todo-item label')[0]
        assert todo_item_label.text == 'First task'

        item = Item.objects.first()
        assert str(item.id) == todo_item_id
        assert item.text == 'First task'

        # Click title to edit it
        assert len(doc('x-todo-item li.editing')) == 0
        x_first_item = ClientComponent('x-todo-item', id=todo_item_id)
        x_first_item.send_user_event(ws, 'toggle_editing')
        doc = x_first_item.assert_render(ws)
        assert len(doc('x-todo-item li.editing')) == 1

        # Edit item with a new text
        x_first_item.send_user_event(ws, 'save', text='Edited task')
        doc = x_first_item.assert_render(ws)
        assert len(doc('x-todo-item li.editing')) == 0, 'Not in read mode'
        todo_item_label = doc('x-todo-item label')[0]
        assert todo_item_label.text == 'Edited task'
        item.refresh_from_db()
        assert item.text == 'Edited task'

        # As an item changed counter changes and renders because has no cache
        x_todo_counter = ClientComponent('x-todo-counter', id='someid-counter')
        doc = x_todo_counter.assert_render(ws)
        assert doc('strong')[0].text == '1'

        # Mark item as completed
        assert len(doc('x-todo-item li.completed')) == 0
        x_first_item.send_user_event(ws, 'completed', completed=True)
        doc = x_first_item.assert_render(ws)
        assert len(doc('x-todo-item li.completed')) == 1

        # Counter is rendered as 0
        doc = x_todo_counter.assert_render(ws)
        assert doc('strong')[0].text == '0'

        # Switch to "only active tasks" filtering
        x_list.send_user_event(ws, 'show', showing='active')
        doc = x_list.assert_render(ws)
        assert len(doc('x-todo-item li.hidden')) == 1

        # Switch to "only done tasks" filtering
        x_list.send_user_event(ws, 'show', showing='completed')
        doc = x_list.assert_render(ws)
        assert len(doc('x-todo-item')) == 1
        assert len(doc('x-todo-item li.hidden')) == 0

        # Switch to "all tasks" filtering
        x_list.send_user_event(ws, 'show', showing='all')
        doc = x_list.assert_render(ws)
        assert len(doc('x-todo-item')) == 1
        assert len(doc('x-todo-item li.hidden')) == 0

        # Add another task
        x_list.send_user_event(ws, 'add', new_item='Another task')
        doc = x_list.assert_render(ws)
        assert len(doc('x-todo-item')) == 2
        assert len(doc('x-todo-item li.completed')) == 1

        # Cache miss in the counter so re-render
        doc = x_todo_counter.assert_render(ws)
        assert doc('strong')[0].text == '1'

        # Remove completed tasks removes just one task
        x_list.send_user_event(ws, 'clear_completed')
        doc = x_list.assert_render(ws)
        assert len(doc('x-todo-item')) == 1
        assert len(doc('x-todo-item.completed')) == 0

        x_first_item.assert_remove(ws)

        ws.close()
