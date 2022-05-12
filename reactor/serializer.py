from django.core.serializers import deserialize, serialize
from django.core.serializers.base import DeserializedObject
from django.db.models import Model

__all__ = ("encode", "decode")


def encode(instance: Model) -> str:
    return serialize("python", [instance])[0]


def decode(instance: str) -> Model:
    obj: DeserializedObject = list(deserialize("python", [instance]))[0]
    obj.object.save = obj.save
    return obj.object
