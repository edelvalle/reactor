from enum import StrEnum

from reactor.component import Component
from reactor.schemas import DomAction, ModelAction

from .models import Item


class Showing(StrEnum):
    ALL = "all"
    COMPLETED = "completed"
    ACTIVE = "active"


class XTodoList(Component):
    _template_name = "todo/list.html"
    _subscriptions = {"item"}

    showing: Showing = Showing.ALL

    @property
    def queryset(self):
        return Item.objects.all()

    @property
    def items(self):
        match self.showing:
            case Showing.ALL:
                qs = self.queryset
            case Showing.COMPLETED:
                qs = self.queryset.filter(completed=True)
            case Showing.ACTIVE:
                qs = self.queryset.filter(completed=False)
        return qs

    async def mutation(
        self,
        channel: str,
        action: ModelAction,
        instance: Item,
    ):
        if action == ModelAction.CREATED:
            await self.dom(
                DomAction.APPEND, "todo-list", XTodoItem, item=instance
            )
        self.skip_render()

    @property
    async def all_items_are_completed(self):
        return (await self.items.acount()) == (
            await self.items.completed().acount()
        )

    async def toggle_all(self, toggle_all: bool):
        await self.items.aupdate(completed=toggle_all)

    async def add(self, new_item: str):
        await Item.objects.acreate(text=new_item)
        self.skip_render()

    async def show(self, showing: Showing):
        self.showing = showing
        self.reactor.params["showing"] = showing

    async def clear_completed(self):
        await self.items.completed().adelete()


class XTodoCounter(Component):
    _template_name = "todo/counter.html"
    _subscriptions = {"item"}

    @property
    def items(self):
        return Item.objects.all()


class XTodoItem(Component):
    _template_name = "todo/item.html"

    @property
    def _subscriptions(self):
        return {f"item.{self.item.id}"}

    item: Item
    editing: bool = False

    async def mutation(self, channel, instance: Item, action):
        if action == ModelAction.DELETED:
            await self.destroy()
        else:
            self.item = instance

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
            await self.send_render()
            await self.focus_on(f"#{self.id} input[name=text]")

    async def save(self, text):
        self.item.text = text
        await self.item.asave()
        self.editing = False
