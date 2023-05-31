from pydantic import Field

from reactor.auto_broadcast import Action
from reactor.component import Component

from .models import Item, ItemQS


class XTodoList(Component):
    _template_name = "todo/list.html"
    _subscriptions = {"item"}
    _url_params = {"showing": "showing"}

    showing: str = "all"
    new_item: str = ""

    @property
    def items(self):
        return Item.objects.all()

    async def all_items_are_completed(self):
        return (await self.items.acount()) == (
            await self.items.completed().acount()
        )

    async def add(self, new_item: str):
        await Item.objects.acreate(text=new_item)
        self.new_item = ""

    async def show(self, showing: str):
        self.showing = showing

    async def toggle_all(self, toggle_all: bool = False):
        await self.reactor.redirect_to("/to-index")

    async def clear_completed(self):
        await self.items.completed().adelete()


class XTodoCounter(Component):
    _template_name = "todo/counter.html"
    _subscriptions = {"item"}

    items: ItemQS = Field(default_factory=Item.objects.all)


class XTodoItem(Component):
    _template_name = "todo/item.html"

    @property
    def _subscriptions(self):
        return {f"item.{self.item.id}"}

    item: Item
    editing: bool = False
    showing: str = "all"

    async def mutation(self, channel, instance: Item, action):
        if action == Action.DELETED:
            await self.destroy()
        else:
            self.item = instance

    @property
    def is_visible(self):
        return (
            self.showing == "all"
            or (self.showing == "completed" and self.item.completed)
            or (self.showing == "active" and not self.item.completed)
        )

    async def delete(self):
        await self.item.adelete()
        await self.destroy()

    async def completed(self, completed: bool = False):
        self.item.completed = completed
        await self.item.asave()

    async def toggle_editing(self):
        if not self.item.completed:
            self.editing = not self.editing
        if self.editing:
            await self.focus_on(f"#{self.id} input[name=text]")

    async def save(self, text):
        self.item.text = text
        await self.item.asave()
        self.editing = False
