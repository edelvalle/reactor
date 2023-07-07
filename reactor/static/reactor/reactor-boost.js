import idiomorph from "idiomorph";

console.log(idiomorph);

function morph(oldNode, newNode) {
  newJoiners = new Set();
  Idiomorph.morph(oldNode, newNode, {
    ignoreActive: true,
    callbacks: {
      beforeNodeMorphed: function (oldNode, newNode) {
        if (
          oldNode instanceof HTMLElement &&
          newNode instanceof HTMLElement &&
          oldNode.hasAttribute("reactor-component") &&
          newNode.hasAttribute("reactor-component") &&
          oldNode.id !== newNode.id
        ) {
          oldNode.leave();
          newJoiners.add(newNode.id);
        }
      },
      afterNodeMorphed: function (oldNode, newNode) {
        if (newJoiners.has(oldNode.id)) {
          oldNode.join();
        }
      },
    },
  });
}

const BOOST_PAGES = JSON.parse(
  document.querySelector("meta[name=reactor-boost]")?.dataset.enabled || "false"
);

console.log("BOOST_PAGES", BOOST_PAGES);

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

function replaceBodyContent(withHtmlContent, scrollY = undefined) {
  let html = new DOMParser().parseFromString(withHtmlContent, "text/html");
  document.title = html.querySelector("title")?.text ?? "";
  morph(document.body, html.body);
  if (scrollY === undefined) {
    document.querySelector("[autofocus]")?.focus();
  } else {
    window.scrollTo(0, scrollY);
  }
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
    history.replaceState(
      {
        content: document.body.outerHTML,
        scrollY: window.scrollY,
      },
      document.title,
      document.location.href
    );
    let response = await fetch(path);
    let content = await response.text();
    history.pushState({}, document.title, path);
    replaceBodyContent(content);
  }

  static replace(path) {
    history.replaceState({}, document.title, path);
  }
}

window.addEventListener("popstate", (event) => {
  if (event.state?.content !== undefined) {
    replaceBodyContent(event.state.content, event.state.scrollY);
  }
  fetch(document.location.href)
    .then((response) => response.text())
    .then((content) => replaceBodyContent(content));
});

export default {
  HistoryCache: HistoryCache,
  morph: morph,
};
