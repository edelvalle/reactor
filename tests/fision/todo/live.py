from django.db.transaction import atomic
from pydantic import Field

from reactor.auto_broadcast import Action
from reactor.component import Component
from reactor.fields import Model, QuerySet

from .models import Item


class XTodoList(Component):
    _template_name = "todo/list.html"
    _subscriptions = {"item"}
    _url_params = {"showing": "showing"}

    showing: str = "all"
    new_item: str = ""

    @property
    def items(self):
        return Item.objects.all()

    @property
    def all_items_are_completed(self):
        return self.items.count() == self.items.completed.count()

    @atomic
    def add(self, new_item: str):
        Item.objects.create(text=new_item)
        self.new_item = ""

    def show(self, showing: str):
        self.showing = showing

    @atomic
    def toggle_all(self, toggle_all: bool = False):
        self.reactor.redirect_to("/to-index")

    @atomic
    def clear_completed(self):
        self.items.completed.delete()


class XTodoCounter(Component):
    _template_name = "todo/counter.html"
    _subscriptions = {"item"}

    items: QuerySet[Item] = Field(default_factory=Item.objects.all)


class XTodoItem(Component):
    _template_name = "todo/item.html"

    @property
    def _subscriptions(self):
        return {f"item.{self.item.id}"}

    item: Model[Item]
    editing: bool = False
    showing: str = "all"

    def mutation(self, channel, instance, action):
        if action == Action.DELETED:
            self.destroy()
        else:
            self.item = instance

    @property
    def is_visible(self):
        return (
            self.showing == "all"
            or (self.showing == "completed" and self.item.completed)
            or (self.showing == "active" and not self.item.completed)
        )

    @atomic
    def delete(self):
        self.item.delete()
        self.destroy()

    @atomic
    def completed(self, completed: bool = False):
        self.item.completed = completed
        self.item.save()

    def toggle_editing(self):
        if not self.item.completed:
            self.editing = not self.editing
        if self.editing:
            self.focus_on(f"#{self.id} input[name=text]")

    @atomic
    def save(self, text):
        self.item.text = text
        self.item.save()
        self.editing = False
