import ReconnectingWebSocket from "reconnecting-websocket";
import boost from "./reactor-boost";

// Connection

const parser = new DOMParser();

class ServerConnection extends EventTarget {
  open(path = "__reactor__") {
    let protocol = location.protocol.replace("http", "ws");
    this.socket = new ReconnectingWebSocket(
      `${protocol}//${location.host}/${path}`,
      [],
      {
        maxEnqueuedMessages: 0,
      }
    );

    this.socket.addEventListener("open", () => {
      console.log("WS: OPEN");
      this.dispatchEvent(new Event("open"));
    });

    this.socket.addEventListener("message", (event) =>
      this._processMessage(event)
    );

    this.socket.addEventListener("close", () => {
      console.log("WS: CLOSE");
      this.dispatchEvent(new Event("close"));
    });
  }

  get isOpen() {
    return this.socket?.readyState == ReconnectingWebSocket.OPEN;
  }

  _processMessage(event) {
    let { command, payload } = JSON.parse(event.data);
    switch (command) {
      case "render":
        var { id, diff } = payload;
        console.log("<<< RENDER", id);
        document.getElementById(id)?.applyDiff(diff);
        break;
      case "append":
      case "prepend":
      case "insert_after":
      case "insert_before":
      case "replace_with":
        var { id, html } = payload;
        console.log(`<<< ${command.toUpperCase()}`, id);
        html = parser.parseFromString(html, "text/html").body.firstChild;
        var element = document.getElementById(id);
        switch (command) {
          case "append":
            element?.append(html);
            break;
          case "prepend":
            element?.prepend(html);
            break;
          case "insert_after":
            element?.after(html);
            break;
          case "insert_before":
            element?.before(html);
            break;
          case "replace_with":
            element?.replaceWith(html);
            break;
        }
        break;
      case "remove":
        var { id } = payload;
        console.log("<<< REMOVE", id);
        document.getElementById(id)?.remove();
        break;
      case "focus_on":
        var { selector } = payload;
        console.log(
          "<<< FOCUS-ON",
          `"${selector}"`,
          document.querySelector(selector)
        );
        window.requestAnimationFrame(() =>
          document.querySelector(selector)?.focus()
        );
        break;
      case "scroll_into_view":
        var { id, behavior, block, inline } = payload;
        window.requestAnimationFrame(() =>
          document
            .getElementById(id)
            ?.scrollIntoView({ behavior, block, inline })
        );
        break;
      case "url_change":
        var { url } = payload;
        console.log("<< URL", payload.command, url);
        switch (payload.command) {
          case "redirect":
            boost.HistoryCache.load(url);
            break;
          case "replace":
            boost.HistoryCache.replace(url);
            break;
          case "push":
            boost.HistoryCache.push(url);
            break;
        }
        break;
      case "set_url_params":
        console.log("<< SET URL PARAMS", payload);

        // "?a=x&..." -> "a=x&..."
        let searchParams = document.location.search.slice(1);

        let currentParams = {};
        if (searchParams.length) {
          currentParams = searchParams
            .split("&") // ["a=x", ...]
            .map((x) => x.split("=")) // [["a", "x"], ...]
            .reduce(
              // {a: "x", ...}
              (acc, data) => {
                let [key, value] = data;
                acc[key] =
                  value === undefined ? undefined : decodeURIComponent(value);
                return acc;
              },
              {}
            );
        }

        let newParams = Object.entries(
          Object.assign(currentParams, payload)
        ).map((key_value) => {
          let [key, value] = key_value;
          return (
            key + (value === undefined ? "" : `=${encodeURIComponent(value)}`)
          );
        });

        let newpath = document.location.pathname;
        if (newParams.length) {
          newpath += "?" + newParams.join("&");
        }
        boost.HistoryCache.replace(newpath);
        break;

      case "back":
        boost.HistoryCache.back();
        break;
      default:
        console.error(`Unknown command "${command}"`, payload);
    }
  }

  sendJoin(name, parent_id, state) {
    this._send("join", { name, parent_id, state });
  }

  sendLeave(id) {
    console.log(">>> LEAVE", id);
    this._send("leave", { id });
  }

