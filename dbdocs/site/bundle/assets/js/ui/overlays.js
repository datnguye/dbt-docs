/* dbdocs SPA — tier 3 (ui): command palette + toast notifications. */

import { el, icon } from "./dom.js";
import * as svc from "../service/service.js";

export var SEARCH_RESULT_CAP = 12;

var _sharedMini = null;
var _sharedDocs = null;

export function isMacPlatform() {
  return /Mac|iPhone|iPad|iPod/.test(navigator.platform || "");
}

export function ensureSearchIndex() {
  if (_sharedMini) return;
  _sharedDocs = svc.searchDocs();
  _sharedMini = new MiniSearch({
    fields: svc.SEARCH_FIELDS.map(function (f) { return f.key; }),
    storeFields: ["label", "resource_type", "schema"],
    searchOptions: {
      prefix: true,
      fuzzy: 0.2,
      boost: { label: 6, name: 6, columns: 3, tags: 2, relation: 2, description: 1, columnDescriptions: 1, code: 0.4 },
    },
  });
  _sharedMini.addAll(_sharedDocs);
}

export function sharedDocs() { return _sharedDocs; }
export function sharedMini() { return _sharedMini; }

export function runSearchQuery(raw) {
  var p = svc.parseSearchQuery(raw);
  if (!p.text) {
    if (!p.filterType) return [];
    var picked = [];
    for (var i = 0; i < _sharedDocs.length && picked.length < SEARCH_RESULT_CAP; i++) {
      if (_sharedDocs[i].resource_type === p.filterType) picked.push(_sharedDocs[i]);
    }
    return picked;
  }
  var opts = {};
  if (p.fields) opts.fields = p.fields;
  if (p.filterType) opts.filter = function (h) { return h.resource_type === p.filterType; };
  return _sharedMini.search(p.text, opts);
}

