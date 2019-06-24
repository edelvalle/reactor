from django.db.transaction import atomic
from django.shortcuts import render
from reactor.component import Component

from .models import Item


def todo(request):
    return render(request, 'todo.html')


class XTodoList(Component):
    template_name = 'todo/list.html'

    def mount(self, showing='all', **kwargs):
        self.showing = showing
        self.subscribe('item.new')

    def serialize(self):
        return dict(
            id=self.id,
            showing=self.showing,
        )

    @property
    def items(self):
        return Item.objects.all()

    @property
    def all_items_are_completed(self):
        return self.items.count() == self.items.completed.count()

    @atomic
    def receive_add(self, new_item, **kwargs):
        Item.objects.create(text=new_item)

    def receive_show(self, showing, **kwargs):
        self.showing = showing

    @atomic
    def receive_toggle_all(self, toggle_all, **kwargs):
        self.items.update(completed=toggle_all)

    @atomic
    def receive_clear_completed(self, **kwargs):
        self.items.completed.delete()


class XTodoCounter(Component):
    template_name = 'todo/counter.html'

    def mount(self, items=None, *args, **kwargs):
        self.items = items or Item.objects.all()
        self.subscribe('item')


class XTodoItem(Component):
    template_name = 'todo/item.html'

    def mount(self, item=None, editing=False, showing='all', **kwargs):
        self.editing = editing
        self.showing = showing
        self.item = item or Item.objects.filter(id=self.id).first()
        if self.item:
            self.subscribe(f'item.{self.item.id}')
        else:
            self.send_destroy()

    def serialize(self):
        return dict(
            id=self.id,
            editing=self.editing,
            showing=self.showing,
        )

    def is_visible(self):
        return (
            self.showing == 'all' or
            self.showing == 'completed' and self.item.completed or
            self.showing == 'active' and not self.item.completed
        )

    @atomic
    def receive_destroy(self, **kwargs):
        self.item.delete()

    @atomic
    def receive_completed(self, completed, **kwargs):
        self.item.completed = completed
        self.item.save()

    def receive_toggle_editing(self, **kwargs):
        if not self.item.completed:
            self.editing = not self.editing

    @atomic
    def receive_save(self, text, **kwargs):
        self.item.text = text
        self.item.save()
        self.editing = False


class XCounter(Component):

    template_name = 'x-counter.html'

    def mount(self, amount=0, **kwargs):
        self.amount = amount

    def serialize(self):
        return dict(id=self.id, amount=self.amount)

    def receive_inc(self, **kwargs):
        self.amount += 1

    def receive_dec(self, **kwargs):
        self.amount -= 1

    def receive_set_to(self, amount, **kwargs):
        self.amount = amount


def counter(request):
    return render(request, 'counter.html')
