from functools import reduce

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
    ):
        self.channel_name = channel_name
        self.user = user or AnonymousUser()
        self.components: dict[str, Component] = {}

    def new(
        self, name: str, state: MessagePayload, parent_id: str | None = None
    ) -> Component:
        component = Component._new(
            name,
            state,
            user=self.user,
            channel_name=self.channel_name,
            parent_id=parent_id,
        )
        return self._register_component(component)

    def join(self, name, state, parent_id=None) -> Component:
        component = Component._rebuild(
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

    def dispatch_event(self, id, command, kwargs):
        assert not command.startswith("_")
        component = self.components[id]
        handler = getattr(component, settings.RECEIVER_PREFIX + command)
        handler(**filter_parameters(handler, kwargs))
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

    @property
    def messages_to_send(self):
        for component in self.components.values():
            for message in component.reactor._messages_to_send:
                yield message
            component.reactor._messages_to_send = []
