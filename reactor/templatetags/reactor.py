import json
from django import template
from django.db.models import QuerySet, Model
from django.template.loader import render_to_string
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.safestring import mark_safe


from ..component import Component

register = template.Library()


class ReactorJSONEncoder(DjangoJSONEncoder):
    def default(self, o):
        if isinstance(o, Model):
            return o.id
        if isinstance(o, QuerySet):
            return list(o.values_list('id', flat=True))
        return super().default(o)


@register.simple_tag
def reactor_header():
    return render_to_string('reactor_header.html')


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
    return json.dumps(value, cls=ReactorJSONEncoder)


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
