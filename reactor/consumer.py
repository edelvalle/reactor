import json
import logging
import typing as t

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.core.signing import Signer
from django.utils.datastructures import MultiValueDict

from reactor.component import Component

from . import serializer
from .repository import ComponentRepository
from .utils import parse_request_data

log = logging.getLogger("reactor")


class ChildComponent(t.TypedDict):
    name: str
    state: str


class ReactorConsumer(AsyncJsonWebsocketConsumer):
    @property
    def user(self):
        return self.scope.get("user") or AnonymousUser()

    async def connect(self):
        await super().connect()
        self.subscriptions = set()
        self.query_string: str = ""
        self.repo = ComponentRepository(
            is_live=True,
            user=self.user,
            channel_name=self.channel_name,
            channel_layer=self.channel_layer,
        )

    # Fronted commands

    async def receive_json(self, content):
        await getattr(self, f'command_{content["command"]}')(
            **content["payload"]
        )

    async def command_join(
        self,
        name: str,
        state: str,
        children: dict[str, ChildComponent] | None = None,
    ):
        signer = Signer()
        decoded_state: dict[str, t.Any] = json.loads(signer.unsign(state))
        decoded_children: dict[str, tuple[str, dict[str, t.Any]]] = {
            id: (name, json.loads(signer.unsign(state)))
            for id, (name, state) in (children or {}).items()
        }
        log.debug(f"<<< JOIN {name} {decoded_state}")
        try:
            component = await self.repo.join(
                name,
                decoded_state,
                children=decoded_children,
            )
        except Exception as e:
            log.exception(e)
            if id := decoded_state.get("id"):
                await self.component_remove(id)
        else:
            await self.send_render(component)
            await self.after_mutation_chores()

    async def command_leave(self, id):
        log.debug(f"<<< LEAVE {id}")
        self.repo.remove(id)

    async def command_query_string(self, qs: str):
        self.query_string = qs
        self.repo.set_query_string(qs)

    async def command_user_event(
        self, id, command, implicit_args, explicit_args
    ):
        kwargs = dict(
            parse_request_data(MultiValueDict(implicit_args)), **explicit_args
        )
        log.debug(f"<<< USER-EVENT {id} {command} {kwargs}")
        component = await self.repo.dispatch_event(id, command, [], kwargs)
        await self.send_render(component)
        await self.after_mutation_chores()

    # Component commands

    async def message_from_component(self, data):
        await getattr(self, f"component_{data['command']}")(**data["kwargs"])

    async def component_dispatch_event(self, id, command, args, kwargs):
        log.debug(f"<<< EVENT {id} {command} {args} {kwargs}")
        component = await self.repo.dispatch_event(id, command, args, kwargs)
        await self.send_render(component)
        await self.after_mutation_chores()

    async def component_remove(self, id):
        log.debug(f">>> REMOVE {id}")
        await self.send_command("remove", {"id": id})

    async def component_send_render(self, id):
        log.debug(f">>> SEND-RENDER {id}")
        if component := self.repo.get(id):
            await self.send_render(component)

    async def component_dom_action(self, action, id, html):
        log.debug(f">>> DOM {action.upper()} {id}")
        await self.send_command(action, {"id": id, "html": html})

    async def component_scroll_into_view(self, id, behavoir, block, inline):
        log.debug(f">>> SCROLL-INTO-VIEW {id}")
        await self.send_command(
            "scroll_into_view",
            {"id": id, "behavoir": behavoir, "block": block, "inline": inline},
        )

    async def component_focus_on(self, selector):
        log.debug(f'>>> FOCUS ON "{selector}"')
        await self.send_command("focus_on", {"selector": selector})

    async def component_url_change(self, command: str, url: str):
        log.debug(f'>>> URL {command.upper()} "{url}"')
        await self.send_command("url_change", {"url": url, "command": command})

    # Incoming messages from subscriptions

    async def model_mutation(self, data):
        # The signature here is coupled to:
        #   `reactor.auto_broadcast.notify_mutation`
        await self._dispatch_notifications(
            "mutation",
            data["channel"],
            {
                "instance": serializer.decode(data["instance"]),
                "action": data["action"],
            },
        )

    async def notification(self, data):
        # The signature here is coupled to:
        #   `reactor.utils.send_notification`
        await self._dispatch_notifications(
            "notification", data["channel"], data["kwargs"]
        )

    async def _dispatch_notifications(
        self, receiver: str, channel: str, kwargs: dict[str, t.Any]
    ):
        for component in self.repo.components_subscribed_to(channel):
            await getattr(component, receiver)(channel, **kwargs)
            await self.send_render(component)
        await self.after_mutation_chores()

    # Reply to front-end

    async def send_render(self, component: Component):
        diff = await component._render_diff(self.repo)
        if diff is not None:
            log.debug(f">>> RENDER {component._name} {component.id}")
            await self.send_command(
                "render",
                {"id": component.id, "diff": diff},
            )

    async def send_command(self, command, payload):
        await self.send_json({"command": command, "payload": payload})

    async def after_mutation_chores(self):
        await self.update_to_which_channels_im_subscribed_to()
        await self.send_query_string()

    async def update_to_which_channels_im_subscribed_to(self):
        if self.channel_layer is not None and self.channel_name is not None:
            subscriptions = self.repo.subscriptions

            # new subscriptions
            for channel in subscriptions - self.subscriptions:
                log.debug(f"::: SUBSCRIBE {self.channel_name} to {channel}")
                await self.channel_layer.group_add(channel, self.channel_name)

            # remove subscriptions
            for channel in self.subscriptions - subscriptions:
                log.debug(f"::: UNSUBSCRIBE {self.channel_name} to {channel}")
                await self.channel_layer.group_discard(
                    channel, self.channel_name
                )

            self.subscriptions = subscriptions

    async def send_query_string(self):
        new_qs = self.repo.get_query_string()
        if self.query_string != new_qs:
            self.query_string = new_qs
            log.debug(f">>> QS {new_qs}")
            await self.send_command("set_query_string", {"qs": new_qs})
