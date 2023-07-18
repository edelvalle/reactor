import json
import typing as t
from functools import reduce
from urllib.parse import parse_qsl, urlencode

from channels.db import database_sync_to_async as db
from channels.layers import BaseChannelLayer
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser

from .component import Component, MessagePayload
from .utils import filter_parameters

ChildrenRepo = dict[str, tuple[str, dict[str, t.Any]]]


class ComponentRepository:
    user: AnonymousUser | AbstractBaseUser

    def __init__(
        self,
        user: AnonymousUser | AbstractBaseUser | None = None,
        params: dict[str, t.Any] | None = None,
        channel_name: str | None = None,
        channel_layer: BaseChannelLayer | None = None,
    ):
        self.params = params or {}
        self.channel_name = channel_name
        self.channel_layer = channel_layer
        self.user = user or AnonymousUser()
        self.components: dict[str, Component] = {}
        self.children: ChildrenRepo = {}

    @staticmethod
    def extract_params(qs: str):
        return {
            key: json.loads(value) if key.endswith(".json") else value
            for key, value in parse_qsl(qs)
        }

    def set_query_string(self, qs: str):
        params = self.extract_params(qs)

        # remove old keys
        for key in list(self.params.keys()):
            if key not in params:
                self.params.pop(key)

        self.params.update(params)

    def get_query_string(self) -> str:
        return urlencode(
            {
                key: json.dumps(value) if key.endswith(".json") else value
                for key, value in self.params.items()
            }
        )

    def get(self, component_id: str) -> Component | None:
        return self.components.get(component_id)

    def build(
        self,
        name: str,
        state: MessagePayload,
        parent_id: str | None = None,
        override_state: bool = True,
    ) -> tuple[Component, bool]:
        if component_id := state.get("id"):
            if component := self.components.get(component_id):
                if override_state:
                    # override with the passed state but preserve the rest of the state
                    for key, value in state.items():
                        setattr(component, key, value)
                    component.reactor.parent_id = parent_id
                return component, False
            elif child := self.children.get(component_id):
                child_name, child_state = child
                if child_name == name:
                    state = child_state | state
                    self.children.pop(component_id)

        component = Component._build(
            name,
            state,
            params=self.params,
            user=self.user,
            channel_name=self.channel_name,
            channel_layer=self.channel_layer,
            parent_id=parent_id,
        )
        return self.register_component(component), True

    async def join(
        self,
        name: str,
        state: MessagePayload,
        parent_id: str | None = None,
        children: ChildrenRepo | None = None,
    ) -> tuple[Component, bool]:
        self.children.update(children or {})
        component, created = await db(self.build)(
            name,
            state,
            parent_id=parent_id,
            override_state=False,
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
