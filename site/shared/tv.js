/* TV mode: the catalog as a 10-foot interface, driven by the D-pad.
 *
 * Inspired by tv4play by ps5-payload-dev (https://github.com/ps5-payload-dev/tv4play),
 * whose README documents how the PS5 browser presents the controller: the
 * D-pad as the arrow keys, Cross as Enter, Circle as Escape, Triangle as F1 and
 * Square as F2, with the television remote's HDMI-CEC keys arriving the same
 * way. Other browsers get the same controls from a connected gamepad through
 * the Gamepad API (a DualSense over USB or Bluetooth, for example). The data
 * comes from the JSON block the build embeds in the page; everything is drawn
 * with DOM APIs, so no metadata is ever parsed as HTML. The state (section,
 * sort, open app) lives in the URL hash, so a reload lands on the same screen.
 */
(function () {
  "use strict";

  var KEY = {
    LEFT: 37, UP: 38, RIGHT: 39, DOWN: 40,
    CROSS: 13, CIRCLE: 27, BACKSPACE: 8, TRIANGLE: 112, SQUARE: 113,
    PAGE_UP: 33, PAGE_DOWN: 34,
    GREEN: 154, CHAN_UP: 157, CHAN_DOWN: 158, NEXT: 176, PREV: 177, TOP_MENU: 131
  };
  var SORTS = [["name", "Name"], ["updated", "Recently updated"], ["author", "Developer"]];
  var HEADINGS = { all: "All", app: "Apps", game: "Games", tool: "Tools", soon: "Coming soon" };
  var REPEAT_MS = 110;

  var apps = [];
  var view = [];
  var state = { kind: "all", sort: "name", zone: "grid", index: 0, rail: 0, detail: -1 };
  var el = {};
  var railItems = [];
  var lastKeyAt = 0;

  function $(id) { return document.getElementById(id); }

  function make(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  }

  /* State in the URL hash */

  function readHash() {
    var params = new URLSearchParams(location.hash.slice(1));
    if (HEADINGS[params.get("kind")]) state.kind = params.get("kind");
    if (SORTS.some(function (s) { return s[0] === params.get("sort"); })) state.sort = params.get("sort");
    return params.get("app");
  }

  function writeHash() {
    var params = new URLSearchParams();
    if (state.kind !== "all") params.set("kind", state.kind);
    if (state.sort !== "name") params.set("sort", state.sort);
    if (state.detail >= 0 && view[state.detail]) params.set("app", view[state.detail].titleid);
    var hash = params.toString();
    history.replaceState(null, "", hash ? "#" + hash : location.pathname + location.search);
  }

  /* The list */

  function compare(a, b) {
    if (state.sort === "updated") return (b.updated_iso || "").localeCompare(a.updated_iso || "") || a.sort_name.localeCompare(b.sort_name);
    if (state.sort === "author") return a.author.toLowerCase().localeCompare(b.author.toLowerCase()) || a.sort_name.localeCompare(b.sort_name);
    return a.sort_name.localeCompare(b.sort_name) || a.titleid.localeCompare(b.titleid);
  }

  function select() {
    view = apps.filter(function (app) {
      if (state.kind === "all") return true;
      if (state.kind === "soon") return app.soon;
      return app.kind === state.kind && !app.soon;
    }).sort(compare);
  }

  /* Each tile is built once and reused, so switching sections doesn't reload or re-decode icons. */
  function tile(app, position) {
    if (app.node) {
      app.node.dataset.index = String(position);
      return app.node;
    }
    var item = make("button", "tv-tile" + (app.soon ? " tv-tile--soon" : ""));
    item.type = "button";
    item.tabIndex = -1;
    item.setAttribute("role", "listitem");
    item.dataset.index = String(position);
    var art = make("span", "tv-tile__art");
    var img = make("img");
    img.src = app.icon;
    img.alt = "";
    img.loading = position < 20 ? "eager" : "lazy";
    img.decoding = "async";
    art.appendChild(img);
    art.appendChild(make("span", "tv-tile__badge" + (app.soon ? " tv-tile__badge--soon" : ""), app.soon ? "Soon" : app.kind_label));
    item.appendChild(art);
    item.appendChild(make("p", "tv-tile__name", app.name));
    item.appendChild(make("p", "tv-tile__meta", app.soon ? app.author : app.author + " · v" + app.version));
    app.node = item;
    return item;
  }

  function renderGrid() {
    select();
    el.grid.textContent = "";
    var fragment = document.createDocumentFragment();
    view.forEach(function (app, i) { fragment.appendChild(tile(app, i)); });
    el.grid.appendChild(fragment);
    el.empty.hidden = view.length > 0;
    el.heading.textContent = HEADINGS[state.kind];
    var sortLabel = SORTS.filter(function (s) { return s[0] === state.sort; })[0][1];
    el.sort.textContent = sortLabel;
    el.status.textContent = view.length + (view.length === 1 ? " app" : " apps") + " · sorted by " + sortLabel.toLowerCase();
    railItems.forEach(function (item) { item.classList.toggle("is-current", item.dataset.kind === state.kind); });
    state.index = Math.min(state.index, Math.max(view.length - 1, 0));
  }

  function columns() {
    var tiles = el.grid.children;
    if (tiles.length < 2) return 1;
    var top = tiles[0].offsetTop;
    for (var i = 1; i < tiles.length; i++) if (tiles[i].offsetTop !== top) return i;
    return tiles.length;
  }

  /* Focus */

  function setFocus(zone, index) {
    var old = document.querySelector(".is-focused");
    if (old) old.classList.remove("is-focused");
    state.zone = zone;
    var target;
    if (zone === "rail") {
      state.rail = Math.max(0, Math.min(index, railItems.length - 1));
      target = railItems[state.rail];
      el.crossHint.textContent = target.dataset.action === "sort" ? "Change sort" : target.dataset.action === "exit" ? "Exit" : "Browse";
    } else {
      if (!view.length) return setFocus("rail", state.rail);
      state.index = Math.max(0, Math.min(index, view.length - 1));
      target = el.grid.children[state.index];
      el.crossHint.textContent = "Open";
      reveal(target);
    }
    target.classList.add("is-focused");
    target.focus({ preventScroll: true });
  }

  function reveal(node) {
    var box = el.main.getBoundingClientRect();
    var rect = node.getBoundingClientRect();
    var margin = box.height * 0.12;
    if (state.index < columns()) el.main.scrollTop = 0;
    else if (rect.top < box.top + margin) el.main.scrollTop -= box.top + margin - rect.top;
    else if (rect.bottom > box.bottom - margin) el.main.scrollTop += rect.bottom - (box.bottom - margin);
  }

  /* Sections and sort */

  function showKind(kind) {
    if (kind === state.kind) return;
    state.kind = kind;
    state.index = 0;
    renderGrid();
    el.main.scrollTop = 0;
    writeHash();
  }

  function cycleSort() {
    var i = SORTS.map(function (s) { return s[0]; }).indexOf(state.sort);
    state.sort = SORTS[(i + 1) % SORTS.length][0];
    var current = view[state.index] && view[state.index].titleid;
    renderGrid();
    var again = view.map(function (a) { return a.titleid; }).indexOf(current);
    state.index = again < 0 ? 0 : again;
    writeHash();
    setFocus(state.zone, state.zone === "rail" ? state.rail : state.index);
  }

  /* Detail */

  function attr(list, label, value) {
    if (!value) return;
    var row = make("div");
    row.appendChild(make("dt", "", label));
    row.appendChild(make("dd", "", value));
    list.appendChild(row);
  }

  function openDetail(index) {
    var app = view[index];
    if (!app) return;
    state.detail = index;
    var d = el.detail;
    d.textContent = "";
    var art = make("div", "tv-detail__art");
    var img = make("img");
    img.src = app.icon;
    img.alt = app.name + " icon";
    art.appendChild(img);
    d.appendChild(art);

    var info = make("div", "tv-detail__info");
    info.appendChild(make("p", "tv-kicker", (app.soon ? "Coming soon" : app.kind_label) + " · " + app.titleid));
    var name = make("h2", "tv-detail__name", app.name);
    name.id = "tv-detail-name";
    info.appendChild(name);
    info.appendChild(make("p", "tv-detail__by", "by " + app.author));
    info.appendChild(make("p", "tv-detail__desc", app.description));
    var attrs = make("dl", "tv-attrs");
    attr(attrs, "Version", app.version);
    attr(attrs, "Format", app.format_label);
    attr(attrs, "License", app.license);
    attr(attrs, "Updated", app.updated);
    attr(attrs, "Source", app.source);
    info.appendChild(attrs);

    if (app.soon) {
      info.appendChild(make("p", "tv-note", "This title ID is reserved by its developer. The app isn't released yet; it will appear here with a download once it is."));
    } else {
      info.appendChild(make("h3", "tv-section-title", "Install"));
      var steps = make("ol", "tv-steps");
      app.steps.forEach(function (step) { steps.appendChild(make("li", "", step)); });
      info.appendChild(steps);
      var get = make("div", "tv-get");
      get.appendChild(make("span", "", "Download it on your computer or phone:"));
      get.appendChild(make("strong", "", app.short_url));
      info.appendChild(get);
      var hash = make("p", "tv-hash", "SHA-256 of " + app.artifact_name);
      hash.appendChild(make("code", "", app.sha256.match(/.{1,8}/g).join(" ")));
      info.appendChild(hash);
      info.appendChild(make("p", "tv-note", "Read the release notes first: some apps need a payload or extra setup. " + app.author + " is solely responsible for this app and its content."));
    }
    d.appendChild(info);

    var nav = make("div", "tv-detail__nav");
    nav.appendChild(make("span", "", index > 0 ? "◀ " + view[index - 1].name : ""));
    var count = make("span");
    count.appendChild(make("b", "", String(index + 1)));
    count.appendChild(document.createTextNode(" of " + view.length));
    nav.appendChild(count);
    nav.appendChild(make("span", "", index < view.length - 1 ? view[index + 1].name + " ▶" : ""));
    d.appendChild(nav);

    d.hidden = false;
    el.detailInfo = info;
    document.body.classList.add("in-detail");
    el.crossHint.textContent = "Back";
    el.moveHint.textContent = "Previous / next · scroll";
    writeHash();
  }

  function closeDetail() {
    el.detail.hidden = true;
    document.body.classList.remove("in-detail");
    el.moveHint.textContent = "Move";
    var index = state.detail;
    state.detail = -1;
    writeHash();
    setFocus("grid", index);
  }

  /* Input */

  function onDetailKey(code) {
    var info = el.detailInfo;
    switch (code) {
      case KEY.CIRCLE: case KEY.BACKSPACE: case KEY.CROSS: case KEY.GREEN: case KEY.TOP_MENU:
        closeDetail(); return true;
      case KEY.LEFT: case KEY.PREV:
        if (state.detail > 0) { state.index = state.detail - 1; openDetail(state.index); } return true;
      case KEY.RIGHT: case KEY.NEXT:
        if (state.detail < view.length - 1) { state.index = state.detail + 1; openDetail(state.index); } return true;
      case KEY.UP: case KEY.CHAN_UP: case KEY.PAGE_UP:
        info.scrollTop -= info.clientHeight * 0.4; return true;
      case KEY.DOWN: case KEY.CHAN_DOWN: case KEY.PAGE_DOWN:
        info.scrollTop += info.clientHeight * 0.4; return true;
    }
    return false;
  }

  function onRailKey(code) {
    var item = railItems[state.rail];
    switch (code) {
      case KEY.UP: setFocus("rail", state.rail - 1); break;
      case KEY.DOWN: setFocus("rail", state.rail + 1); break;
      case KEY.RIGHT: if (view.length) setFocus("grid", state.index); break;
      case KEY.CROSS: case KEY.GREEN:
        if (item.dataset.action === "sort") cycleSort();
        else if (item.dataset.action === "exit") location.href = item.href;
        else if (view.length) setFocus("grid", state.index);
        break;
      default: return false;
    }
    item = railItems[state.rail];
    if (item.dataset.kind) showKind(item.dataset.kind);
    return true;
  }

  function onGridKey(code) {
    var cols = columns();
    var i = state.index;
    switch (code) {
      case KEY.LEFT: if (i % cols === 0) setFocus("rail", state.rail); else setFocus("grid", i - 1); break;
      case KEY.RIGHT: if (i % cols < cols - 1 && i < view.length - 1) setFocus("grid", i + 1); break;
      case KEY.UP: if (i >= cols) setFocus("grid", i - cols); break;
      case KEY.DOWN: if (i + cols < view.length) setFocus("grid", i + cols); else if (Math.floor(i / cols) < Math.floor((view.length - 1) / cols)) setFocus("grid", view.length - 1); break;
      case KEY.CHAN_UP: case KEY.PAGE_UP: setFocus("grid", Math.max(i % cols, i - cols * 2)); break;
      case KEY.CHAN_DOWN: case KEY.PAGE_DOWN: setFocus("grid", Math.min(view.length - 1, i + cols * 2)); break;
      case KEY.CROSS: case KEY.GREEN: openDetail(i); break;
      case KEY.CIRCLE: case KEY.BACKSPACE: setFocus("rail", state.rail); break;
      default: return false;
    }
    return true;
  }

  function press(code) {
    document.body.classList.remove("uses-mouse");
    if (state.detail >= 0) return onDetailKey(code);
    if (code === KEY.TRIANGLE) { cycleSort(); return true; }
    if (code === KEY.SQUARE || code === KEY.TOP_MENU) { setFocus("rail", state.rail); return true; }
    return state.zone === "rail" ? onRailKey(code) : onGridKey(code);
  }

  function onKey(event) {
    var code = event.keyCode;
    var arrow = code >= KEY.LEFT && code <= KEY.DOWN;
    if (event.repeat && !arrow) { event.preventDefault(); return; }
    var now = Date.now();
    if (arrow && event.repeat && now - lastKeyAt < REPEAT_MS) { event.preventDefault(); return; }
    lastKeyAt = now;
    // A browser that reports the controller both ways sends a key right after the pad press: count it once.
    if (lastPad.code === code && now - lastPad.at < 150) { event.preventDefault(); return; }
    if (press(code)) event.preventDefault();
  }

  /* Gamepad API, for browsers that don't turn the controller into keys. The
     PS5 browser does, so there it stays off and no press counts twice. Buttons
     use the standard mapping; the left stick works like the D-pad. */

  var PAD_BUTTONS = [[0, KEY.CROSS], [1, KEY.CIRCLE], [2, KEY.SQUARE], [3, KEY.TRIANGLE],
                     [12, KEY.UP], [13, KEY.DOWN], [14, KEY.LEFT], [15, KEY.RIGHT], [4, KEY.PAGE_UP], [5, KEY.PAGE_DOWN]];
  var PAD_REPEAT_DELAY = 380;
  var padHeld = {};
  var lastPad = { code: 0, at: 0 };
  var polling = false;

  function padCodes(pad) {
    var down = [];
    PAD_BUTTONS.forEach(function (pair) {
      var button = pad.buttons[pair[0]];
      if (button && button.pressed) down.push(pair[1]);
    });
    var x = pad.axes[0] || 0, y = pad.axes[1] || 0;
    if (x < -0.6) down.push(KEY.LEFT); else if (x > 0.6) down.push(KEY.RIGHT);
    if (y < -0.6) down.push(KEY.UP); else if (y > 0.6) down.push(KEY.DOWN);
    return down;
  }

  function pollPads() {
    var pads = navigator.getGamepads ? navigator.getGamepads() : [];
    var now = Date.now();
    var down = {};
    Array.prototype.forEach.call(pads, function (pad) {
      if (pad && pad.connected) padCodes(pad).forEach(function (code) { down[code] = true; });
    });
    Object.keys(padHeld).forEach(function (code) { if (!down[code]) delete padHeld[code]; });
    Object.keys(down).forEach(function (key) {
      var code = Number(key);
      var held = padHeld[code];
      var arrow = code >= KEY.LEFT && code <= KEY.DOWN;
      if (!held) padHeld[code] = { next: now + PAD_REPEAT_DELAY };
      else if (arrow && now >= held.next) held.next = now + REPEAT_MS;
      else return;
      lastPad = { code: code, at: now };
      press(code);
    });
    polling = Array.prototype.some.call(pads, function (pad) { return pad && pad.connected; });
    if (polling) window.requestAnimationFrame(pollPads);
  }

  function startPads() {
    if (polling || !navigator.getGamepads || /PlayStation/i.test(navigator.userAgent)) return;
    var connected = Array.prototype.some.call(navigator.getGamepads(), function (pad) { return pad && pad.connected; });
    if (!connected) return; // "gamepadconnected" calls again once a controller is used
    polling = true;
    window.requestAnimationFrame(pollPads);
  }

  function onPointer(event) {
    document.body.classList.add("uses-mouse");
    var target = event.target.closest(".tv-tile, .tv-rail__item");
    if (!target || state.detail >= 0) return;
    if (target.classList.contains("tv-tile")) {
      setFocus("grid", Number(target.dataset.index));
      if (event.type === "click") openDetail(state.index);
    } else {
      setFocus("rail", railItems.indexOf(target));
      if (event.type !== "click") return;
      if (target.dataset.action === "sort") cycleSort();
      else if (target.dataset.kind) showKind(target.dataset.kind);
    }
  }

  function init() {
    try {
      // Arriving through the TV mode link returns the layout to automatic choice (see app.js).
      if (new URLSearchParams(location.search).get("layout") === "tv") {
        localStorage.removeItem("catalog-layout");
        history.replaceState(null, "", location.pathname + location.hash);
      }
    } catch (error) { /* storage blocked */ }
    var data = JSON.parse($("tv-data").textContent);
    apps = data.apps;
    apps.forEach(function (app) { app.sort_name = app.name.toLowerCase(); });
    el = {
      grid: $("tv-grid"), main: $("tv-main"), empty: $("tv-empty"), heading: $("tv-heading"),
      status: $("tv-status"), sort: $("tv-sort"), detail: $("tv-detail"), crossHint: $("tv-hint-cross"),
      moveHint: $("tv-hint-move")
    };
    railItems = Array.prototype.slice.call(document.querySelectorAll(".tv-rail__item"));
    var openId = readHash();
    renderGrid();
    state.rail = Math.max(0, railItems.map(function (i) { return i.dataset.kind; }).indexOf(state.kind));
    setFocus(view.length ? "grid" : "rail", 0);
    if (openId) {
      var index = view.map(function (a) { return a.titleid; }).indexOf(openId);
      if (index >= 0) { setFocus("grid", index); openDetail(index); }
    }
    document.addEventListener("keydown", onKey);
    window.addEventListener("gamepadconnected", startPads);
    startPads();
    document.addEventListener("click", onPointer);
    document.addEventListener("mouseover", onPointer);
    el.detail.addEventListener("click", function () { closeDetail(); });
    window.addEventListener("resize", function () { if (state.zone === "grid" && view.length) reveal(el.grid.children[state.index]); });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