  sendUserEvent(id, command, implicit_args, explicit_args) {
    console.log(">>> USER_EVENT", id, command, explicit_args);
    this._send("user_event", { id, command, implicit_args, explicit_args });
  }

  _send(command, payload) {
    if (this.isOpen) {
      this.socket.send(JSON.stringify({ command, payload }));
    }
  }
}

let connection = new ServerConnection();

for ({ dataset } of document.querySelectorAll("meta[name=reactor-component]")) {
  let baseElement = document.createElement(dataset.extends);

  class ReactorComponent extends baseElement.constructor {
    constructor(...args) {
      super(...args);
      this._lastReceivedHtml = [];
      this.joinBind = () => this.join();
      this.wentOffline = () => this.classList.add("reactor-disconnected");
    }

    connectedCallback() {
      connection.addEventListener("open", this.joinBind);
      connection.addEventListener("close", this.wentOffline);
      this.join();
    }

    disconnectedCallback() {
      connection.removeEventListener("open", this.joinBind);
      connection.removeEventListener("close", this.wentOffline);
      this.leave();
    }

    join() {
      this.classList.remove("reactor-disconnected");
      connection.sendJoin(this.dataset.name, this.parentId, this.dataset.state);
    }

    leave() {
      connection.sendLeave(this.id);
    }

    applyDiff(diff) {
      window.requestAnimationFrame(() => {
        let html = this.getHtml(diff);
        boost.morph(this, html);
      });
    }

    getHtml(diff) {
      let fragments = [];
      let cursor = 0;
      for (let fragment of diff) {
        if (typeof fragment === "string") {
          fragments.push(fragment);
        } else if (fragment < 0) {
          cursor -= fragment;
        } else {
          fragments.push(
            ...this._lastReceivedHtml.slice(cursor, cursor + fragment)
          );
          cursor += fragment;
        }
      }
      this._lastReceivedHtml = fragments;
      return fragments.join(" ");
    }

    /**
     * Returns the id of the parent component
     *
     * @returns {?String}
     */
    get parentId() {
      return this.parentComponent?.id;
    }

    /**
     * Returns the high parent reactor component if any is found component
     *
     * @returns {?ReactorComponent}
     */
    get parentComponent() {
      return this.parentElement?.closest("[reactor-component]");
    }

    /**
     * Dispatches a command to this component and sends it to the backend
     * @param {String} command
     * @param {Object} args
     * @param {?HTMLFormElement} form
     */
    dispatch(command, args, formScope) {
      connection.sendUserEvent(
        this.id,
        command,
        this.serialize(formScope),
        args
      );
    }

    /**
     * Serialize all elements inside `element` with a [name] attribute into
     * a an array of `[element[name], element[value]]`
     * @param {HTMLElement} element
     */
    serialize(element) {
      let result = {};
      for (let el of element.querySelectorAll("[name]")) {
        // Avoid serializing data of a nested component
        if (el.closest("[reactor-component]") !== this) {
          continue;
        }

        let value = null;
        switch (el.type.toLowerCase()) {
          case "checkbox":
          case "radio":
            value = el.checked ? el.value || true : null;
            break;
          case "select-multiple":
            value = el.selectedOptions.map((option) => option.value);
            break;
          default:
            value = el.value;
            break;
        }

        if (value !== null) {
          let key = el.getAttribute("name");
          let values = result[key] ?? [];
          values.push(value);
          result[key] = values;
        }
      }
      return result;
    }
  }

  customElements.define(dataset.tagName, ReactorComponent, {
    extends: dataset.extends,
  });
}

connection.open();
var debounceTimeout = undefined;

window.reactor = {
  /**
   * Forwards a user event to a component
   * @param {HTMLElement} element
   * @param {String} name
   * @param {Object} args
   */
  send(element, name, args) {
    let component = element.closest("[reactor-component]");
    if (component !== null) {
      let form = element.closest("form");
      let formScope = component.contains(form) ? form : component;
      component.dispatch(name, args, formScope);
    }
  },

  /**
   * Debounce a function call
   * @param {Number} delay
   * @returns
   */
  debounce(delay) {
    return (f) => {
      return (...args) => {
        clearTimeout(debounceTimeout);
        debounceTimeout = setTimeout(() => f(...args), delay);
      };
    };
  },
};
