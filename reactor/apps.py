from django.apps import AppConfig
from django.utils.module_loading import autodiscover_modules


class ReactorConfig(AppConfig):
    name = "reactor"
    verbose_name = "Django Reactor"

    def ready(self):
        from . import auto_broadcast  # noqa

        autodiscover_modules("live")
