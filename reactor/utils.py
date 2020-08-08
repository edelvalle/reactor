import logging
from functools import wraps

from asgiref.sync import async_to_sync

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
