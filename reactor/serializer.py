import typing as t

from django.core.serializers import deserialize, serialize
from django.core.serializers.base import DeserializedObject
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Model
from pydantic import BaseModel

__all__ = ("encode", "decode")


def encode(instance: Model) -> str:
    return serialize("json", [instance], cls=ReactorJSONEncoder)


def decode(instance: str) -> Model:
    obj: DeserializedObject = list(deserialize("json", instance))[0]
    obj.object.save = obj.save
    return obj.object


class ReactorJSONEncoder(DjangoJSONEncoder):
    def default(self, o: t.Any) -> t.Any:
        if isinstance(o, BaseModel):
            return o.dict()
        else:
            return super().default(o)
