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
    return {"BOOST_PAGES": settings.BOOST_PAGES}


@register.simple_tag(takes_context=True)
def tag_header(context):
    component: Component = context["this"]
    repo: ComponentRepository = context["reactor_repository"]
    return format_html(
        (
            'id="{id}" '
            'data-name="{name}" '
            'data-state="{state}" '
            'data-is-live="{is_live}" '
            "reactor-component"
        ),
        id=component.id,
        name=component._name,
        is_live=str(repo.is_live).lower(),
        state=Signer().sign(component.json(exclude=component._exclude_fields)),
    )


@register.simple_tag(takes_context=True)
def component(context, _name, **kwargs):
    if (repo := context.get("reactor_repository")) is None:
        qs = (
            (request := context.get("request"))
            and request.META["QUERY_STRING"]
            or ""
        )
        repo = ComponentRepository(
            is_live=False,
            user=context.get("user"),
            params=ComponentRepository.extract_params(qs),
        )
        context["reactor_repository"] = repo

    component = repo.build(_name, state=kwargs)
    return component._render(repo) or ""


@register.simple_tag(takes_context=True)
def on(context, _event_and_modifiers, _command, **kwargs: t.Any):
    component: t.Optional[Component] = context.get("this")

    assert component, "Can't find a component in this context"
    handler = getattr(component, _command, None)
    assert handler, f"Missing handler: {component._name}.{_command}"
    assert callable(handler), f"Not callable: {component._name}.{_command}"

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
