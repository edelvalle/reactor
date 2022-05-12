from django.urls import path

from .consumer import ReactorConsumer

websocket_urlpatterns = [
    path("__reactor__", ReactorConsumer.as_asgi()),  # type: ignore
]
