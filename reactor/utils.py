import inspect
import logging
from functools import wraps

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils.datastructures import MultiValueDict

log = logging.getLogger("reactor")


def broadcast(*names, **kwargs):
    for name in names:
        log.debug(f"<-> {name}")
        send_to_group(name, "model_mutation", **kwargs)


def on_commit(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        from django.db.transaction import on_commit

        on_commit(lambda: f(*args, **kwargs))

    return wrapper


def send_to_group(_whom, type, **kwargs):
    if _whom:

        @on_commit
        def send_message():
            async_to_sync(get_channel_layer().group_send)(
                _whom, dict(type=type, origin=_whom, **kwargs)
            )

        send_message()


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


def parse_request_data(data: MultiValueDict):
    output = {}
    for key in set(data):
        if key.endswith("[]"):
            value = data.getlist(key)
        else:
            value = data.get(key)
        _set_value_on_path(output, key, value)
    return output


def _set_value_on_path(target, path, value):
    initial = target
    fragments = path.split(".")
    for fragment in fragments[:-1]:
        fragment, default, index = _get_default_value(fragment)
        target.setdefault(fragment, default)
        target = target[fragment]
        if index is not None:
            i_need_this_length = index + 1 - len(target)
            if i_need_this_length > 0:
                target.extend({} for _ in range(i_need_this_length))
            target = target[index]

    fragment, default, index = _get_default_value(fragments[-1])
    target[fragment] = value
    return initial


def _get_default_value(fragment):
    if fragment.endswith("[]"):
        fragment = fragment[:-2]
        default = []
        index = None
    if fragment.endswith("]"):
        index = int(fragment[fragment.index("[") + 1 : -1])
        fragment = fragment[: fragment.index("[")]
        default = []
    else:
        default = {}
        index = None
    return fragment, default, index
