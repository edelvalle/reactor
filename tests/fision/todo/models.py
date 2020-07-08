from uuid import uuid4
from django.db import models


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


class Item(BaseModel):
    completed = models.BooleanField(default=False)
    text = models.CharField(max_length=256)

    objects = ItemQS.as_manager()

    def __str__(self):
        return self.text
