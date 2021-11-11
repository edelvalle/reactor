import json

from lru import LRU as LRUDict

from . import settings


def transpile(event_and_modifiers: str, command: str, kwargs: dict):
    """Translates from from the tag `on` in to JavaScript"""
    name, *modifiers = event_and_modifiers.split(".")
    cache_key = f"{modifiers}.{command}.{kwargs}"
    code = CODE_CACHE.get(cache_key)
    if code is None:
        modifiers.append("_reactor_code")
        code = command
        stack = [kwargs]
        while modifiers:
            modifier = modifiers.pop()
            handler = getattr(Modifiers, modifier, None)
            if handler:
                code = handler(code, stack)
            else:
                stack.append(modifier)

        CODE_CACHE[cache_key] = code
    return "on" + name, code


CODE_CACHE = LRUDict(settings.TRANSPILER_CACHE_SIZE)


class Modifiers:
    @staticmethod
    def _reactor_code(code, stack):
        kwargs = json.dumps(stack.pop())
        return f"reactor.send(event.target, '{code}', {kwargs})"

    @staticmethod
    def _add_curly(code, stack=None):
        return "{" + code + "}"

    # Events

    @classmethod
    def debounce(cls, code, stack):
        name = stack.pop()
        delay = stack.pop()
        code = cls._add_curly(code)
        return f"reactor.debounce('{name}', {delay})(() => {code})()"

    @staticmethod
    def prevent(code, stack):
        return "event.preventDefault(); " + code

    @staticmethod
    def stop(code, stack):
        return "event.stopPropagation(); " + code

    # Key modifiers

    @classmethod
    def ctrl(cls, code, stack):
        code = cls.add_curly(code)
        return f"if (event.ctrlKey) {code}"

    @classmethod
    def alt(cls, code, stack):
        code = cls.add_curly(code)
        return f"if (event.altKey) {code}"

    @classmethod
    def shift(cls, code, stack):
        code = cls.add_curly(code)
        return f"if (event.shiftKey) {code}"

    @classmethod
    def meta(cls, code, stack):
        code = cls.add_curly(code)
        return f"if (event.metaKey) {code}"

    # Key codes

    @classmethod
    def key(cls, code, stack):
        key = stack.pop()
        code = cls._add_curly(code)
        return f"if ((event.key + '').toLowerCase() == '{key}') {code}"

    @classmethod
    def key_code(cls, code, stack):
        keyCode = stack.pop()
        code = cls._add_curly(code)
        return f"if (event.keyCode == {keyCode}) {code}"

    # Key shortcuts
    @classmethod
    def enter(cls, code, stack):
        return cls.key(code, ["enter"])

    @classmethod
    def tab(cls, code, stack):
        return cls.key(code, ["tab"])

    @classmethod
    def delete(cls, code, stack):
        return cls.key(code, ["delete"])

    @classmethod
    def backspace(cls, code, stack):
        return cls.key(code, ["backspace"])

    @classmethod
    def esc(cls, code, stack):
        return cls.key(code, ["escape"])

    @classmethod
    def space(cls, code, stack):
        return cls.key(code, [" "])

    @classmethod
    def up(cls, code, stack):
        return cls.key(code, ["arrowup"])

    @classmethod
    def down(cls, code, stack):
        return cls.key(code, ["arrowdown"])

    @classmethod
    def left(cls, code, stack):
        return cls.key(code, ["arrowleft"])

    @classmethod
    def right(cls, code, stack):
        return cls.key(code, ["arrowright"])
