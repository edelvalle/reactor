from django.core.serializers import deserialize, serialize
from django.core.serializers.base import DeserializedObject

__all__ = ("encode", "decode")


def encode(instance):
    return serialize("python", [instance])[0]


def decode(instance):
    obj: DeserializedObject = list(deserialize("python", [instance]))[0]
    obj.object.save = obj.save
    return obj.object
