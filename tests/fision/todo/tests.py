import json
from pytest import mark

from django.test import TestCase, Client

from channels.db import database_sync_to_async as db
from reactor.tests import reactor

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


@mark.asyncio
@mark.django_db(transaction=True)
async def test_live_components():
    client = Client()
    assert await db(Item.objects.count)() == 0

    html_response = await db(client.get)('/')
    assert html_response.status_code == 200

    async with reactor() as comm:

        x_list = comm.add_component(
            'x-todo-list',
            {'id': 'someid', 'showing': 'all'}
        )
        x_todo_counter = comm.add_component(
            'x-todo-counter',
            {'id': 'someid-counter'}
        )
        doc = await comm.send_join(x_list)
        todo_list = doc('#someid')
        assert json.loads(todo_list.attr['state']) == comm[x_list].state

        # Add new item
        doc = await comm.send(x_list, 'add', new_item='First task')

        # There was an item crated and rendered
        assert await db(Item.objects.count)() == 1
        assert len(doc('[is=x-todo-item]')) == 1
        todo_item_id = doc('[is=x-todo-item]')[0].get('id')
        todo_item_label = doc('[is=x-todo-item] label')[0]
        assert todo_item_label.text == 'First task'

        item = await db(Item.objects.first)()
        assert str(item.id) == todo_item_id
        assert item.text == 'First task'

        # Click title to edit it
        assert len(doc('[is=x-todo-item] li.editing')) == 0
        x_first_item = comm.add_component('x-todo-item', {'id': todo_item_id})
        doc = await comm.send(x_first_item, 'toggle_editing')
        assert len(doc('[is=x-todo-item] li.editing')) == 1

        # Edit item with a new text
        doc = await comm.send(x_first_item, 'save', text='Edited task')
        assert len(doc('[is=x-todo-item] li.editing')) == 0, 'Not in read mode'
        todo_item_label = doc('[is=x-todo-item] label')[0]
        assert todo_item_label.text == 'Edited task'
        await db(item.refresh_from_db)()
        assert item.text == 'Edited task'

        # Check counter has 1 item left
        doc = comm[x_todo_counter].doc
        assert doc('strong')[0].text == '1'

        # Mark item as completed
        assert len(doc('[is=x-todo-item] li.completed')) == 0
        doc = await comm.send(x_first_item, 'completed', completed=True)

        # Item is completed
        assert len(doc('[is=x-todo-item] li.completed')) == 1

        # Counter is rendered as 0
        doc = comm[x_todo_counter].doc
        assert doc('strong')[0].text == '0'

        # Switch to "only active tasks" filtering
        doc = await comm.send(x_list, 'show', showing='active')
        assert len(doc('[is=x-todo-item] li.hidden')) == 1

        # Switch to "only done tasks" filtering
        doc = await comm.send(x_list, 'show', showing='completed')
        assert len(doc('[is=x-todo-item]')) == 1
        assert len(doc('[is=x-todo-item] li.hidden')) == 0

        # Switch to "all tasks" filtering
        doc = await comm.send(x_list, 'show', showing='all')
        assert len(doc('[is=x-todo-item]')) == 1
        assert len(doc('[is=x-todo-item] li.hidden')) == 0

        # Add another task
        doc = await comm.send(x_list, 'add', new_item='Another task')
        assert len(doc('[is=x-todo-item]')) == 2
        assert len(doc('[is=x-todo-item] li.completed')) == 1

        # Cache miss in the counter so re-render
        doc = comm[x_todo_counter].doc
        assert doc('strong')[0].text == '1'

        # Remove completed tasks removes just one task
        doc = await comm.send(x_list, 'clear_completed')
        assert len(doc('[is=x-todo-item]')) == 1
        assert len(doc('[is=x-todo-item].completed')) == 0

        # Cache miss in the counter so re-render
        doc = comm[x_todo_counter].doc
        assert doc('strong')[0].text == '1'
