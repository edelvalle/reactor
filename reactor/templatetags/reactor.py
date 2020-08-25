from django import template
from django.template.loader import render_to_string


from .. import json
from ..component import Component
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
        component = parent._root_component.get_or_create(
            _name,
            _parent_id=parent.id,
            id=id,
            **kwargs
        )
    else:
        component = Component._build(_name, _context=context, id=id)
        component.mount(**kwargs)
    return component._render()


@register.filter
def concat(value, arg):
    return f'{value}-{arg}'


@register.filter()
def tojson(value, indent=None):
    return json.dumps(value, indent=indent)


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
