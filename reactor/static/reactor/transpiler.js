


/**
 * Transpiles the reactor event DSL into JavaScript
 * @param {HTMLElement} el
 */
function transpile(el) {
    if (el.attributes === undefined) return el

    // find the attrs that need transpilation
    let replacements = []
    for (let attr of el.attributes) {
        if (attr.name.startsWith("@")) {
            console.log(attr.name, attr.value)
            replacements.push(transpileAttribute(attr))
        }
    }

    // replace the transpiled attrs
    for (let { oldName, name, code } of replacements) {
        el.attributes.removeNamedItem(oldName)
        let newAttr = document.createAttribute(name)
        newAttr.value = code
        el.attributes.setNamedItem(newAttr)
    }

    return el
}

// Attribute transpiler

let transpilerCache = {}



class Modifiers {
    /**
     * Transforms the code in the event handler into JavaScript
     *
     *  onclick="do_something"
     *  -> {command: "do_something", "args": "null"}
     *
     * onclick="do_something {argument1: 42, argument2: 'a'}"
     * -> {command: "do_something", "args": "{argument1: 42, argument2: 'a'}"}
     *
     * @param {String} code
     */
    static __reactorCode(code) {
        let splitBetweenCommandAndArguments = code.indexOf(" ")
        let name = code
        let args = "null"
        if (splitBetweenCommandAndArguments !== -1) { // has arguments
            name = code.slice(0, splitBetweenCommandAndArguments)
            args = code.slice(splitBetweenCommandAndArguments + 1)
        }
        return `reactor.send(event.target, '${name}', ${args});`
    }

    // Events

    static debounce(code, stack) {
        let name = stack.pop()
        let delay = stack.pop()
        return `reactor.debounce('${name}', ${delay})(() => {${code}})()`
    }

    static prevent(code) {
        return "event.preventDefault(); " + code
    }

    static stop(code) {
        return "event.stopPropagation(); " + code
    }

    // Key modifiers

    static ctrl(code) {
        return `if (event.ctrlKey) { ${code} }`
    }

    static alt(code) {
        return `if (event.altKey) { ${code} }`
    }

    static shift(code) {
        return `if (event.shiftKey) { ${code} }`
    }

    static meta(code) {
        return `if (event.metaKey) { ${code} }`
    }

    // Key codes

    static key(code, stack) {
        let key = stack.pop()
        return `if ((event.key + "").toLowerCase() == "${key}") { ${code} }`
    }

    static keyCode(code, stack) {
        let keyCode = stack.pop()
        return `if (event.keyCode == ${keyCode}) { ${code} }`
    }

    // Key shortcuts

    static enter(code) {
        return Modifiers.key(code, ["enter"])
    }

    static tab(code) {
        return Modifiers.key(code, ["tab"])
    }

    static delete(code) {
        return Modifiers.key(code, ["delete"])
    }

    static backspace(code) {
        return Modifiers.key(code, ["backspace"])
    }

    static esc(code) {
        return Modifiers.key(code, ["escape"])
    }

    static space(code) {
        return Modifiers.key(code, [" "])
    }

    static up(code) {
        return Modifiers.key(code, ["arrowup"])
    }

    static down(code) {
        return Modifiers.key(code, ["arrowdown"])
    }

    static left(code) {
        return Modifiers.key(code, ["arrowleft"])
    }

    static right(code) {
        return Modifiers.key(code, ["arrowright"])
    }
}


function transpileAttribute(attribute) {
    let [name, ...modifiers] = attribute.name.split(".")
    modifiers.push("__reactorCode")
    let cacheKey = `${modifiers}.${attribute.value}`

    let code = transpilerCache[cacheKey]
    console.log(">", code !== undefined)
    if (code === undefined) {
        code = attribute.value
        let stack = []
        while (modifiers.length) {
            let modifier = modifiers.pop()
            let handler = Modifiers[modifier]
            if (handler === undefined) {
                stack.push(modifiers)
                continue
            } else {
                code = handler(code, stack)
            }
        }
        transpilerCache[cacheKey] = code
    }
    return { oldName: attribute.name, name: `on${name.slice(1)}`, code }
}


export default transpile
