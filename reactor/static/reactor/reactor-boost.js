const BOOST_PAGES = JSON.parse(
  document.querySelector("meta[name=reactor-boost]")?.dataset.enabled || "false"
);
console.log("BOOST_PAGES", BOOST_PAGES);

function boostAllLinks() {
  if (BOOST_PAGES) {
    for (let link of document.querySelectorAll("a[href]")) {
      boostElement(link);
    }
  }
}

/**
 * Intercepts a clicks on links and loads them from cache and then network
 * @param {HTMLElement} element
 */
function boostElement(element) {
  if (BOOST_PAGES) {
    if (
      element.tagName?.toLowerCase() === "a" &&
      element.hasAttribute("href") &&
      !(
        element.boosted ||
        element.hasAttribute("onclick") ||
        element.hasAttribute("target") ||
        element.hasAttribute(":no-boost")
      )
    ) {
      element.boosted = true;
      element.addEventListener("click", _load);
    }
  }
}

/**
 * Event handler for links
 * @param {MouseEvent} event
 */
function _load(event) {
  event.preventDefault();
  let url =
    event.target.tagName?.toLowerCase === "a"
      ? event.target.href
      : event.target.closest("a").href;
  HistoryCache.load(url);
}

function replaceBodyContent(withHtmlContent, options) {
  console.log("replaceBodyContent", options);
  let html = document.createElement("html");
  html.innerHTML = withHtmlContent;
  window.requestAnimationFrame(() => {
    if (options?.beforeReplace) options.beforeReplace(html);
    document.body = html.querySelector("body");
    boostAllLinks();
    if (options?.afterReplace) options.afterReplace(html);
    document.querySelector("[autofocus]")?.focus();
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
  /**  @type {Array<{url: String, content: String, title: String, scroll: Number}>} */
  static maxSize = 10;
  static cache = [];
  static currentPath = window.location.pathname + window.location.search;

  static async load(url) {
    if (BOOST_PAGES) {
      this._saveCurrentPage();
      console.log(url);
      if (hasSameOriginAsDocument(url)) {
        this.push(url);
        await this.restoreFromCurrentPath();
      } else {
        location.assign(url);
      }
    } else {
      location.assign(url);
    }
  }

  static async restoreFromCurrentPath() {
    this._saveCurrentPage();
    let path = window.location.pathname + window.location.search;
    console.log("Restoring Page:", path);
    let page = this._get(path);
    if (page) {
      replaceBodyContent(page.content, {
        beforeReplace() {
          document.title = page.title;
        },
        afterReplace() {
          window.scrollTo(0, page.scroll);
        },
      });
      console.log("currentPath", path);
      this.currentPath = path;
    }

    // I don't care if the page is restored or came from the network
    // This will pull the page from the server just in case of any change

    let response = await fetch(window.location.href);
    let content = await response.text();
    this.replace(response.url);
    replaceBodyContent(content, {
      beforeReplace(html) {
        document.title = html.querySelector("title")?.text ?? "";
      },
      afterReplace() {
        HistoryCache._saveCurrentPage();
      },
    });
  }

  static back() {
    window.history.back();
  }

  static push(path) {
    history.pushState({}, document.title, path);
    this.currentPath = path;
  }

  static replace(path) {
    history.replaceState({}, document.title, path);
    this.currentPath = path;
  }

  static _saveCurrentPage() {
    console.log("Saving page:", this.currentPath);

    // Remove path from the history cache if is already existed
    this.cache = this.cache.filter(({ url }) => url != this.currentPath);

    // Put the new entry in the cache
    this.cache.push({
      url: this.currentPath,
      content: document.body.outerHTML,
      title: document.title,
      scroll: window.scrollY,
    });

    // Keep the history at a reasonable size
    if (this.cache.length > this.maxSize) {
      let page = this.cache.shift();
      console.log("Evicted:", page.url);
    }

    console.log(
      "Currently cached:",
      this.cache.map(({ url }) => url)
    );
  }

  static _get(path) {
    return this.cache.find((page) => page.url == path);
  }
}

window.addEventListener("popstate", (event) => {
  HistoryCache.restoreFromCurrentPath();
});

window.addEventListener("load", () => {
  boostAllLinks();
});

export default {
  boostElement,
  HistoryCache: HistoryCache,
};
