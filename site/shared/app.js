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

  // Search, kind filter and URL state for the catalog grid.
  function setupStore() {
    var grid = document.querySelector("[data-grid]");
    if (!grid) return;
    var cards = Array.prototype.slice.call(grid.querySelectorAll("[data-app]"));
    var input = document.querySelector("[data-search]");
    var chips = Array.prototype.slice.call(document.querySelectorAll("[data-kind]"));
    var counts = Array.prototype.slice.call(document.querySelectorAll("[data-count]"));
    var empty = document.querySelector("[data-empty]");
    var params = new URLSearchParams(window.location.search);
    var kind = params.get("kind") || "all";
    if (!chips.some(function (c) { return c.getAttribute("data-kind") === kind; })) kind = "all";
    if (input) input.value = params.get("q") || "";

    function normalize(text) {
      return (text || "").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "");
    }

    function apply(updateUrl) {
      var terms = normalize(input ? input.value : "").split(/\s+/).filter(Boolean);
      var shown = 0;
      cards.forEach(function (card) {
        var text = normalize(card.getAttribute("data-search-text"));
        var visible = (kind === "all" || card.getAttribute("data-app-kind") === kind) &&
          terms.every(function (term) { return text.indexOf(term) !== -1; });
        card.hidden = !visible;
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
      if (updateUrl) {
        var next = new URLSearchParams();
        if (input && input.value.trim()) next.set("q", input.value.trim());
        if (kind !== "all") next.set("kind", kind);
        var query = next.toString();
        window.history.replaceState(null, "", window.location.pathname + (query ? "?" + query : "") + window.location.hash);
      }
    }

    if (input) input.addEventListener("input", function () { apply(true); });
    chips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        kind = chip.getAttribute("data-kind");
        apply(true);
      });
    });
    document.addEventListener("keydown", function (event) {
      var typing = event.target && /^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName);
      if (event.key === "/" && !typing && input) {
        event.preventDefault();
        input.focus();
      } else if (event.key === "Escape" && event.target === input) {
        input.value = "";
        apply(true);
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
