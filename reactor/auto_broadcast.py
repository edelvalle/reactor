import logging
import typing as t

from django.db import models
from django.db.models.signals import m2m_changed, post_save, pre_delete
from django.dispatch import receiver

from . import serializer
from .settings import AUTO_BROADCAST
from .utils import send_to

__all__ = ("Action",)

log = logging.getLogger("reactor")


MODEL = AUTO_BROADCAST.get("MODEL", False)
MODEL_PK = AUTO_BROADCAST.get("MODEL_PK", False)
RELATED = AUTO_BROADCAST.get("RELATED", False)
M2M = AUTO_BROADCAST.get("M2M", False)


class Action:
    # Model action
    UPDATED = "UPDATED"
    DELETED = "DELETED"
    CREATED = "CREATED"

    # M2M actions
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    CLEARED = "CLEARED"

    T = (
        t.Literal["UPDATED"]
        | t.Literal["DELETED"]
        | t.Literal["CREATED"]
        | t.Literal["ADDED"]
        | t.Literal["REMOVED"]
        | t.Literal["CLEARED"]
    )


if MODEL or MODEL_PK or RELATED:

    @receiver(post_save)
    def broadcast_post_save(sender, instance, created=False, **kwargs):
        name = sender._meta.model_name
        encoded_instance = serializer.encode(instance)
        action = Action.CREATED if created else Action.UPDATED
        if MODEL:
            notify_mutation([name], encoded_instance, action)

        if instance.pk is not None:
            if MODEL_PK:
                notify_mutation(
                    [f"{name}.{instance.pk}"],
                    encoded_instance,
                    action,
                )
            if RELATED:
                broadcast_related(
                    sender, instance, encoded_instance, action=action
                )

    @receiver(pre_delete)
    def broadcast_pre_delete(sender, instance, **kwargs):
        name = sender._meta.model_name
        encoded_instance = serializer.encode(instance)
        if MODEL:
            notify_mutation([name], encoded_instance, Action.DELETED)

        if instance.pk is not None:
            if MODEL_PK:
                notify_mutation(
                    [f"{name}.{instance.pk}"],
                    encoded_instance,
                    Action.DELETED,
                )
            if RELATED:
                broadcast_related(
                    sender, instance, encoded_instance, Action.DELETED
                )


def broadcast_related(sender, instance, encoded_instance, action: Action.T):
    for field in get_related_fields(sender):
        if field["is_m2m"]:
            fk_ids = getattr(instance, field["name"]).values_list(
                "id", flat=True
            )
        else:
            fk_ids = filter(None, [getattr(instance, field["name"])])

        if fk_ids:
            group_names = [
                f'{field["related_model_name"]}.{fk_id}.{field["related_name"]}'
                for fk_id in fk_ids
            ]
            notify_mutation(group_names, encoded_instance, action)


MODEL_RELATED_FIELDS = {}


def get_related_fields(model):
    related_fields = MODEL_RELATED_FIELDS.get(model)
    if related_fields is None:
        fields = []
        for field in model._meta.get_fields():
            if isinstance(field, (models.ForeignKey, models.ManyToManyField)):
                related_name = field.related_query_name()
                if related_name != "+":
                    is_m2m = isinstance(field, models.ManyToManyField)
                    if not is_m2m or M2M and is_m2m:
                        fields.append(
                            {
                                "is_m2m": is_m2m,
                                "name": field.attname,
                                "related_name": related_name,
                                "related_model_name": field.related_model._meta.model_name,  # noqa
                            }
                        )
        related_fields = MODEL_RELATED_FIELDS[model] = tuple(fields)
    return related_fields


if M2M:

    @receiver(m2m_changed)
    def broadcast_m2m_changed(
        sender, instance, action, model, pk_set, **kwargs
    ):
        if action.startswith("post_") and instance.pk:
            encoded_instance = serializer.encode(instance)
            if action.endswith("_add"):
                action = Action.ADDED
            elif action.endswith("_remove"):
                action = Action.REMOVED
            elif action.endswith("_clear"):
                action = Action.CLEARED
            else:
                assert False, f"Unknown action `{action}`"

            model_name = model._meta.model_name
            attr_name = get_name_of(sender, model)
            updates = [f"{model_name}.{pk}.{attr_name}" for pk in pk_set or []]
            notify_mutation(updates, encoded_instance, action)

            model = type(instance)
            model_name = model._meta.model_name
            attr_name = get_name_of(sender, model)
            update = f"{model_name}.{instance.pk}.{attr_name}"
            notify_mutation(
                [f"{update}.{pk}" for pk in pk_set or []],
                encoded_instance,
                action,
            )


def get_name_of(through, model):
    for model_field in model._meta.get_fields():
        found = getattr(model_field, "through", None) or getattr(
            getattr(model, model_field.name, None), "through", None
        )
        if through is found:
            return model_field.name


def notify_mutation(names: t.Iterable[str], instance: str, action: Action.T):
    for name in (n.replace("_", "-") for n in names):
        log.debug(f"<-> {action} {name}")
        send_to(name, "model_mutation", instance=instance, action=action)
