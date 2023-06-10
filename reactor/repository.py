from functools import reduce

from channels.db import database_sync_to_async as db
from channels.layers import BaseChannelLayer
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser

from .component import Component, MessagePayload
from .utils import filter_parameters


class ComponentRepository:
    user: AnonymousUser | AbstractBaseUser

    def __init__(
        self,
        user: AnonymousUser | AbstractBaseUser | None = None,
        channel_name: str | None = None,
        channel_layer: BaseChannelLayer | None = None,
    ):
        self.channel_name = channel_name
        self.channel_layer = channel_layer
        self.user = user or AnonymousUser()
        self.components: dict[str, Component] = {}

    def get(self, component_id: str) -> Component | None:
        return self.components.get(component_id)

    def build(
        self, name: str, state: MessagePayload, parent_id: str | None = None
    ) -> tuple[Component, bool]:
        if (component_id := state.get("id")) and (
            component := self.components.get(component_id)
        ):
            # override with the passed state but preserve the rest of the state
            for key, value in state.items():
                setattr(component, key, value)
            component.reactor.parent_id = parent_id
            return component, False
        else:
            component = Component._build(
                name,
                state,
                user=self.user,
                channel_name=self.channel_name,
                channel_layer=self.channel_layer,
                parent_id=parent_id,
            )
            return self.register_component(component), True

    async def join(
        self, name: str, state: MessagePayload, parent_id: str | None = None
    ) -> tuple[Component, bool]:
        component, created = await db(self.build)(
            name, state, parent_id=parent_id
        )
        if created:
            await component.joined()
        return component, created

    def register_component(self, component: Component):
        self.components[component.id] = component
        return component

    def remove(self, id):
        self.components.pop(id, None)

    async def dispatch_event(self, id, command, kwargs):
        assert not command.startswith("_")
        component = self.components[id]
        handler = getattr(component, command)
        await handler(**filter_parameters(handler, kwargs))
        return component

    def components_subscribed_to(self, channel):
        # XXX: There is a list() here because the dict can change size during
        # iteration
        for component in list(self.components.values()):
            if channel in component._subscriptions:
                yield component

    @property
    def subscriptions(self):
        return reduce(
            lambda a, b: a.union(b),
            (
                component._subscriptions
                for component in list(self.components.values())
            ),
            set(),
        )
