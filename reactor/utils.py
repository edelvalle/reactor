import inspect
import logging
import typing
from functools import wraps

import pydantic
from asgiref.sync import async_to_sync

from django.http import QueryDict
from channels.layers import get_channel_layer

log = logging.getLogger('reactor')


def broadcast(*names, **kwargs):
    for name in names:
        log.debug(f'<-> {name}')
        send_to_group(name, 'update', **kwargs)


def on_commit(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        from django.db.transaction import on_commit
        on_commit(lambda: f(*args, **kwargs))
    return wrapper


def send_to_channel(_channel_name, type, **kwargs):
    if _channel_name:
        @on_commit
        def send_message():
            async_to_sync(get_channel_layer().send)(
                _channel_name, dict(type=type, **kwargs)
            )
        send_message()


def send_to_group(_whom, type, **kwargs):
    if _whom:
        @on_commit
        def send_message():
            async_to_sync(get_channel_layer().group_send)(
                _whom, dict(type=type, origin=_whom, **kwargs)
            )
        send_message()


# Introspection


def get_model(f, ignore=()):
    params = list(inspect.signature(f).parameters.values())
    fields = {}
    for param in params:
        if param.name in ignore:
            continue
        if param.kind is not inspect.Parameter.VAR_KEYWORD:
            default = param.default
            if default is inspect._empty:
                default = ...
            annotation = param.annotation
            if annotation is inspect._empty:
                if default is ...:
                    field = (typing.Any, ...)
                else:
                    field = default
            else:
                field = (annotation, default)

            if field is None:
                continue
            fields[param.name] = field
    return pydantic.create_model(f.__name__, **fields)


# Decoder for client requests

def extract_data(arguments):
    query = QueryDict(mutable=True)
    for key, value in arguments:
        query.appendlist(key, value)

    kwargs = {}
    for key in set(query):
        if key.endswith('[]'):
            value = query.getlist(key)
        else:
            value = query.get(key)
        _set_value_on_path(kwargs, key, value)
    return kwargs


def _set_value_on_path(target, path, value):
    initial = target
    parts = path.split('.')
    for part in parts[:-1]:
        part, default, index = _get_default_value(part)
        target.setdefault(part, default)
        target = target[part]
        if index is not None:
            i_need_this_length = index + 1 - len(target)
            if i_need_this_length > 0:
                target.extend({} for _ in range(i_need_this_length))
            target = target[index]

    part, default, index = _get_default_value(parts[-1])
    target[part] = value
    return initial


def _get_default_value(part):
    if part.endswith('[]'):
        part = part[:-2]
        default = []
        index = None
    if part.endswith(']'):
        index = int(part[part.index('[') + 1:-1])
        part = part[:part.index('[')]
        default = []
    else:
        default = {}
        index = None
    return part, default, index
