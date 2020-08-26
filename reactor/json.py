from typing import Generator
import orjson

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


def loads(text_data):
    return orjson.loads(text_data)


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


def dumps(obj, indent=False, default=default):
    option = (
        orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY
    )
    if indent:
        option |= orjson.OPT_INDENT_2
    return orjson.dumps(obj, default=default, option=option).decode()


class Encoder:
    def __init__(self, *args, **kwargs):
        pass

    def default(self, obj):
        return default(obj)

    def encode(self, obj):
        return dumps(obj, default=self.default)
