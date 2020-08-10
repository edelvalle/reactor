
import django

django.setup(set_prefix=False)


def get_asgi_application():
    from django.conf import settings
    from django.utils.module_loading import import_module
    from channels.auth import AuthMiddlewareStack
    from channels.routing import ProtocolTypeRouter, URLRouter

    urls = import_module(settings.ROOT_URLCONF)
    return ProtocolTypeRouter({
        'websocket': AuthMiddlewareStack(URLRouter(
            urls.websocket_urlpatterns,
        ))
    })
