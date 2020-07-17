from .component import broadcast

from django.dispatch import receiver
from django.db import models
from django.db.models.signals import post_save, pre_delete, m2m_changed


@receiver(post_save)
def broadcast_post_save(sender, instance, created=False, **kwargs):
    name = sender._meta.model_name
    broadcast(name)
    if created:
        broadcast(f'{name}.new')

    if instance.pk is not None:
        broadcast(f'{name}.{instance.pk}')
        broadcast_related(sender, instance, created=created)


@receiver(pre_delete)
def broadcast_post_delete(sender, instance, **kwargs):
    name = sender._meta.model_name
    broadcast(name)
    if instance.pk is not None:
        broadcast(f'{name}.del')
        broadcast(f'{name}.{instance.pk}')
        broadcast_related(sender, instance, deleted=True)


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
        elif isinstance(field, models.ManyToManyField):
            fk_ids = getattr(instance, field.attname).values_list(
                'id', flat=True
            )
            fk_model_name = field.related_model._meta.model_name
            fk_attr_name = field.related_query_name()
            if fk_attr_name != '+':
                group_names = [
                    f'{fk_model_name}.{fk_id}.{fk_attr_name}'
                    for fk_id in fk_ids
                ]
                broadcast(*group_names)
                if created:
                    broadcast(*[f'{gn}.new' for gn in group_names])
                if deleted:
                    broadcast(*[f'{gn}.del' for gn in group_names])


@receiver(m2m_changed)
def broadcast_m2m_changed(
        sender, instance, action, reverse, model, pk_set, **kwargs):
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