export function showToast(message) {
  var region = document.getElementById("toast-region");
  if (!region) return;
  var toast = el("div", { class: "toast" }, [message]);
  region.appendChild(toast);
  setTimeout(function () {
    toast.classList.add("toast-out");
    toast.addEventListener("animationend", function () {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, { once: true });
  }, 2200);
}

export function initCommandPalette() {
  if (typeof MiniSearch === "undefined") return;

  var isMac = isMacPlatform();
  var focusBeforeOpen = null;
  var paletteEl = null;
  var activeIdx = -1;

  function closePalette() {
    if (!paletteEl) return;
    var backdrop = document.getElementById("cmd-backdrop");
    if (backdrop && backdrop.parentNode) backdrop.parentNode.removeChild(backdrop);
    paletteEl = null;
    activeIdx = -1;
    if (focusBeforeOpen && typeof focusBeforeOpen.focus === "function") {
      focusBeforeOpen.focus();
    }
    focusBeforeOpen = null;
  }

  function paletteResultRows() {
    if (!paletteEl) return [];
    return Array.prototype.slice.call(paletteEl.querySelectorAll(".cmd-result[data-idx]"));
  }

  function movePaletteActive(delta) {
    var rows = paletteResultRows();
    if (!rows.length) return;
    rows.forEach(function (r) {
      r.classList.remove("cmd-active");
      r.setAttribute("aria-selected", "false");
    });
    if (activeIdx < 0 && delta < 0) {
      activeIdx = rows.length - 1;
    } else {
      activeIdx = (activeIdx + delta + rows.length) % rows.length;
    }
    var target = rows[activeIdx];
    if (target) {
      target.classList.add("cmd-active");
      target.setAttribute("aria-selected", "true");
      target.scrollIntoView({ block: "nearest" });
      var input = document.getElementById("cmd-input");
      if (input) input.setAttribute("aria-activedescendant", "cmd-opt-" + activeIdx);
    }
  }

  function activateRow(row) {
    if (!row) return;
    var href = row.getAttribute("data-href");
    if (href) location.hash = href;
    else {
      var action = row.getAttribute("data-action");
      if (action === "toggle-theme") {
        var t = document.getElementById("theme-toggle");
        if (t) t.click();
      } else if (action === "overview") {
        location.hash = "#/overview";
      } else if (action === "dag") {
        location.hash = "#/dag";
      } else if (action === "health") {
        location.hash = "#/health";
      } else if (action === "about") {
        location.hash = "#/about";
      }
    }
    closePalette();
  }

  function wireResultRow(row, i) {
    row.addEventListener("mousedown", function (e) { e.preventDefault(); activateRow(row); });
    row.addEventListener("click", function (e) { e.preventDefault(); activateRow(row); });
    row.addEventListener("mouseover", function () {
      activeIdx = i;
      paletteResultRows().forEach(function (r) {
        r.classList.remove("cmd-active");
        r.setAttribute("aria-selected", "false");
      });
      row.classList.add("cmd-active");
      row.setAttribute("aria-selected", "true");
    });
  }

  function renderPaletteResults(query, resultsEl, input) {
    while (resultsEl.firstChild) resultsEl.removeChild(resultsEl.firstChild);
    activeIdx = -1;
    input.removeAttribute("aria-activedescendant");

    var q = query.trim();

    if (!q) {
      var actions = [
        { label: "Catalog overview", icon: "catalog", action: "overview" },
        { label: "Lineage / DAG", icon: "dag", action: "dag" },
        { label: "Toggle theme", icon: "info", action: "toggle-theme" },
      ];
      if (svc.healthEnabled()) {
        actions.splice(2, 0, { label: "Health Check", icon: "health", action: "health" });
      }
      if (svc.meta().show_about !== false) {
        actions.splice(actions.length, 0, { label: "About / JSON API", icon: "api", action: "about" });
      }
      resultsEl.appendChild(el("div", { class: "cmd-section-label" }, ["Quick actions"]));
      actions.forEach(function (a, i) {
        var row = el("div", {
          class: "cmd-result", tabindex: "-1",
          role: "option", "aria-selected": "false",
          id: "cmd-opt-" + i, "data-idx": String(i), "data-action": a.action,
        }, [icon(a.icon, 15), el("span", { class: "cmd-result-label" }, [a.label])]);
        wireResultRow(row, i);
        resultsEl.appendChild(row);
      });
      return;
    }

    ensureSearchIndex();
    var hits = runSearchQuery(q).slice(0, SEARCH_RESULT_CAP);

    if (!hits.length) {
      resultsEl.appendChild(el("div", { class: "cmd-empty" }, ['No results for "' + q + '".']));
      return;
    }

    resultsEl.appendChild(el("div", { class: "cmd-section-label" }, ["Nodes"]));
    hits.forEach(function (h, i) {
      var href = "#/node/" + encodeURIComponent(h.id);
      var row = el("div", {
        class: "cmd-result", tabindex: "-1",
        role: "option", "aria-selected": "false",
        id: "cmd-opt-" + i, "data-idx": String(i), "data-href": href,
      }, [
        el("span", { class: "dot " + h.resource_type }),
        el("span", { class: "cmd-result-label" }, [h.label]),
        el("span", { class: "cmd-result-meta" }, [h.resource_type + (h.schema ? " · " + h.schema : "")]),
      ]);
      wireResultRow(row, i);
      resultsEl.appendChild(row);
    });
  }

  function openPalette() {
    if (document.getElementById("cmd-backdrop")) return;
    focusBeforeOpen = document.activeElement;

    var input = el("input", {
      id: "cmd-input", type: "search", autocomplete: "off",
      placeholder: "Search nodes or type a command…",
      "aria-label": "Command palette",
      "aria-autocomplete": "list",
      "aria-controls": "cmd-results",
    });
    var resultsEl = el("div", { id: "cmd-results", role: "listbox", "aria-label": "Results" });

    var palette = el("div", {
      id: "cmd-palette",
      role: "dialog", "aria-modal": "true", "aria-label": "Command palette",
    }, [
      el("div", { class: "cmd-input-wrap" }, [
        icon("catalog", 16),
        input,
        el("kbd", { class: "cmd-kbd-close" }, ["Esc"]),
      ]),
      resultsEl,
    ]);

    var backdrop = el("div", { id: "cmd-backdrop" }, [palette]);
    document.body.appendChild(backdrop);
    paletteEl = palette;

    renderPaletteResults("", resultsEl, input);
    input.focus();

    input.addEventListener("input", function () {
      renderPaletteResults(input.value, resultsEl, input);
    });

    input.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { e.preventDefault(); closePalette(); }
      else if (e.key === "ArrowDown") { e.preventDefault(); movePaletteActive(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); movePaletteActive(-1); }
      else if (e.key === "Enter") {
        e.preventDefault();
        var rows = paletteResultRows();
        activateRow(rows[activeIdx >= 0 ? activeIdx : 0]);
      }
    });

    backdrop.addEventListener("mousedown", function (e) {
      if (e.target === backdrop) closePalette();
    });
  }

  document.addEventListener("keydown", function (e) {
    var modKey = isMac ? e.metaKey : e.ctrlKey;
    if (modKey && e.key === "k") {
      e.preventDefault();
      if (document.getElementById("cmd-backdrop")) closePalette();
      else openPalette();
    }
    if (e.key === "Escape" && document.getElementById("cmd-backdrop")) {
      closePalette();
    }
  });
}
