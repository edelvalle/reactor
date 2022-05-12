import typing as t

from .layers import BaseChannelLayer, Message

Scope = dict[str, t.Any]

Receive = t.Callable[[str], t.Coroutine[None, None, Message]]
Send = t.Callable[[str, Message], t.Coroutine[None, None, None]]
AsgiApp = t.Callable[[Scope, Receive, Send], t.Coroutine[None, None, None]]

class AsyncConsumer:
    scope: Scope
    channel_layer: None | BaseChannelLayer
    channel_name: None | str
    __call__: AsgiApp
    async def dispatch(self, message: dict[t.Any, t.Any]) -> None: ...
    async def send(self, message: dict[t.Any, t.Any]) -> None: ...
    @classmethod
    async def as_asgi(cls, **initkwargs: t.Any) -> AsgiApp: ...
