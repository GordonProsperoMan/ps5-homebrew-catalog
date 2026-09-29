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
    var gridElements = Array.prototype.slice.call(scope.querySelectorAll("[data-grid]"));
    if (!gridElements.length) return null;
    var input = scope.querySelector("[data-search]");
    var chips = Array.prototype.slice.call(scope.querySelectorAll("[data-kind]"));
    var statusSelect = scope.querySelector("[data-status-filter]");
    var formatSelect = scope.querySelector("[data-format-filter]");
    var sortSelect = scope.querySelector("[data-sort]");
    var dirButton = scope.querySelector("[data-sort-dir]");
    var sortHeads = Array.prototype.slice.call(scope.querySelectorAll("[data-sort-key]"));
    var reset = scope.querySelector("[data-reset]");
    var viewButtons = Array.prototype.slice.call(scope.querySelectorAll("[data-view-button]"));
    var counts = Array.prototype.slice.call(scope.querySelectorAll("[data-count]"));
    var empty = scope.querySelector("[data-empty]");
    var kind = "all";
    var dir = "asc";
    var searchTimer = null;

    function normalize(text) {
      return (text || "").toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f]/g, "");
    }

    // Read every item's attributes once; filtering then only compares strings.
    var grids = gridElements.map(function (element) {
      return {
        element: element,
        panel: element.getAttribute("data-view-panel"),
        sortedBy: "name:asc",  // the build emits items sorted by name
        filteredBy: null,
        shown: 0,
        items: Array.prototype.map.call(element.querySelectorAll("[data-app]"), function (el) {
          return {
            el: el,
            text: normalize(el.getAttribute("data-search-text")),
            kind: el.getAttribute("data-app-kind"),
            status: el.getAttribute("data-status"),
            format: el.getAttribute("data-format"),
            name: el.getAttribute("data-name") || "",
            titleid: el.getAttribute("data-titleid") || "",
            author: el.getAttribute("data-author") || "",
            updated: el.getAttribute("data-updated") || ""
          };
        })
      };
    });

    // Ascending comparators; a descending sort reverses them. Ties fall back to the name.
    var sorters = {
      name: function (a, b) { return a.name.localeCompare(b.name); },
      titleid: function (a, b) { return a.titleid.localeCompare(b.titleid); },
      kind: function (a, b) { return a.kind.localeCompare(b.kind) || sorters.name(a, b); },
      author: function (a, b) { return a.author.localeCompare(b.author) || sorters.name(a, b); },
      updated: function (a, b) { return a.updated.localeCompare(b.updated) || sorters.name(a, b); }
    };

    // Most recently updated first; everything else A to Z.
    function defaultDir(key) {
      return key === "updated" ? "desc" : "asc";
    }

    function sortKey() {
      return sortSelect && sorters[sortSelect.value] ? sortSelect.value : "name";
    }

    function comparator(key, direction) {
      var compare = sorters[key] || sorters.name;
      return direction === "desc" ? function (a, b) { return compare(b, a); } : compare;
    }

    function pick(select, value) {
      if (!select) return;
      var allowed = Array.prototype.some.call(select.options, function (o) { return o.value === value; });
      select.value = allowed ? value : select.options[0].value;
    }

    function view() {
      return root.getAttribute("data-view") === "list" ? "list" : "cards";
    }

    function query() {
      var next = new URLSearchParams();
      if (input && input.value.trim()) next.set("q", input.value.trim());
      if (kind !== "all") next.set("kind", kind);
      if (statusSelect && statusSelect.value !== "all") next.set("status", statusSelect.value);
      if (formatSelect && formatSelect.value !== "all") next.set("format", formatSelect.value);
      if (sortKey() !== "name") next.set("sort", sortKey());
      if (dir !== defaultDir(sortKey())) next.set("dir", dir);
      if (view() === "list") next.set("view", "list");
      return next.toString();
    }

    // Bring one grid up to date. Work happens only when the sort or filters
    // changed since that grid was last updated, so the hidden view costs nothing
    // until it is shown.
    function refresh(grid, sorting, filters) {
      if (grid.sortedBy !== sorting) {
        var parts = sorting.split(":");
        var fragment = document.createDocumentFragment();
        grid.items.sort(comparator(parts[0], parts[1])).forEach(function (item) { fragment.appendChild(item.el); });
        grid.element.appendChild(fragment);
        grid.sortedBy = sorting;
      }
      if (grid.filteredBy !== filters.key) {
        var shown = 0;
        grid.items.forEach(function (item) {
          var visible = (filters.kind === "all" || item.kind === filters.kind) &&
            (filters.status === "all" || item.status === filters.status) &&
            (filters.format === "all" || item.format === filters.format) &&
            filters.terms.every(function (term) { return item.text.indexOf(term) !== -1; });
          if (item.el.hidden === visible) item.el.hidden = !visible;
          if (visible) shown += 1;
        });
        grid.shown = shown;
        grid.filteredBy = filters.key;
      }
    }

    function apply(updateUrl) {
      var filters = {
        terms: normalize(input ? input.value : "").split(/\s+/).filter(Boolean),
        kind: kind,
        status: statusSelect ? statusSelect.value : "all",
        format: formatSelect ? formatSelect.value : "all"
      };
      filters.key = [filters.terms.join(" "), filters.kind, filters.status, filters.format].join("|");
      var key = sortKey();
      var current = view();
      var shown = 0;
      grids.forEach(function (grid) {
        if (grid.panel && grid.panel !== current) return;
        refresh(grid, key + ":" + dir, filters);
        shown = grid.shown;
      });
      if (dirButton) {
        dirButton.textContent = dir === "asc" ? "↑" : "↓";
        dirButton.setAttribute("aria-label", dir === "asc" ? "Ascending; switch to descending" : "Descending; switch to ascending");
        dirButton.setAttribute("title", dir === "asc" ? "Ascending" : "Descending");
      }
      sortHeads.forEach(function (head) {
        var active = head.getAttribute("data-sort-key") === key;
        var label = "Sort by " + head.textContent.trim().toLowerCase();
        head.setAttribute("data-active", active ? dir : "");
        head.setAttribute("aria-label", active ? label + ", currently " + (dir === "asc" ? "ascending" : "descending") : label);
      });
      chips.forEach(function (chip) {
        chip.setAttribute("aria-pressed", String(chip.getAttribute("data-kind") === kind));
      });
      viewButtons.forEach(function (button) {
        button.setAttribute("aria-pressed", String(button.getAttribute("data-view-button") === current));
      });
      counts.forEach(function (count) {
        var template = count.getAttribute("data-count") || "{n}";
        count.textContent = template.replace("{n}", shown).replace("{s}", shown === 1 ? "" : "s");
      });
      if (empty) empty.hidden = shown !== 0;
      var q = query();
      if (reset) reset.hidden = q.replace(/(^|&)(sort|dir|view)=[^&]*/g, "") === "";
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
      var requested = params.get("dir");
      dir = requested === "asc" || requested === "desc" ? requested : defaultDir(sortKey());
      setView(params.get("view") === "list" ? "list" : "cards", false);
    }

    function sortBy(key, direction) {
      pick(sortSelect, key);
      dir = direction || defaultDir(sortKey());
      applyNow();
    }

    function setView(next, updateUrl) {
      if (next === "list") root.setAttribute("data-view", "list");
      else root.removeAttribute("data-view");
      apply(updateUrl);
    }

    function applyNow() {
      window.clearTimeout(searchTimer);
      apply(true);
    }

    // Typing waits for a short pause so a burst of keystrokes filters once.
    if (input) input.addEventListener("input", function () {
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(function () { apply(true); }, 150);
    });
    [statusSelect, formatSelect].forEach(function (select) {
      if (select) select.addEventListener("change", applyNow);
    });
    if (sortSelect) sortSelect.addEventListener("change", function () { sortBy(sortSelect.value); });
    if (dirButton) dirButton.addEventListener("click", function () {
      dir = dir === "asc" ? "desc" : "asc";
      applyNow();
    });
    // List headers: a new column sorts in its natural order, the active one reverses.
    sortHeads.forEach(function (head) {
      head.addEventListener("click", function () {
        var key = head.getAttribute("data-sort-key");
        if (key === sortKey()) sortBy(key, dir === "asc" ? "desc" : "asc");
        else sortBy(key);
      });
    });
    chips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        kind = chip.getAttribute("data-kind");
        applyNow();
      });
    });
    viewButtons.forEach(function (button) {
      button.addEventListener("click", function () {
        window.clearTimeout(searchTimer);
        setView(button.getAttribute("data-view-button"), true);
      });
    });
    if (reset) reset.addEventListener("click", function () {
      kind = "all";
      if (input) input.value = "";
      pick(statusSelect, "all");
      pick(formatSelect, "all");
      applyNow();
    });

    load(window.location.search);
    return { input: input, apply: applyNow, load: load };
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
