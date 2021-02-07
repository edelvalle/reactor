from django.db.transaction import atomic
from reactor.component import Component

from .models import Item


class XTodoList(Component):
    template_name = 'todo/list.html'

    def __init__(self, showing='all', new_item='', **kwargs):
        super().__init__(**kwargs)
        self.showing = showing
        self.new_item = new_item
        self._subscribe('item.new')

    @property
    def items(self):
        return Item.objects.all()

    @property
    def all_items_are_completed(self):
        return self.items.count() == self.items.completed.count()

    @atomic
    def add(self, new_item: str):
        Item.objects.create(text=new_item)
        self.new_item = ''

    def show(self, showing: str):
        self.showing = showing

    @atomic
    def toggle_all(self, toggle_all: bool):
        self.items.update(completed=toggle_all)

    @atomic
    def clear_completed(self):
        self.items.completed.delete()


class XTodoCounter(Component):
    template_name = 'todo/counter.html'

    def __init__(self, items=None, **kwargs):
        super().__init__(**kwargs)
        self.items = items or Item.objects.all()
        self._subscribe('item')


class XTodoItem(Component):
    template_name = 'todo/item.html'

    def __init__(self, item=None, editing=False, showing='all', **kwargs):
        super().__init__(**kwargs)
        self.editing = editing
        self.showing = showing
        self.item = item or Item.objects.filter(id=self.id).first()
        if self.item:
            self._subscribe(f'item.{self.item.id}')
        else:
            super().destroy()

    def is_visible(self):
        return (
            self.showing == 'all' or
            self.showing == 'completed' and self.item.completed or
            self.showing == 'active' and not self.item.completed
        )

    @atomic
    def destroy(self):
        self.item.delete()
        super().destroy()

    @atomic
    def completed(self, completed: bool = False):
        self.item.completed = completed
        self.item.save()

    def toggle_editing(self):
        if not self.item.completed:
            self.editing = not self.editing

    @atomic
    def save(self, text):
        self.item.text = text
        self.item.save()
        self.editing = False
