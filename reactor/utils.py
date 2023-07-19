import inspect
import logging
import typing as t
from collections import defaultdict
from functools import wraps

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async as db
from channels.layers import get_channel_layer
from django.utils.datastructures import MultiValueDict

log = logging.getLogger("reactor")

P = t.ParamSpec("P")

__all__ = (
    "on_commit",
    "db",
    "send_to",
    "send_notification",
    "filter_parameters",
    "parse_request_data",
)


def on_commit(f: t.Callable[P, None]):
    @wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs):
        from django.db.transaction import on_commit  # type: ignore

        on_commit(lambda: f(*args, **kwargs))

    return wrapper


@on_commit
def send_to(channel: t.Optional[str], type: str, **kwargs: t.Any):
    """Sends a message of `type` to the"""
    if channel:
        async_to_sync(get_channel_layer().group_send)(
            channel, dict(type=type, channel=channel, **kwargs)
        )


@on_commit
def send_notification(channel: str, **kwargs):
    log.debug(f"<-> NOTIFICATION {channel} {kwargs}")
    send_to(channel, "notification", kwargs=kwargs)


# Introspection


def filter_parameters(f, kwargs):
    has_kwargs = any(
        param.kind == inspect.Parameter.VAR_KEYWORD
        for param in inspect.signature(f).parameters.values()
    )
    if has_kwargs:
        return kwargs
    else:
        return {
            param: value
            for param, value in kwargs.items()
            if param in f.model.__fields__
        }


# Decoder for client requests
def parse_request_data(data: MultiValueDict[str, t.Any]):
    return _parse_obj(_extract_data(data))


def _extract_data(data: MultiValueDict[str, t.Any]):
    for key in set(data):
        if key.endswith("[]"):
            key = key.removesuffix("[]")
            value = data.getlist(key)
        else:
            value = data.get(key)
        yield key.split("."), value


def _parse_obj(
    data: t.Iterable[tuple[list[str], t.Any]], output=None
) -> dict[str, t.Any] | t.Any:
    output = output or {}
    arrays = defaultdict(lambda: defaultdict(dict))  # field -> index -> value
    for key, value in data:
        fragment, *tail = key
        if "[" in fragment:
            field_name = fragment[: fragment.index("[")]
            index = int(fragment[fragment.index("[") + 1 : -1])
            arrays[field_name][index] = (
                _parse_obj([(tail, value)], arrays[field_name][index])
                if tail
                else value
            )
        else:
            output[fragment] = _parse_obj([(tail, value)]) if tail else value

    for field, items in arrays.items():
        output[field] = [
            v for _, v in sorted(items.items(), key=lambda kv: kv[0])
        ]
    return output


data = [
    (["a"], [2, 2, 3, 5, 5]),
    (["b"], 2),
    (["x[0]"], 10),
    (["x[1]"], 20),
    (["c[1]", "a"], 1),
    (["c[0]", "a"], 3),
    (["c[1]", "b"], 1),
    (["c[0]", "b"], 4),
]


assert _parse_obj(data) == {
    "a": [2, 2, 3, 5, 5],
    "b": 2,
    "c": [{"a": 3, "b": 4}, {"a": 1, "b": 1}],
    "x": [10, 20],
}
