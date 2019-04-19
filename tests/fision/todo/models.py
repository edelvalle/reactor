from uuid import uuid4
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from reactor.component import send_to_group


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
        send_to_group('item', 'update')
        send_to_group('item.updated', 'update')
        for item in self:
            send_to_group(f'item.{item.id}', 'update')
        return results


class Item(BaseModel):
    completed = models.BooleanField(default=False)
    text = models.CharField(max_length=256)

    objects = ItemQS.as_manager()

    def __str__(self):
        return self.text


@receiver(post_save, sender=Item)
def emit_element_saved(sender, instance, created, **kwargs):
    send_to_group(f'item', 'update')
    if created:
        send_to_group('item.new', 'update')
    else:
        send_to_group('item.updated', 'update')
        send_to_group(f'item.{instance.id}', 'update')


@receiver(post_delete, sender=Item)
def emit_element_deleted(sender, instance, **kwargs):
    send_to_group('item', 'update')
    send_to_group('item.deleted', 'update')
    send_to_group(f'item.{instance.id}', 'update')
