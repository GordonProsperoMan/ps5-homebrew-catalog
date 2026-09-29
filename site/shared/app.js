// Progressive enhancement only: every page is complete static HTML and works
// without JavaScript. This script adds, on top of that:
//   - search, filters, sorting and a Cards/List switch on the catalog page,
//     all kept in the URL (?q=…&kind=…&status=…&format=…&sort=…&view=list);
//   - in-page navigation: opening an app swaps in its static page without a
//     reload, and going back restores the catalog with filters and scroll intact;
//   - copy buttons and the card tilt effect.
(function () {
  "use strict";
  var root = document.documentElement;
  root.classList.add("js");
  try {
    if (new URLSearchParams(window.location.search).get("view") === "list") root.setAttribute("data-view", "list");
  } catch (error) { /* old browsers keep the card view */ }
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var store = null; // controller of the catalog on screen, if any

  document.addEventListener("DOMContentLoaded", function () {
    enhance(document);
    setupNavigation();
    document.addEventListener("keydown", onKeyDown);
  });

  function enhance(scope) {
    setupCopy(scope);
    setupTilt(scope);
    store = setupStore(scope);
  }

  function each(scope, selector, fn) {
    Array.prototype.forEach.call(scope.querySelectorAll(selector), fn);
  }

  function setupCopy(scope) {
    each(scope, "[data-copy]", function (button) {
      button.addEventListener("click", function () {
        if (!navigator.clipboard || !navigator.clipboard.writeText) return;
        navigator.clipboard.writeText(button.getAttribute("data-copy")).then(function () {
          var original = button.textContent;
          button.textContent = button.getAttribute("data-copied") || "Copied";
          window.setTimeout(function () { button.textContent = original; }, 1400);
        }, function () {});
      });
    });
  }

  // Pointer-driven tilt and sheen: sets --rx, --ry, --mx, --my on [data-tilt].
  function setupTilt(scope) {
    if (reduceMotion) return;
    each(scope, "[data-tilt]", function (el) {
      var strength = parseFloat(el.getAttribute("data-tilt")) || 10;
      el.addEventListener("pointermove", function (event) {
        var box = el.getBoundingClientRect();
        var x = (event.clientX - box.left) / box.width;
        var y = (event.clientY - box.top) / box.height;
        el.style.setProperty("--mx", (x * 100).toFixed(1) + "%");
        el.style.setProperty("--my", (y * 100).toFixed(1) + "%");
        el.style.setProperty("--rx", ((0.5 - y) * strength).toFixed(2) + "deg");
        el.style.setProperty("--ry", ((x - 0.5) * strength).toFixed(2) + "deg");
      });
      el.addEventListener("pointerleave", function () {
        ["--mx", "--my", "--rx", "--ry"].forEach(function (name) { el.style.removeProperty(name); });
      });
    });
  }

  // ── Catalog: search, filters, sorting and view, shared by both views ──

  function setupStore(scope) {
    var grids = Array.prototype.slice.call(scope.querySelectorAll("[data-grid]"));
    if (!grids.length) return null;
    var input = scope.querySelector("[data-search]");
    var chips = Array.prototype.slice.call(scope.querySelectorAll("[data-kind]"));
    var statusSelect = scope.querySelector("[data-status-filter]");
    var formatSelect = scope.querySelector("[data-format-filter]");
    var sortSelect = scope.querySelector("[data-sort]");
    var reset = scope.querySelector("[data-reset]");
    var viewButtons = Array.prototype.slice.call(scope.querySelectorAll("[data-view-button]"));
    var counts = Array.prototype.slice.call(scope.querySelectorAll("[data-count]"));
    var empty = scope.querySelector("[data-empty]");
    var kind = "all";

    function pick(select, value) {
      if (!select) return;
      var allowed = Array.prototype.some.call(select.options, function (o) { return o.value === value; });
      select.value = allowed ? value : select.options[0].value;
    }

    function normalize(text) {
      return (text || "").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "");
    }

    var sorters = {
      name: function (a, b) { return a.getAttribute("data-name").localeCompare(b.getAttribute("data-name")); },
      titleid: function (a, b) { return a.getAttribute("data-titleid").localeCompare(b.getAttribute("data-titleid")); },
      kind: function (a, b) {
        return a.getAttribute("data-app-kind").localeCompare(b.getAttribute("data-app-kind")) || sorters.name(a, b);
      },
      updated: function (a, b) {
        return (b.getAttribute("data-updated") || "").localeCompare(a.getAttribute("data-updated") || "") || sorters.name(a, b);
      }
    };

    function view() {
      return root.getAttribute("data-view") === "list" ? "list" : "cards";
    }

    function query() {
      var next = new URLSearchParams();
      if (input && input.value.trim()) next.set("q", input.value.trim());
      if (kind !== "all") next.set("kind", kind);
      if (statusSelect && statusSelect.value !== "all") next.set("status", statusSelect.value);
      if (formatSelect && formatSelect.value !== "all") next.set("format", formatSelect.value);
      if (sortSelect && sortSelect.value !== "name") next.set("sort", sortSelect.value);
      if (view() === "list") next.set("view", "list");
      return next.toString();
    }

    function apply(updateUrl) {
      var terms = normalize(input ? input.value : "").split(/\s+/).filter(Boolean);
      var status = statusSelect ? statusSelect.value : "all";
      var format = formatSelect ? formatSelect.value : "all";
      var sorter = sorters[sortSelect ? sortSelect.value : "name"] || sorters.name;
      var shown = 0;
      grids.forEach(function (grid, index) {
        var items = Array.prototype.slice.call(grid.querySelectorAll("[data-app]"));
        items.sort(sorter).forEach(function (item) {
          grid.appendChild(item);
          var text = normalize(item.getAttribute("data-search-text"));
          var visible = (kind === "all" || item.getAttribute("data-app-kind") === kind) &&
            (status === "all" || item.getAttribute("data-status") === status) &&
            (format === "all" || item.getAttribute("data-format") === format) &&
            terms.every(function (term) { return text.indexOf(term) !== -1; });
          item.hidden = !visible;
          if (visible && index === 0) shown += 1;
        });
      });
      chips.forEach(function (chip) {
        chip.setAttribute("aria-pressed", String(chip.getAttribute("data-kind") === kind));
      });
      viewButtons.forEach(function (button) {
        button.setAttribute("aria-pressed", String(button.getAttribute("data-view-button") === view()));
      });
      counts.forEach(function (count) {
        var template = count.getAttribute("data-count") || "{n}";
        count.textContent = template.replace("{n}", shown).replace("{s}", shown === 1 ? "" : "s");
      });
      if (empty) empty.hidden = shown !== 0;
      var q = query();
      if (reset) reset.hidden = q.replace(/(^|&)(sort|view)=[^&]*/g, "") === "";
      if (updateUrl) {
        window.history.replaceState(window.history.state, "", window.location.pathname + (q ? "?" + q : "") + window.location.hash);
      }
    }

    // Read filters and view from a query string (initial load, back/forward, header links).
    function load(search) {
      var params = new URLSearchParams(search);
      kind = params.get("kind") || "all";
      if (!chips.some(function (c) { return c.getAttribute("data-kind") === kind; })) kind = "all";
      if (input) input.value = params.get("q") || "";
      pick(statusSelect, params.get("status") || "all");
      pick(formatSelect, params.get("format") || "all");
      pick(sortSelect, params.get("sort") || "name");
      setView(params.get("view") === "list" ? "list" : "cards", false);
    }

    function setView(next, updateUrl) {
      if (next === "list") root.setAttribute("data-view", "list");
      else root.removeAttribute("data-view");
      apply(updateUrl);
    }

    if (input) input.addEventListener("input", function () { apply(true); });
    [statusSelect, formatSelect, sortSelect].forEach(function (select) {
      if (select) select.addEventListener("change", function () { apply(true); });
    });
    chips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        kind = chip.getAttribute("data-kind");
        apply(true);
      });
    });
    viewButtons.forEach(function (button) {
      button.addEventListener("click", function () { setView(button.getAttribute("data-view-button"), true); });
    });
    if (reset) reset.addEventListener("click", function () {
      kind = "all";
      if (input) input.value = "";
      pick(statusSelect, "all");
      pick(formatSelect, "all");
      apply(true);
    });

    load(window.location.search);
    return { input: input, apply: apply, load: load };
  }

  function onKeyDown(event) {
    var input = store && store.input;
    if (!input || !document.body.contains(input)) return;
    var typing = event.target && /^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName);
    if (event.key === "/" && !typing) {
      event.preventDefault();
      input.focus();
    } else if (event.key === "Escape" && event.target === input) {
      input.value = "";
      store.apply(true);
    } else if (event.key === "Enter" && event.target === input) {
      input.blur();
    }
  }

  // ── In-page navigation between the catalog and app pages ──

  function setupNavigation() {
    var main = document.getElementById("main");
    var base = document.body.getAttribute("data-base");
    if (!main || !base || !window.history.pushState || !window.fetch || !window.DOMParser) return;

    var pages = {};      // app page path -> {html, title, bodyClass}
    var home = null;     // the catalog's live DOM and state while an app page is shown
    var current = window.location.pathname;
    var lastLink = null;
    var ticket = 0;
    window.history.replaceState({ nav: true }, "", window.location.href);
    if ("scrollRestoration" in window.history) window.history.scrollRestoration = "manual";

    function isHome(path) { return path === base; }
    function isApp(path) { return path.indexOf(base + "app/") === 0; }

    document.addEventListener("click", function (event) {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      var link = event.target.closest ? event.target.closest("a[href]") : null;
      if (!link || link.target || link.hasAttribute("download")) return;
      var url = new URL(link.href, window.location.href);
      if (url.origin !== window.location.origin || !(isHome(url.pathname) || isApp(url.pathname))) return;
      if (url.pathname === window.location.pathname && url.search === window.location.search && url.hash) return;
      event.preventDefault();
      if (isApp(url.pathname)) lastLink = link;
      go(url, "push");
    });

    window.addEventListener("popstate", function () {
      go(new URL(window.location.href), "pop");
    });

    function show(content, title, bodyClass) {
      main.textContent = "";
      main.appendChild(content);
      document.title = title;
      document.body.className = bodyClass;
    }

    function detachHome() {
      // Read the scroll position first: detaching the catalog shrinks the page to nothing.
      var scroll = window.scrollY;
      var fragment = document.createDocumentFragment();
      while (main.firstChild) fragment.appendChild(main.firstChild);
      home = { fragment: fragment, title: document.title, bodyClass: document.body.className,
               scroll: scroll, search: window.location.search, store: store, link: lastLink };
    }

    function focusHeading() {
      var heading = main.querySelector("h1");
      if (!heading) return;
      heading.setAttribute("tabindex", "-1");
      heading.focus({ preventScroll: true });
    }

    function scrollToHash(url) {
      var target = url.hash && document.getElementById(decodeURIComponent(url.hash.slice(1)));
      if (target) target.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
      return Boolean(target);
    }

    function fetchPage(path) {
      if (pages[path]) return Promise.resolve(pages[path]);
      return window.fetch(path, { credentials: "same-origin" }).then(function (response) {
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.text();
      }).then(function (html) {
        var doc = new DOMParser().parseFromString(html, "text/html");
        var newMain = doc.getElementById("main");
        if (!newMain) throw new Error("page has no main element");
        var page = { html: newMain.innerHTML, title: doc.title, bodyClass: doc.body.className };
        if (isApp(path)) pages[path] = page;
        return page;
      });
    }

    function go(url, mode) {
      var mine = ++ticket;

      // Catalog to catalog, e.g. the header's "List" link: just apply the URL.
      if (isHome(url.pathname) && isHome(current)) {
        if (store) store.load(url.search);
        if (mode === "push") {
          window.history.replaceState({ nav: true }, "", url.pathname + url.search + url.hash);
          scrollToHash(url);
        }
        return;
      }

      // Back to the catalog we left: reattach it as it was.
      if (isHome(url.pathname) && home) {
        var saved = home;
        home = null;
        show(saved.fragment, saved.title, saved.bodyClass);
        store = saved.store;
        current = url.pathname;
        if (mode === "push") {
          window.history.pushState({ nav: true }, "", url.pathname + (url.search || saved.search) + url.hash);
          if (url.search && store) store.load(url.search);
        } else if (store) {
          store.load(url.search);
        }
        if (!(mode === "push" && scrollToHash(url))) window.scrollTo(0, saved.scroll);
        if (saved.link && document.body.contains(saved.link)) saved.link.focus({ preventScroll: true });
        return;
      }

      // Anything else: fetch the static page and swap its content in.
      var leavingHome = isHome(current);
      fetchPage(url.pathname).then(function (page) {
        if (mine !== ticket) return;
        if (leavingHome) detachHome();
        var template = document.createElement("template");
        template.innerHTML = page.html;
        show(template.content, page.title, page.bodyClass);
        current = url.pathname;
        if (mode === "push") window.history.pushState({ nav: true }, "", url.pathname + url.search + url.hash);
        enhance(main);
        if (!scrollToHash(url)) window.scrollTo(0, 0);
        focusHeading();
      }).catch(function () {
        window.location.assign(url.href);
      });
    }
  }
})();
