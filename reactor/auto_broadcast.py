
from django.dispatch import receiver
from django.db import models
from django.db.models.signals import post_save, pre_delete, m2m_changed

from .utils import broadcast
from .settings import AUTO_BROADCAST


MODEL = AUTO_BROADCAST.get('MODEL', False)
MODEL_PK = AUTO_BROADCAST.get('MODEL_PK', False)
RELATED = AUTO_BROADCAST.get('RELATED', False)
M2M = AUTO_BROADCAST.get('M2M', False)


if MODEL or MODEL_PK or RELATED:
    @receiver(post_save)
    def broadcast_post_save(sender, instance, created=False, **kwargs):
        name = sender._meta.model_name
        if MODEL:
            broadcast(name)
            created and broadcast(f'{name}.new')

        if instance.pk is not None:
            MODEL_PK and broadcast(f'{name}.{instance.pk}')
            RELATED and broadcast_related(sender, instance, created=created)

    @receiver(pre_delete)
    def broadcast_post_delete(sender, instance, **kwargs):
        name = sender._meta.model_name
        MODEL and broadcast(name)

        if instance.pk is not None:
            MODEL and broadcast(f'{name}.del')
            MODEL_PK and broadcast(f'{name}.{instance.pk}')
            RELATED and broadcast_related(sender, instance, deleted=True)


def broadcast_related(sender, instance, deleted=False, created=False):
    for field in sender._meta.get_fields():
        if isinstance(field, models.ForeignKey):
            fk_id = getattr(instance, field.attname)
            if fk_id is not None:
                fk_model_name = field.related_model._meta.model_name
                fk_attr_name = field.related_query_name()
                group_name = f'{fk_model_name}.{fk_id}.{fk_attr_name}'
                broadcast(group_name)
                if created:
                    broadcast(f'{group_name}.new')
                if deleted:
                    broadcast(f'{group_name}.del')
        elif M2M and isinstance(field, models.ManyToManyField):
            fk_attr_name = field.related_query_name()
            if fk_attr_name != '+':
                fk_ids = getattr(instance, field.attname).values_list(
                    'id', flat=True
                )
                fk_model_name = field.related_model._meta.model_name
                group_names = [
                    f'{fk_model_name}.{fk_id}.{fk_attr_name}'
                    for fk_id in fk_ids
                ]
                broadcast(*group_names)
                if created:
                    broadcast(*[f'{gn}.new' for gn in group_names])
                if deleted:
                    broadcast(*[f'{gn}.del' for gn in group_names])


if M2M:
    @receiver(m2m_changed)
    def broadcast_m2m_changed(
        sender, instance, action, model, pk_set, **kwargs
    ):
        if action.startswith('post_') and instance.pk:
            model_name = model._meta.model_name
            attr_name = get_name_of(sender, model)
            updates = [f'{model_name}.{pk}.{attr_name}' for pk in pk_set or []]
            broadcast(*updates)
            broadcast(*[f'{u}.{instance.pk}' for u in updates])

            model = type(instance)
            model_name = model._meta.model_name
            attr_name = get_name_of(sender, model)
            update = f'{model_name}.{instance.pk}.{attr_name}'
            broadcast(update)
            broadcast(*[f'{update}.{pk}' for pk in pk_set or []])


def get_name_of(through, model):
    for model_field in model._meta.get_fields():
        found = (
            getattr(model_field, 'through', None) or
            getattr(getattr(model, model_field.name, None), 'through', None)
        )
        if through is found:
            return model_field.name
