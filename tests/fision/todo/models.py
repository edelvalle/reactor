from uuid import uuid4

from django.db import models


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)

    class Meta:
        abstract = True


class ItemQS(models.QuerySet["Item"]):
    def completed(self):
        return self.filter(completed=True)

    def active(self):
        return self.filter(completed=False)


class Item(BaseModel):
    completed = models.BooleanField(default=False)
    text = models.CharField(max_length=256)

    objects: ItemQS = ItemQS.as_manager()  # type: ignore

    def __str__(self):
        return self.text
