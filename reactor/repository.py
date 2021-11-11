from django.contrib.auth.models import AnonymousUser

from .component import Component
from .utils import filter_parameters


class ComponentRepository:
    def __init__(self, user=None, channel_name=None):
        self.channel_name = channel_name
        self.user = user or AnonymousUser()
        self.components: dict[str, Component] = {}

    def build(self, name, state, parent_id=None) -> Component:
        if (id := state.get("id")) and (component := self.components.get(id)):
            component = component.copy(update=state)
        else:
            component = Component._build(
                name,
                state,
                user=self.user,
                channel_name=self.channel_name,
                parent_id=parent_id,
            )
        self.components[component.id] = component
        return component

    def remove(self, id):
        self.components.pop(id, None)

    def dispatch_event(self, id, command, kwargs):
        assert not command.startswith("_")
        component = self.components[id]
        handler = getattr(component, command)
        handler(**filter_parameters(handler, kwargs))
        return component

    def components_subscribed_to(self, channel):
        # XXX: There is a list() here because the dict can change size during
        # iteration
        for component in list(self.components.values()):
            if channel in component.reactor._subscriptions:
                yield component

    @property
    def messages_to_send(self):
        for component in self.components.values():
            for message in component.reactor._messages_to_send:
                yield message
            component.reactor._messages_to_send = []
