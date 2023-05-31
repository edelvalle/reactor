import typing as t

from django import template
from django.core.signing import Signer
from django.template.base import Node, Parser, Token
from django.utils.html import format_html

from .. import settings
from ..component import Component
from ..event_transpiler import transpile
from ..repository import ComponentRepository

register = template.Library()


@register.inclusion_tag("reactor_header.html")
def reactor_header():
    return {
        "components": [
            {"tag_name": component._tag_name, "extends": component._extends}
            for component in Component._all.values()
        ],
        "BOOST_PAGES": settings.BOOST_PAGES,
    }


@register.simple_tag(takes_context=True)
def tag_header(context):
    component = context["this"]
    return format_html(
        'is="{tag_name}" '
        'id="{id}" '
        'data-name="{name}" '
        'data-state="{state}"'
        "reactor-component",
        tag_name=component._tag_name,
        id=component.id,
        name=component._name,
        state=Signer().sign(component.json(exclude=component._exclude_fields)),
    )


@register.simple_tag(takes_context=True)
def component(context, _name, **kwargs):
    parent: t.Optional[Component] = context.get("this")
    parent_id = parent.id if parent else None

    repo: ComponentRepository = context.get(
        "reactor_repository",
        ComponentRepository(user=context.get("user")),
    )

    component = repo.new(_name, state=kwargs, parent_id=parent_id)
    return component.render(repo) or ""


@register.simple_tag(takes_context=True)
def on(context, _event_and_modifiers, _command, **kwargs: t.Any):
    component: t.Optional[Component] = context.get("this")

    assert component, "Can't find a component in this context"
    attr_name = settings.RECEIVER_PREFIX + _command
    handler = getattr(component, attr_name, None)
    assert handler, f"Missing handler: {component._name}.{attr_name}"
    assert callable(handler), f"Not callable: {component._name}.{attr_name}"

    event, code = transpile(_event_and_modifiers, _command, kwargs)
    return format_html('{event}="{code}"', event=event, code=code)


@register.filter(name="str")
def to_string(value):
    return str(value)


@register.filter
def concat(value, arg):
    return f"{value}{arg}"


# Shortcuts and helpers


@register.tag()
def cond(parser: Parser, token: Token):
    """Prints some text conditionally

        ```html
        {% cond {'works': True, 'does not work': 1 == 2} %}
        ```
    Will output 'works'.
    """
    dict_expression = token.contents[len("cond ") :]
    return CondNode(dict_expression)


@register.tag(name="class")
def class_cond(parser: Parser, token: Token):
    """Prints classes conditionally

    ```html
    <div {% class {'btn': True, 'loading': loading, 'falsy': 0} %}></div>
    ```

    If `loading` is `True` will print:

    ```html
    <div class="btn loading"></div>
    ```
    """
    dict_expression = token.contents[len("class ") :]
    return ClassNode(dict_expression)


class CondNode(Node):
    def __init__(self, dict_expression):
        self.dict_expression = dict_expression

    def render(self, context):
        variables: dict[str, t.Any] = context.flatten()  # type: ignore
        terms = eval(self.dict_expression, variables)
        return " ".join(term for term, ok in terms.items() if ok)


class ClassNode(CondNode):
    def render(self, *args, **kwargs):
        text = super().render(*args, **kwargs)
        return f'class="{text}"'
