from typing import Generator

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


class Encoder(DjangoJSONEncoder):

    def default(self, o):
        if isinstance(o, models.Model):
            return o.pk

        if isinstance(o, models.QuerySet):
            return list(o.values_list('pk', flat=True))

        if isinstance(o, (Generator, set)):
            return list(o)

        if hasattr(o, '__json__'):
            return o.__json__()

        return super().default(o)
