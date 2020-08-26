from typing import Generator
import orjson

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


def loads(text_data):
    return orjson.loads(text_data)


def dumps(obj, indent=False):
    option = (
        orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY
    )
    if indent:
        option |= orjson.OPT_INDENT_2
    return orjson.dumps(obj, default=default, option=option).decode()


def default(o):
    if isinstance(o, models.Model):
        return o.pk

    if isinstance(o, models.QuerySet):
        return list(o.values_list('pk', flat=True))

    if isinstance(o, (Generator, set)):
        return list(o)

    if hasattr(o, '__json__'):
        return o.__json__()

    return DjangoJSONEncoder().default(o)


class Encoder:
    def __init__(self, *args, **kwargs):
        pass

    def encode(self, obj):
        return dumps(obj)
