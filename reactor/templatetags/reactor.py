from django import template
from django.template.base import Token, Parser, Node
from django.template.loader import render_to_string
from django.core.signing import Signer
from django.utils.html import format_html


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
def tag_header(context):
    component = context['this']
    return format_html(
        'is="{tag_name}" id="{id}" state="{state}"',
        tag_name=component._tag_name,
        id=component.id,
        state=Signer().sign(component._state_json),
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
        component = Component._build(
            _name,
            request=context['request'],
            id=id,
            **kwargs
        )
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


@register.tag()
def cond(parser: Parser, token: Token):
    dict_expression = token.contents[len('cond '):]
    return CondNode(dict_expression)


@register.tag(name='class')
def class_cond(parser: Parser, token: Token):
    dict_expression = token.contents[len('class '):]
    return ClassNode(dict_expression)


class CondNode(Node):
    def __init__(self, dict_expression):
        self.dict_expression = dict_expression

    def render(self, context):
        terms = eval(self.dict_expression, context.flatten())
        return ' '.join(
            term
            for term, ok in terms.items()
            if ok
        )


class ClassNode(CondNode):
    def render(self, *args, **kwargs):
        text = super().render(*args, **kwargs)
        return f'class="{text}"'
