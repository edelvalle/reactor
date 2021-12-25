import morphdom from 'morphdom'
import ReconnectingWebSocket from 'reconnecting-websocket'
import boost from './reactor-boost'


// Connection

class ServerConnection extends EventTarget {
    open(path = '__reactor__') {
        let protocol = location.protocol.replace("http", "ws")
        this.socket = new ReconnectingWebSocket(
            `${protocol}//${location.host}/${path}`, [],
            {
                maxEnqueuedMessages: 0,
            }
        )

        this.socket.addEventListener(
            "open",
            () => {
                console.log("WS: OPEN")
                this.dispatchEvent(new Event("open"))
            }
        )

        this.socket.addEventListener(
            "message",
            (event) => this._processMessage(event)
        )

        this.socket.addEventListener(
            "close",
            () => {
                console.log("WS: CLOSE")
                this.dispatchEvent(new Event("close"))
            }
        )
    }

    get isOpen() {
        return this.socket?.readyState == ReconnectingWebSocket.OPEN
    }

    _processMessage(event) {
        let { command, payload } = JSON.parse(event.data)
        switch (command) {
            case "render":
                var { id, diff } = payload
                console.log("<<< RENDER", id)
                document.getElementById(id)?.applyDiff(diff)
                break
            case "remove":
                var { id } = payload
                console.log("<<< REMOVE", id)
                document.getElementById(id)?.remove()
                break
            case "focus_on":
                var { selector } = payload
                console.log('<<< FOCUS-ON', `"${selector}"`)
                document.querySelector(selector)?.focus()
                break
            case "visit":
                var { url, replace } = payload
                if (replace) {
                    console.log("<< REPLACE", url)
                    boost.HistoryCache.replace(url)
                } else {
                    console.log("<< VISIT", url)
                    boost.HistoryCache.load(url)
                }
                break
            case "page":
                var { url, content } = payload
                console.log("<< PAGE", `"${url}"`)
                boost.HistoryCache.loadContent(url, content)
                break
            case "back":
                boost.HistoryCache.back()
                break
            default:
                console.error(`Unknown command "${command}"`, payload)
        }

    }

    sendJoin(name, state) {
        console.log(">>> JOIN", name)
        this._send("join", { name, state })
    }

    sendLeave(id) {
        console.log(">>> LEAVE", id)
        this._send("leave", { id })
    }

    sendUserEvent(id, command, implicit_args, explicit_args) {
        console.log(">>> USER_EVENT", id, command, explicit_args)
        this._send("user_event", { id, command, implicit_args, explicit_args })
    }

    _send(command, payload) {
        if (this.isOpen) {
            this.socket.send(JSON.stringify({ command, payload }))
        }
    }
}

let connection = new ServerConnection()

for ({ dataset } of document.querySelectorAll("meta[name=reactor-component]")) {

    let baseElement = document.createElement(dataset.extends)

    class ReactorComponent extends baseElement.constructor {

        constructor(...args) {
            super(...args)
            this._lastReceivedHtml = []
            this.joinBind = () => this.join()
            this.wentOffline = () => this.classList.add("reactor-disconnected")
        }

        connectedCallback() {
            connection.addEventListener("open", this.joinBind)
            connection.addEventListener("close", this.wentOffline)
            this.join()
        }

        disconnectedCallback() {
            connection.removeEventListener("open", this.joinBind)
            connection.removeEventListener("close", this.wentOffline)
            connection.sendLeave(this.id)
        }

        join() {
            this.classList.remove("reactor-disconnected")
            if (this.isRoot) {
                connection.sendJoin(this.dataset.name, this.dataset.state)
            }
        }

        applyDiff(diff) {
            let html = this.getHtml(diff)
            window.requestAnimationFrame(() => {
                morphdom(this, html, {
                    onBeforeNodeAdded(node) {
                        boost.boostElement(node)
                    },
                    onElUpdated(node) {
                        boost.boostElement(node)
                    },
                })
            })
        }

        getHtml(diff) {
            let fragments = []
            let cursor = 0
            for (let fragment of diff) {
                if (typeof fragment === "string") {
                    fragments.push(fragment)
                } else if (fragment < 0) {
                    cursor -= fragment
                } else {
                    fragments.push(...this._lastReceivedHtml.slice(cursor, cursor + fragment))
                    cursor += fragment
                }
            }
            this._lastReceivedHtml = fragments
            return fragments.join(" ")
        }

        /**
         * Returns true when this is a high level component and has no parent
         * component
         *
         * @returns {boolean}
         */
        get isRoot() {
            return !this.parentComponent
        }

        /**
         * Returns the high parent reactor component if any is found component
         *
         * @returns {?ReactorComponent}
         */
        get parentComponent() {
            return this.parentElement?.closest("[reactor-component]")
        }

        /**
         * Dispatches a command to this component and sends it to the backend
         * @param {String} command
         * @param {Object} args
         * @param {?HTMLFormElement} form
         */
        dispatch(command, args, formScope) {
            connection.sendUserEvent(
                this.id, command, this.serialize(formScope), args
            )
        }

        /**
         * Serialize all elements inside `element` with a [name] attribute into
         * a an array of `[element[name], element[value]]`
         * @param {HTMLElement} element
         */
        serialize(element) {
            let result = {}
            for (let el of element.querySelectorAll("[name]")) {
                // Avoid serializing data of a nested component
                if (el.closest("[reactor-component]") !== this) {
                    continue
                }

                let value = null
                switch (el.type.toLowerCase()) {
                    case "checkbox":
                    case "radio":
                        value = el.checked ? (el.value || true) : null
                        break
                    case "select-multiple":
                        value = el.selectedOptions.map(option => option.value)
                        break
                    default:
                        value = el.value
                        break
                }

                if (value !== null) {
                    let key = el.getAttribute("name")
                    let values = result[key] ?? []
                    values.push(value)
                    result[key] = values
                }
            }
            return result
        }
    }

    customElements.define(dataset.tagName, ReactorComponent, { extends: dataset.extends })

}


connection.open()
debounceTimeouts = {}

window.reactor = {
    /**
     * Forwards a user event to a component
     * @param {HTMLElement} element
     * @param {String} name
     * @param {Object} args
     */
    send(element, name, args) {
        let component = element.closest("[reactor-component]")
        if (component !== null) {
            let form = element.closest("form")
            let formScope = component.contains(form) ? form : component
            component.dispatch(name, args, formScope)
        }

    },

    /**
     * Debounce a function call
     * @param {String} delayName
     * @param {Number} delay
     * @returns
     */
    debounce(delayName, delay) {
        return (f) => {
            return (...args) => {
                clearTimeout(debounceTimeouts[delayName])
                debounceTimeouts[delayName] = setTimeout(() => f(...args), delay)
            }
        }
    }
}
