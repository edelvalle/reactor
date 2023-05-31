from functools import reduce

from channels.layers import BaseChannelLayer
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser

from . import settings
from .component import Component, MessagePayload
from .utils import filter_parameters


class ComponentRepository:
    user: AnonymousUser | AbstractBaseUser

    def __init__(
        self,
        user: AbstractBaseUser | None = None,
        channel_name: str | None = None,
        channel_layer: BaseChannelLayer | None = None,
    ):
        self.channel_name = channel_name
        self.channel_layer = channel_layer
        self.user = user or AnonymousUser()
        self.components: dict[str, Component] = {}

    def get(self, component_id: str) -> Component | None:
        return self.components.get(component_id)

    def new(
        self, name: str, state: MessagePayload, parent_id: str | None = None
    ) -> Component:
        component = Component._new(
            name,
            state,
            user=self.user,
            channel_name=self.channel_name,
            channel_layer=self.channel_layer,
            parent_id=parent_id,
        )
        return self._register_component(component)

    async def join(self, name, state, parent_id=None) -> Component:
        component = await Component._rebuild(
            name,
            state,
            user=self.user,
            channel_name=self.channel_name,
            parent_id=parent_id,
        )
        return self._register_component(component)

    def _register_component(self, component):
        self.components[component.id] = component
        return component

    def remove(self, id):
        self.components.pop(id, None)

    async def dispatch_event(self, id, command, kwargs):
        assert not command.startswith("_")
        component = self.components[id]
        handler = getattr(component, settings.RECEIVER_PREFIX + command)
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
