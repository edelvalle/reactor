from django.urls import path

from . import channels


websocket_urlpatterns = [
    path('reactor', channels.ReactorConsumer)
]
