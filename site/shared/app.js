// Progressive enhancement only: every page works without JavaScript.
(function () {
  "use strict";
  var root = document.documentElement;
  root.classList.add("js");
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  document.addEventListener("DOMContentLoaded", function () {
    setupCopy();
    setupStore();
    setupTilt();
  });

  function setupCopy() {
    Array.prototype.forEach.call(document.querySelectorAll("[data-copy]"), function (button) {
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

  // Search, filters, sorting and URL state shared by the card and list views.
  function setupStore() {
    var grid = document.querySelector("[data-grid]");
    if (!grid) return;
    var items = Array.prototype.slice.call(grid.querySelectorAll("[data-app]"));
    var input = document.querySelector("[data-search]");
    var chips = Array.prototype.slice.call(document.querySelectorAll("[data-kind]"));
    var statusSelect = document.querySelector("[data-status-filter]");
    var formatSelect = document.querySelector("[data-format-filter]");
    var sortSelect = document.querySelector("[data-sort]");
    var reset = document.querySelector("[data-reset]");
    var viewLinks = Array.prototype.slice.call(document.querySelectorAll("[data-view-link]"));
    var counts = Array.prototype.slice.call(document.querySelectorAll("[data-count]"));
    var empty = document.querySelector("[data-empty]");
    var params = new URLSearchParams(window.location.search);

    function pick(select, value) {
      if (!select) return "all";
      var allowed = Array.prototype.some.call(select.options, function (o) { return o.value === value; });
      select.value = allowed ? value : select.options[0].value;
      return select.value;
    }

    var kind = params.get("kind") || "all";
    if (!chips.some(function (c) { return c.getAttribute("data-kind") === kind; })) kind = "all";
    if (input) input.value = params.get("q") || "";
    pick(statusSelect, params.get("status") || "all");
    pick(formatSelect, params.get("format") || "all");
    pick(sortSelect, params.get("sort") || "name");

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

    function state() {
      var next = new URLSearchParams();
      if (input && input.value.trim()) next.set("q", input.value.trim());
      if (kind !== "all") next.set("kind", kind);
      if (statusSelect && statusSelect.value !== "all") next.set("status", statusSelect.value);
      if (formatSelect && formatSelect.value !== "all") next.set("format", formatSelect.value);
      if (sortSelect && sortSelect.value !== "name") next.set("sort", sortSelect.value);
      return next.toString();
    }

    function apply(updateUrl) {
      var terms = normalize(input ? input.value : "").split(/\s+/).filter(Boolean);
      var status = statusSelect ? statusSelect.value : "all";
      var format = formatSelect ? formatSelect.value : "all";
      var shown = 0;
      items.slice().sort(sorters[sortSelect ? sortSelect.value : "name"] || sorters.name).forEach(function (item) {
        grid.appendChild(item);
        var text = normalize(item.getAttribute("data-search-text"));
        var visible = (kind === "all" || item.getAttribute("data-app-kind") === kind) &&
          (status === "all" || item.getAttribute("data-status") === status) &&
          (format === "all" || item.getAttribute("data-format") === format) &&
          terms.every(function (term) { return text.indexOf(term) !== -1; });
        item.hidden = !visible;
        if (visible) shown += 1;
      });
      chips.forEach(function (chip) {
        chip.setAttribute("aria-pressed", String(chip.getAttribute("data-kind") === kind));
      });
      counts.forEach(function (count) {
        var template = count.getAttribute("data-count") || "{n}";
        count.textContent = template.replace("{n}", shown).replace("{s}", shown === 1 ? "" : "s");
      });
      if (empty) empty.hidden = shown !== 0;
      var query = state();
      var filtered = query.replace(/(^|&)sort=[^&]*/, "") !== "";
      if (reset) reset.hidden = !filtered;
      viewLinks.forEach(function (link) {
        link.setAttribute("href", link.getAttribute("data-view-link") + (query ? "?" + query : ""));
      });
      if (updateUrl) {
        window.history.replaceState(null, "", window.location.pathname + (query ? "?" + query : "") + window.location.hash);
      }
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
    if (reset) reset.addEventListener("click", function () {
      kind = "all";
      if (input) input.value = "";
      pick(statusSelect, "all");
      pick(formatSelect, "all");
      apply(true);
    });
    document.addEventListener("keydown", function (event) {
      var typing = event.target && /^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName);
      if (event.key === "/" && !typing && input) {
        event.preventDefault();
        input.focus();
      } else if (event.key === "Escape" && event.target === input) {
        input.value = "";
        apply(true);
      } else if (event.key === "Enter" && event.target === input) {
        input.blur();
      }
    });
    apply(false);
  }

  // Pointer-driven tilt and sheen: sets --rx, --ry, --mx, --my on [data-tilt].
  function setupTilt() {
    if (reduceMotion) return;
    Array.prototype.forEach.call(document.querySelectorAll("[data-tilt]"), function (el) {
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
})();
