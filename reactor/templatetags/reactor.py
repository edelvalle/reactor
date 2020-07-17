import json
from django import template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe


from ..component import Component
from ..json import Encoder
from ..settings import INCLUDE_TURBOLINKS

register = template.Library()


@register.simple_tag
def reactor_header():
    return render_to_string(
        'reactor_header.html',
        {'include_tlinks': INCLUDE_TURBOLINKS}
    )


@register.simple_tag(takes_context=True)
def component(context, _name, id=None, **kwargs):
    parent = context.get('this')  # type: Component
    if parent:
        component = parent._children.get_or_create(_name, id=id, **kwargs)
    else:
        component = Component.build(_name, context=context, id=id)
        component.mount(**kwargs)
    return component.render()


@register.filter
def concat(value, arg):
    return f'{value}-{arg}'


@register.filter()
def tojson_safe(value):
    return mark_safe(tojson(value))


@register.filter()
def tojson(value):
    return json.dumps(value, cls=Encoder)


@register.filter
def eq(value, other):
    if value == other:
        return 'yes'
    else:
        return ''


@register.filter
def then(value, true_result):
    if value:
        return true_result
    else:
        return ''


@register.filter
def ifnot(value, false_result):
    if not value:
        return false_result
    else:
        return ''
