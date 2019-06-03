from uuid import uuid4
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from reactor import broadcast


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)

    class Meta:
        abstract = True


class ItemQS(models.QuerySet):

    @property
    def completed(self):
        return self.filter(completed=True)

    @property
    def active(self):
        return self.filter(completed=False)

    def update(self, *args, **kwargs):
        results = super().update(*args, **kwargs)
        broadcast('item')
        broadcast('item.updated')
        for item in self:
            broadcast(f'item.{item.id}')
        return results


class Item(BaseModel):
    completed = models.BooleanField(default=False)
    text = models.CharField(max_length=256)

    objects = ItemQS.as_manager()

    def __str__(self):
        return self.text


@receiver(post_save, sender=Item)
def emit_element_saved(sender, instance, created, **kwargs):
    broadcast(f'item')
    if created:
        broadcast('item.new')
    else:
        broadcast('item.updated')
        broadcast(f'item.{instance.id}')


@receiver(post_delete, sender=Item)
def emit_element_deleted(sender, instance, **kwargs):
    broadcast('item')
    broadcast('item.deleted')
    broadcast(f'item.{instance.id}')
