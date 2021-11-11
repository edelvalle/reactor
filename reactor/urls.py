import json

from django.http.response import HttpResponse
from django.urls import path

from .component import Component
from .consumer import ReactorConsumer


def build_component(request, component):
    component = _get_component(request, component)
    return HttpResponse(component._render())


def user_event(request, component, event):
    component = _get_component(request, component)
    args = json.loads(request.GET.get("args", "{}"))
    html = " ".join(component._dispatch(event, args))
    return HttpResponse(html)


def _get_component(request, component) -> Component:
    component = Component._build(component, _context={"user": request.user})
    kwargs = orjson.loads(request.GET.get("state", "{}"))
    component.mount(**kwargs)
    return component


urlpatterns = [
    path("__reactor__/<component>", build_component),
    path("__reactor__/<component>/<event>", user_event),
]

websocket_urlpatterns = [path("__reactor__", ReactorConsumer.as_asgi())]
