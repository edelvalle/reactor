
import orjson
from django.urls import path
from django.http.response import HttpResponse
from .channels import ReactorConsumer
from .component import Component


def build_component(request, component):
    component = _get_component(request, component)
    return HttpResponse(component._render())


def user_event(request, component, event):
    component = _get_component(request, component)
    args = orjson.loads(request.GET.get('args', '{}'))
    html = ' '.join(component._dispatch(event, args))
    return HttpResponse(html)


def _get_component(request, component) -> Component:
    component = Component._build(component, _context={'user': request.user})
    kwargs = orjson.loads(request.GET.get('state', '{}'))
    component.mount(**kwargs)
    return component


urlpatterns = [
    path('__reactor__/<component>', build_component),
    path('__reactor__/<component>/<event>', user_event),
]

websocket_urlpatterns = [
    path('__reactor__', ReactorConsumer.as_asgi())
]
