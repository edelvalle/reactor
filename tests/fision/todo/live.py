from reactor.component import Component
from reactor.schemas import DomAction, ModelAction

from .models import Item, ItemQS


class XTodoList(Component):
    _template_name = "todo/list.html"
    _subscriptions = {"item"}
    _url_params = {"showing": "showing"}

    showing: str = "all"
    new_item: str = ""

    items: ItemQS

    async def mutation(self, channel, action: ModelAction, instance: Item):
        if action == ModelAction.CREATED:
            await self.dom(
                DomAction.APPEND,
                "todo-list",
                XTodoItem,
                id=f"item-{instance.id}",
                item=instance,
            )
        self.skip_render()

    @property
    async def all_items_are_completed(self):
        return (await self.items.acount()) == (
            await self.items.completed().acount()
        )

    async def add(self, new_item: str):
        await Item.objects.acreate(text=new_item)
        self.skip_render()
        self.new_item = ""

    async def show(self, showing: str):
        self.showing = showing

    async def toggle_all(self, itoggle_all: bool = False):
        await self.reactor.redirect_to("/to-index")

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
    showing: str = "all"

    async def mutation(self, channel, instance: Item, action):
        if action == ModelAction.DELETED:
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
            await self.send_render()
            await self.focus_on(f"#{self.id} input[name=text]")

    async def save(self, text):
        self.item.text = text
        await self.item.asave()
        self.editing = False
        self.editing = False
