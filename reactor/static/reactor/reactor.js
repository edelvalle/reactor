import ReconnectingWebSocket from "reconnecting-websocket";
import boost from "./reactor-boost";

// Connection

const parser = new DOMParser();

class ServerConnection {
  constructor() {
    this.components = {};
  }

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
      this.sendQueryString();
      this.joinAllComponents();
    });

    this.socket.addEventListener("message", (event) =>
      this._processMessage(event)
    );

    this.socket.addEventListener("close", () => {
      console.log("WS: CLOSE");
      this.components = {};
      document
        .querySelectorAll("[reactor-component]")
        .forEach((element) => element.classList.add("reactor-disconnected"));
    });

    boost.navEvent.addEventListener("newLocation", () => {
      this.sendQueryString();
    });

    boost.navEvent.addEventListener("newContent", () => {
      let registeredIds = new Set(Object.keys(this.components));
      for (let element of document.querySelectorAll("[reactor-component]")) {
        if (!registeredIds.delete(element.id)) {
          let component = new ReactorComponent(element.id);
          this.components[element.id] = component;
          component.join(true);
        }
      }
      for (let id of registeredIds.keys()) {
        delete this.components[id];
        this.sendLeave(id);
      }
    });
  }

  get isOpen() {
    return this.socket?.readyState == ReconnectingWebSocket.OPEN;
  }

  joinAllComponents() {
    this.components = {};
    document.querySelectorAll("[reactor-component]").forEach((el) => {
      el.classList.remove("reactor-disconnected");
      let component = new ReactorComponent(el.id);
      this.components[el.id] = component;
      component.join();
    });
  }

  _processMessage(event) {
    let { command, payload } = JSON.parse(event.data);
    switch (command) {
      case "render":
        var { id, diff } = payload;
        console.log("<<< RENDER", id);
        this.components[id]?.applyDiff(diff);
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
        if (element) {
          switch (command) {
            case "append":
              element.append(html);
              break;
            case "prepend":
              element.prepend(html);
              break;
            case "insert_after":
              element.after(html);
              break;
            case "insert_before":
              element.before(html);
              break;
            case "replace_with":
              boost.morph(element, html);
              break;
          }
        }
        boost.navEvent.sendNewContent();
        break;
      case "remove":
        var { id } = payload;
        console.log("<<< REMOVE", id);
        document.getElementById(id)?.remove();
        boost.navEvent.sendNewContent();
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

      case "set_query_string":
        var { qs } = payload;
        qs = qs.length ? `?${qs}` : "";
        console.log("<< SET URL PARAMS", qs);
        boost.HistoryCache.replace(document.location.pathname + qs);
        break;

      case "back":
        boost.HistoryCache.back();
        break;
      default:
        console.error(`Unknown command "${command}"`, payload);
    }
  }

  sendQueryString() {
    // "?a=x&..." -> "a=x&..."
    let qs = document.location.search.slice(1);
    console.log("QS", qs);
    this._send("query_string", { qs });
  }

  sendJoin(name, component_id, state, children) {
    console.log(">>> JOIN", name, component_id);
    this._send("join", { name, state, children });
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

class ReactorComponent {
  /**
   * Returns the id of the parent component
   *
   * @param {HTMLElement} el
   */
  constructor(id) {
    this.id = id;
    this.lastReceivedHtml = [];
  }

  getElemenet() {
    return document.getElementById(this.id);
  }

  applyDiff(diff) {
    window.requestAnimationFrame(() => {
      let el = this.getElemenet();
      if (el) {
        let html = this.getHtml(diff);
        boost.morph(el, html);
        boost.navEvent.sendNewContent();
      }
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
          ...this.lastReceivedHtml.slice(cursor, cursor + fragment)
        );
        cursor += fragment;
      }
    }
    this.lastReceivedHtml = fragments;
    return fragments.join(" ");
  }

  get parent() {
    return this.getElemenet()?.parentElement?.closest("[reactor-component]");
  }

  join(force = false) {
    if (force || !this.parent) {
      let element = this.getElemenet();
      if (element) {
        let children = Array.from(
          element.querySelectorAll("[reactor-component]")
        ).reduce((children, el) => {
          children[el.id] = [el.dataset.name, el.dataset.state];
          return children;
        }, {});

        connection.sendJoin(
          element.dataset.name,
          element.id,
          element.dataset.state,
          children
        );
      }
    }
  }

  /**
   * Dispatches a command to this component and sends it to the backend
   * @param {String} command
   * @param {Object} args
   * @param {?HTMLFormElement} form
   */
  dispatch(command, args, formScope) {
    connection.sendUserEvent(this.id, command, this.serialize(formScope), args);
  }

  /**
   * Serialize all elements inside `element` with a [name] attribute into
   * a an array of `[element[name], element[value]]`
   * @param {HTMLElement} element
   */
  serialize(element) {
    let result = {};
    let thisElement = this.getElemenet();
    for (let el of element.querySelectorAll("[name]")) {
      // Avoid serializing data of a nested component
      if (el.closest("[reactor-component]") !== thisElement) {
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
    let component_el = element.closest("[reactor-component]");
    let component = connection.components[component_el.id];
    if (component_el !== null && component !== undefined) {
      let form = element.closest("form");
      let formScope = component_el.contains(form) ? form : component_el;
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
