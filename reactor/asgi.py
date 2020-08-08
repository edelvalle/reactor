
import django

django.setup(set_prefix=False)

from django.conf import settings  # noqa
from django.utils.module_loading import import_module  # noqa
from django.core.handlers.asgi import ASGIHandler  # noqa
from channels.auth import AuthMiddlewareStack  # noqa
from channels.routing import URLRouter  # noqa


urls = import_module(settings.ROOT_URLCONF)


class ASGIHandler(ASGIHandler):
    websocket_handler = AuthMiddlewareStack(
        URLRouter(urls.websocket_urlpatterns)
    )

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'websocket':
            return await self.websocket_handler(scope)(receive, send)
        else:
            return await super().__call__(scope, receive, send)
