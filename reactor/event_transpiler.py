import json
import typing as t

from django.core.serializers.json import DjangoJSONEncoder

from . import settings

Stack = list[t.Any]


def transpile(event_and_modifiers: str, command: str, kwargs: dict[str, t.Any]):
    """Translates from from the tag `on` in to JavaScript"""
    name, *modifiers = event_and_modifiers.split(".")
    cache_key = f"_handler:{modifiers}.{command}.{kwargs}"
    code: t.Optional[str] = settings.transpiler_cache.get(cache_key)
    if code is None:
        if not modifiers or modifiers[-1] != "inlinejs":
            modifiers.append("_reactor_code")
        code = command
        stack: Stack = [kwargs]
        while modifiers:
            modifier = modifiers.pop()
            handler: t.Optional[t.Callable[[str, Stack], str]] = getattr(
                Modifiers, modifier, None
            )
            if handler:
                code = handler(code, stack)
            else:
                stack.append(modifier)

        settings.transpiler_cache.set(cache_key, code)
    return "on" + name, code


class Modifiers:
    @staticmethod
    def _reactor_code(code: str, stack: Stack):
        kwargs = json.dumps(stack.pop(), cls=DjangoJSONEncoder)
        return f"reactor.send(event.target, '{code}', {kwargs})"

    @staticmethod
    def _add_curly(code: str):
        return "{%s}" % (code,)

    @staticmethod
    def inlinejs(code: str, stack: Stack):
        return code

    # Events

    @classmethod
    def debounce(cls, code: str, stack: Stack):
        name = stack.pop()
        delay = stack.pop()
        code = cls._add_curly(code)
        return f"reactor.debounce('{name}', {delay})(() => {code})()"

    @staticmethod
    def prevent(code: str, stack: Stack):
        return "event.preventDefault(); " + code

    @staticmethod
    def stop(code: str, stack: Stack):
        return "event.stopPropagation(); " + code

    # Key modifiers

    @classmethod
    def ctrl(cls, code: str, stack: Stack):
        code = cls._add_curly(code)
        return f"if (event.ctrlKey) {code}"

    @classmethod
    def alt(cls, code: str, stack: Stack):
        code = cls._add_curly(code)
        return f"if (event.altKey) {code}"

    @classmethod
    def shift(cls, code: str, stack: Stack):
        code = cls._add_curly(code)
        return f"if (event.shiftKey) {code}"

    @classmethod
    def meta(cls, code: str, stack: Stack):
        code = cls._add_curly(code)
        return f"if (event.metaKey) {code}"

    # Key codes

    @classmethod
    def key(cls, code: str, stack: Stack):
        key = stack.pop()
        code = cls._add_curly(code)
        return f"if ((event.key + '').toLowerCase() == '{key}') {code}"

    @classmethod
    def key_code(cls, code: str, stack: Stack):
        keyCode = stack.pop()
        code = cls._add_curly(code)
        return f"if (event.keyCode == {keyCode}) {code}"

    # Key shortcuts
    @classmethod
    def enter(cls, code: str, stack: Stack):
        return cls.key(code, ["enter"])

    @classmethod
    def tab(cls, code: str, stack: Stack):
        return cls.key(code, ["tab"])

    @classmethod
    def delete(cls, code: str, stack: Stack):
        return cls.key(code, ["delete"])

    @classmethod
    def backspace(cls, code: str, stack: Stack):
        return cls.key(code, ["backspace"])

    @classmethod
    def esc(cls, code: str, stack: Stack):
        return cls.key(code, ["escape"])

    @classmethod
    def space(cls, code: str, stack: Stack):
        return cls.key(code, [" "])

    @classmethod
    def up(cls, code: str, stack: Stack):
        return cls.key(code, ["arrowup"])

    @classmethod
    def down(cls, code: str, stack: Stack):
        return cls.key(code, ["arrowdown"])

    @classmethod
    def left(cls, code: str, stack: Stack):
        return cls.key(code, ["arrowleft"])

    @classmethod
    def right(cls, code: str, stack: Stack):
        return cls.key(code, ["arrowright"])
