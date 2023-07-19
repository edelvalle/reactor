import _load from "idiomorph";

function morph(oldNode, newNode) {
  Idiomorph.morph(oldNode, newNode);
}

const BOOST_PAGES = JSON.parse(
  document.querySelector("meta[name=reactor-boost]")?.dataset.enabled || "false"
);

console.log("BOOST_PAGES", BOOST_PAGES);

class NavEvents extends EventTarget {
  sendNewLocation() {
    console.log("LOAD", document.location.href);
    this.dispatchEvent(new Event("newLocation"));
  }

  sendNewContent() {
    this.dispatchEvent(new Event("newContent"));
  }
}

let navEvent = new NavEvents();

if (BOOST_PAGES) {
  document.addEventListener("click", (e) => {
    let link = e.target;
    link = link.tagName.toLowerCase() !== "a" ? link.closest("a") : link;
    if (
      link &&
      link.href &&
      (!link.target || link.target === "_self") &&
      link.origin == document.location.origin &&
      e.button === 0 && // left click only
      !e.metaKey && // open in new tab (mac)
      !e.ctrlKey && // open in new tab (win & linux)
      !e.altKey && // download
      !e.shiftKey
    ) {
      e.preventDefault();
      HistoryCache.load(link.href);
    }
  });
}

function replaceBodyContent(newBody, scrollY = undefined) {
  window.requestAnimationFrame(() => {
    morph(document.body, newBody);
    if (scrollY === undefined) {
      document.querySelector("[autofocus]")?.focus();
    } else {
      window.scrollTo(0, scrollY);
    }
    navEvent.sendNewContent();
  });
}

function hasSameOriginAsDocument(url) {
  if (url.startsWith("http://") || url.startsWith("https://")) {
    return new URL(url).origin === document.location.origin;
  } else {
    return true;
  }
}

class HistoryCache {
  static async load(url) {
    if (BOOST_PAGES) {
      // this._saveCurrentPage();
      if (hasSameOriginAsDocument(url)) {
        this.push(url);
      } else {
        document.location.assign(url);
      }
    } else {
      document.location.assign(url);
    }
  }

  static back() {
    window.history.back();
  }

  static async push(path) {
    if (document.body == null) debugger;
    history.replaceState(
      {
        content: document.body.outerHTML,
        scrollY: window.scrollY,
      },
      document.title,
      document.location.href
    );
    history.pushState({}, document.title, path);
    this.replaceContentFromUrl(path);
  }

  static async replaceContentFromUrl(url) {
    navEvent.sendNewLocation();
    let response = await fetch(url);
    let content = await response.text();
    let doc = new DOMParser().parseFromString(content, "text/html");
    document.title = doc.querySelector("title")?.text ?? "";
    replaceBodyContent(doc.body);
  }

  static replace(path) {
    history.replaceState({}, document.title, path);
  }
}

window.addEventListener("popstate", (event) => {
  navEvent.sendNewLocation();
  if (event.state?.content !== undefined) {
    replaceBodyContent(event.state.content, event.state.scrollY);
  }
  HistoryCache.replaceContentFromUrl(document.location.href);
});

export default {
  HistoryCache: HistoryCache,
  morph: morph,
  navEvent: navEvent,
};
