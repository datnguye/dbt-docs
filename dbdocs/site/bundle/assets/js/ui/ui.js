/* dbdocs SPA — tier 3: ui.

   DOM only. Renders the catalog, per-node pages, nav, search, theme and version
   switcher. Reads derived values from the service tier; never inspects the raw
   DATA shape directly. Graphs (lineage DAG + ERDs) are rendered by the React
   Flow bundle exposed as window.dbdocsGraph. No build step. */

import * as svc from "../service/service.js";
import { el, clear, icon, KNOWN_ICONS } from "./dom.js";
import { showToast, initCommandPalette, ensureSearchIndex, runSearchQuery, SEARCH_RESULT_CAP, isMacPlatform } from "./overlays.js";

var app = null;
var sidebar = null;
var mountedGraph = null;
var expandCollapseRefresh = null;
var sectionObserver = null;
var sectionObserverRefresh = null;

function unmountGraph() {
  if (mountedGraph && window.dbdocsGraph) {
    try { window.dbdocsGraph.unmount(mountedGraph); } catch (e) { /* ignore */ }
  }
  mountedGraph = null;
}

function graphMount(mode, focus, rtype, schema, erdFocus, erdSchema, layer) {
  var root = el("div", { class: "graph-host", id: "graph-root", "data-mode": mode });
  if (focus) root.setAttribute("data-focus", focus);
  if (rtype) root.setAttribute("data-rtype", rtype);
  if (schema) root.setAttribute("data-schema", schema);
  if (layer) root.setAttribute("data-layer", layer);
  if (erdFocus) root.setAttribute("data-erd-focus", erdFocus);
  if (erdSchema) root.setAttribute("data-erd-schema", erdSchema);
  var skeleton = el("div", { class: "graph-skeleton" });
  root.appendChild(skeleton);
  setTimeout(function () {
    if (root.contains(skeleton)) root.removeChild(skeleton);
    if (window.dbdocsGraph) { mountedGraph = root; window.dbdocsGraph.mount(root); }
    else root.appendChild(el("p", { class: "empty" }, ["Graph bundle not loaded."]));
  }, 0);
  return root;
}

function copyToClipboard(text, onResult) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(function () { onResult(true); }).catch(function () { onResult(false); });
  } else {
    onResult(false);
  }
}

function copyLinkButton() {
  var btn = el("button", { class: "fs-btn copy-link-btn", type: "button", title: "Copy link to this page" });
  btn.appendChild(icon("link", 15));
  btn.appendChild(document.createTextNode(" Copy link"));
  btn.addEventListener("click", function () {
    copyToClipboard(location.href, function (ok) {
      showToast(ok ? "Link copied!" : "Copy unavailable in this context.");
    });
  });
  return btn;
}

function sectionLinkButton(nodeId, sectionId) {
  var btn = el("button", {
    class: "fs-btn section-link-btn", type: "button",
    title: "Copy link to this section", "aria-label": "Copy link to this section",
  });
  btn.appendChild(icon("link", 14));
  btn.addEventListener("click", function () {
    var url = location.origin + location.pathname +
      "#/node/" + encodeURIComponent(nodeId) + "?sec=" + encodeURIComponent(sectionId);
    copyToClipboard(url, function (ok) {
      showToast(ok ? "Section link copied!" : "Copy unavailable in this context.");
    });
  });
  return btn;
}

export function route() {
  unmountGraph();
  if (expandCollapseRefresh) {
    app.removeEventListener("toggle", expandCollapseRefresh, true);
    expandCollapseRefresh = null;
  }
  if (sectionObserverRefresh) {
    app.removeEventListener("toggle", sectionObserverRefresh, true);
    sectionObserverRefresh = null;
  }
  if (sectionObserver) {
    sectionObserver.disconnect();
    sectionObserver = null;
  }
  var r = svc.parseHash(location.hash);
  var routeNode = r.view === "node" && r.id ? svc.node(r.id) : null;
  if (routeNode) renderNode(routeNode);
  else if (r.view === "dag") renderDag(r.query.focus, r.query.rtype, r.query.schema, r.query.layer);
  else if (r.view === "health") renderHealth(r.query.d);
  else if (r.view === "about") renderAbout();
  else if (r.view === "erd") { renderOverview(r.query.erd_focus, r.query.erd_schema); _scrollToErd(); }
  else renderOverview(r.query.erd_focus, r.query.erd_schema);
  if (r.view !== "dag") app.appendChild(contentFooter());
  highlightNav(r);
  app.focus();
  app.scrollTop = 0;
  app.classList.remove("page-enter");
  void app.offsetWidth;
  app.classList.add("page-enter");
  if (r.view === "node" && r.query.col) {
    _forceNodeSectionOpen("node-sec-columns");
    focusColumn(r.query.col);
  }
  if (r.view === "node" && r.query.sec) focusSection(r.query.sec);
  if (r.view === "node") _initSectionObserver();
}

function _scrollToErd() {
  setTimeout(function () {
    var heading = document.getElementById("erd-heading");
    if (!heading) return;
    heading.scrollIntoView({ behavior: "smooth", block: "start" });
    heading.focus({ preventScroll: true });
  }, 0);
}

function _forceNodeSectionOpen(sectionId) {
  var el_ = document.getElementById(sectionId);
  if (el_ && !el_.open) el_.open = true;
}

function focusSection(sec) {
  var target = document.getElementById("node-sec-" + sec);
  if (!target) return;
  target.open = true;
  setTimeout(function () {
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    var head = target.querySelector("summary");
    if (head) head.focus({ preventScroll: true });
  }, 0);
}

function _initSectionObserver() {
  if (!window.IntersectionObserver) return;
  var active = null;
  sectionObserver = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      var sec = entry.target.closest("details.node-section");
      if (!sec) return;
      if (entry.isIntersecting) {
        if (active && active !== sec) active.classList.remove("section-in-view");
        active = sec;
        sec.classList.add("section-in-view");
      } else if (active === sec) {
        sec.classList.remove("section-in-view");
        active = null;
      }
    });
  }, { root: app, threshold: 0.15 });
  app.querySelectorAll("details.node-section[open] > summary").forEach(function (s) {
    sectionObserver.observe(s);
  });
  sectionObserverRefresh = function () {
    if (!sectionObserver) return;
    app.querySelectorAll("details.node-section[open] > summary").forEach(function (s) {
      sectionObserver.observe(s);
    });
  };
  app.addEventListener("toggle", sectionObserverRefresh, true);
}

function focusColumn(column) {
  var row = app.querySelector('tr[data-col="' + (window.CSS && CSS.escape ? CSS.escape(String(column).toLowerCase()) : String(column).toLowerCase()) + '"]');
  if (!row) return;
  row.scrollIntoView({ block: "center" });
  row.setAttribute("tabindex", "-1");
  row.focus({ preventScroll: true });
  row.classList.add("col-flash");
  setTimeout(function () { row.classList.remove("col-flash"); }, 1600);
}

function contentFooter() {
  var foot = el("div", { class: "content-foot" });
  var left = el("span", { class: "cf-left" }, [
    icon("catalog", 14),
    el("span", {}, ["Generated by "]),
    el("a", { href: "https://github.com/datnguye/dbt-docs", target: "_blank", rel: "noopener" }, ["dbdocs"]),
  ]);
  var meta = svc.footerMeta();
  if (meta) left.appendChild(el("span", { class: "cf-meta" }, [" · " + meta]));
  var right = el("a", { class: "cf-top", href: "#", onclick: function (e) { e.preventDefault(); app.scrollTop = 0; } }, ["↑ Back to top"]);
  foot.appendChild(left);
  foot.appendChild(right);
  return foot;
}

var _NAV_TAB_KEYS = { catalog: 1, semantic: 1, other: 1 };
var _activeNavTab = "catalog";

function _loadNavTab() {
  var stored;
  try { stored = localStorage.getItem("dbdocs-nav-tab") || "catalog"; } catch (e) { stored = "catalog"; }
  _activeNavTab = _NAV_TAB_KEYS[stored] ? stored : "catalog";
}

function _saveNavTab(key) {
  _activeNavTab = key;
  try { localStorage.setItem("dbdocs-nav-tab", key); } catch (e) {}
}

function _buildCatalogPanel() {
  var wrap = el("div", { "data-tab-panel": "catalog" });
  var TREE = svc.tree();
  var NODES = svc.nodes();
  Object.keys(TREE).forEach(function (db) {
    var dbDetails = el("details", { class: "nav-section nav-db", open: "" }, [
      el("summary", {}, [icon("database"), el("span", {}, [db])]),
    ]);
    Object.keys(TREE[db]).forEach(function (schema) {
      var ids = svc.sortedNodeIds(TREE[db][schema]);
      var items = el("ul", { class: "nav-items" }, ids.map(function (id) {
        var n = NODES[id];
        return el("li", { "data-filter": svc.treeFilterText(id) }, [el("a", { href: "#/node/" + encodeURIComponent(id), "data-node": id }, [
          el("span", { class: "dot " + n.resource_type }), n.label,
        ])]);
      }));
      var schemaDetails = el("details", { class: "nav-section nav-schema", open: "" }, [
        el("summary", {}, [icon("schema"), el("span", {}, [schema])]), items,
      ]);
      dbDetails.appendChild(schemaDetails);
    });
    wrap.appendChild(dbDetails);
  });
  return wrap;
}

function _buildTypelessPanel(tabKey) {
  var wrap = el("div", { "data-tab-panel": tabKey });
  var NODES = svc.nodes();
  svc.navSections(tabKey).forEach(function (sec) {
    var items = el("ul", { class: "nav-items" }, sec.ids.map(function (id) {
      var n = NODES[id];
      return el("li", { "data-filter": svc.treeFilterText(id) }, [
        el("a", { href: "#/node/" + encodeURIComponent(id), "data-node": id }, [
          el("span", { class: "dot " + n.resource_type }), n.label,
        ]),
      ]);
    }));
    var details = el("details", {
      class: "nav-section nav-sl-section", open: "",
      "data-sl-rtype": sec.rtype,
    }, [
      el("summary", {}, [icon(sec.rtype), el("span", {}, [sec.label + " (" + sec.count + ")"])]),
      items,
    ]);
    wrap.appendChild(details);
  });
  return wrap;
}

function renderSidebarBody(tabKey) {
  var oldPanel = sidebar.querySelector(".nav-tab-panel");
  var panel = el("div", {
    class: "nav-tab-panel", id: "nav-tabpanel",
    role: "tabpanel", "aria-labelledby": "nav-tab-" + tabKey,
  });
  if (tabKey === "catalog") {
    panel.appendChild(_buildCatalogPanel());
  } else {
    panel.appendChild(_buildTypelessPanel(tabKey));
  }
  if (oldPanel) {
    sidebar.replaceChild(panel, oldPanel);
  } else {
    sidebar.appendChild(panel);
  }
}

export function buildNav() {
  clear(sidebar);
  sidebar.appendChild(el("a", { class: "nav-cta", href: "#/overview", "data-nav": "overview" }, [icon("catalog"), "Catalog overview"]));
  sidebar.appendChild(el("a", { class: "nav-cta", href: "#/dag", "data-nav": "dag" }, [icon("dag"), "Lineage / DAG"]));
  if (svc.healthEnabled()) {
    sidebar.appendChild(el("a", { class: "nav-cta", href: "#/health", "data-nav": "health" }, [icon("health"), "Health Check"]));
  }

  var tabs = svc.resourceTabs();
  _loadNavTab();
  var validKeys = tabs.map(function (t) { return t.key; });
  if (validKeys.indexOf(_activeNavTab) < 0) _activeNavTab = "catalog";

  var tabStrip = el("div", { class: "nav-tabs", role: "tablist", "aria-label": "Resource types" });
  tabs.forEach(function (t) {
    var isActive = t.key === _activeNavTab;
    var btn = el("button", {
      class: "nav-tab" + (isActive ? " active" : ""),
      role: "tab",
      type: "button",
      "aria-selected": isActive ? "true" : "false",
      id: "nav-tab-" + t.key,
      "aria-controls": "nav-tabpanel",
    }, [t.label + " (" + t.count + ")"]);
    btn.addEventListener("click", function () { activateNavTab(t.key); });
    tabStrip.appendChild(btn);
  });
  tabStrip.addEventListener("keydown", function (e) {
    var btns = Array.prototype.slice.call(tabStrip.querySelectorAll('[role="tab"]'));
    var cur = btns.indexOf(document.activeElement);
    if (cur < 0) return;
    var next = cur;
    if (e.key === "ArrowRight") next = (cur + 1) % btns.length;
    else if (e.key === "ArrowLeft") next = (cur - 1 + btns.length) % btns.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = btns.length - 1;
    else return;
    e.preventDefault();
    btns[next].focus();
  });
  sidebar.appendChild(tabStrip);

  var filter = el("input", {
    class: "nav-filter", type: "search", id: "nav-filter",
    placeholder: "Filter…", autocomplete: "off",
  });
  filter.addEventListener("input", function () { filterNav(filter.value); });
  sidebar.appendChild(filter);

  renderSidebarBody(_activeNavTab);
}

function activateNavTab(key) {
  if (key === _activeNavTab && sidebar.querySelector(".nav-tab-panel")) return;
  _saveNavTab(key);
  sidebar.querySelectorAll('[role="tab"]').forEach(function (btn) {
    var isThis = btn.id === "nav-tab-" + key;
    btn.classList.toggle("active", isThis);
    btn.setAttribute("aria-selected", isThis ? "true" : "false");
  });
  renderSidebarBody(key);
  var filterEl = document.getElementById("nav-filter");
  if (filterEl) filterNav(filterEl.value);
}

function filterNav(query) {
  var q = String(query || "").trim().toLowerCase();
  var panel = sidebar.querySelector(".nav-tab-panel");
  if (!panel) return;
  panel.querySelectorAll(".nav-db").forEach(function (db) {
    var dbHas = false;
    db.querySelectorAll(".nav-schema").forEach(function (sc) {
      var scHas = false;
      sc.querySelectorAll("li[data-filter]").forEach(function (li) {
        var match = !q || li.getAttribute("data-filter").indexOf(q) !== -1;
        li.hidden = !match;
        if (match) scHas = true;
      });
      sc.hidden = !scHas;
      if (q && scHas) sc.open = true;
      if (scHas) dbHas = true;
    });
    db.hidden = !dbHas;
    if (q && dbHas) db.open = true;
  });
  panel.querySelectorAll(".nav-sl-section").forEach(function (sec) {
    var secHas = false;
    sec.querySelectorAll("li[data-filter]").forEach(function (li) {
      var match = !q || li.getAttribute("data-filter").indexOf(q) !== -1;
      li.hidden = !match;
      if (match) secHas = true;
    });
    sec.hidden = !secHas;
    if (q && secHas) sec.open = true;
  });
}

function highlightNav(r) {
  sidebar.querySelectorAll("[data-node], [data-nav]").forEach(function (a) { a.classList.remove("active"); });
  if (r.view === "node" && r.id) {
    var n = svc.node(r.id);
    if (n && !svc.isCatalogNode(r.id)) {
      activateNavTab(svc.tabForRtype(n.resource_type));
      var sec = sidebar.querySelector('.nav-sl-section[data-sl-rtype="' + n.resource_type + '"]');
      if (sec) sec.open = true;
    }
    var a = sidebar.querySelector('[data-node="' + (window.CSS && CSS.escape ? CSS.escape(r.id) : r.id) + '"]');
    if (a) a.classList.add("active");
  } else {
    var navKey = r.view === "dag" ? "dag" : r.view === "health" ? "health" : "overview";
    var nav = sidebar.querySelector('[data-nav="' + navKey + '"]');
    if (nav) nav.classList.add("active");
  }
}

function renderAbout() {
  clear(app);
  app.appendChild(el("h1", {}, ["About"]));

  var apiSection = el("section", { class: "about-section" }, [
    el("h2", {}, ["JSON API"]),
    el("p", {}, [
      "dbdocs generate emits a static, addressable JSON API tree under ",
      el("code", {}, ["api/v1/"]),
      ". Every file is self-contained for headless and AI-agent consumption — no HTML parsing needed. Served over HTTP alongside the SPA.",
    ]),
    el("ul", { class: "about-api-list" }, [
      el("li", {}, [el("code", {}, ["index.json"]), " — entry-point index: metadata + all node stubs with relative links"]),
      el("li", {}, [el("code", {}, ["nodes/<id>.json"]), " — one file per node, enriched with depends_on, referenced_by, and column lineage"]),
      el("li", {}, [el("code", {}, ["lineage.json"]), " — the full node-level lineage graph (edges, parents, children)"]),
      el("li", {}, [el("code", {}, ["health.json"]), " — the Health Check section (dimensions, findings, test results)"]),
      el("li", {}, [el("code", {}, ["column-lineage.json"]), " — whole-graph column lineage (upstream edges + downstream children)"]),
      el("li", {}, [el("code", {}, ["schema/"]), " — JSON Schemas for each endpoint"]),
    ]),
    el("p", {}, [
      el("a", {
        class: "about-api-link", href: "api/v1/", target: "_blank", rel: "noopener",
        "aria-label": "Open the JSON API (opens in new tab)",
      }, [icon("api"), " Open the JSON API"]),
    ]),
  ]);
  app.appendChild(apiSection);

  var links = svc.aboutLinks();
  if (links.length) {
    var linksSection = el("section", { class: "about-section" }, [
      el("h2", {}, ["Links"]),
    ]);
    var linkList = el("ul", { class: "about-links-list" });
    links.forEach(function (link) {
      if (!link || !link.label || !link.href) return;
      linkList.appendChild(el("li", {}, [
        el("a", {
          href: link.href, target: "_blank", rel: "noopener",
          "aria-label": link.label + " (opens in new tab)",
        }, [link.label]),
      ]));
    });
    linksSection.appendChild(linkList);
    app.appendChild(linksSection);
  }
}

function renderOverview(erdFocus, erdSchema) {
  clear(app);
  var META = svc.meta();
  app.appendChild(el("h1", {}, [META.project_name || "dbt docs"]));
  if (META.site_description) app.appendChild(el("p", { class: "description", html: svc.mdInline(META.site_description) }, []));

  app.appendChild(el("div", { class: "cards" }, resourceCards(svc.counts())));

  if (svc.healthEnabled()) app.appendChild(healthSummaryCard());

  var erdHost = graphMount("erd", null, null, null, erdFocus || "", erdSchema || "");
  var fsBtn = el("button", {
    class: "fs-btn", type: "button", title: "Toggle full screen",
    onclick: function () { toggleFullscreen(erdHost); },
  }, [icon("fullscreen", 15), " Full screen"]);
  var erdHeader = el("div", { class: "page-head" }, [
    el("h2", { id: "erd-heading", tabindex: "-1" }, ["Entity-relationship diagram"]),
    el("div", { class: "page-head-actions" }, [fsBtn]),
  ]);
  app.appendChild(erdHeader);
  app.appendChild(erdHost);

  var README = svc.readme();
  if (README) app.appendChild(renderReadme(README));
}

function healthPills(summary, extraClass) {
  var pills = [
    el("span", { class: "health-pill pass" }, [String(summary.pass || 0) + " pass"]),
    el("span", { class: "health-pill warn" }, [String(summary.warn || 0) + " warn"]),
    el("span", { class: "health-pill fail" }, [String(summary.fail || 0) + " fail"]),
  ];
  if (summary.error) pills.push(el("span", { class: "health-pill error" }, [String(summary.error) + " error"]));
  if (summary.skipped) pills.push(el("span", { class: "health-pill skipped" }, [String(summary.skipped) + " skipped"]));
  pills.push(el("span", { class: "health-pill total" }, [String(summary.total || 0) + " total"]));
  return el("div", { class: "health-pills" + (extraClass ? " " + extraClass : "") }, pills);
}

var HEALTH_DIM_LABELS = {
  testing: "Testing",
  documentation: "Documentation",
  modeling: "Modeling",
  structure: "Structure",
  performance: "Performance",
  governance: "Governance",
};
var HEALTH_DIM_DESC = {
  testing: "Data-test coverage and primary-key tests",
  documentation: "Model and source descriptions",
  modeling: "DAG shape and layering best practices",
  structure: "Naming conventions and directory layout",
  performance: "Materializations and view chains",
  governance: "Contracts and model access",
};

function healthLabel(cat) {
  var words = String(cat).replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function healthScoreClass(score) {
  if (score >= 90) return "good";
  if (score >= 70) return "warn";
  return "bad";
}

function healthSummaryCard() {
  var total = svc.healthTotalIssues();
  var dims = svc.healthDimensions();
  var section = el("section", { class: "health-card" });
  section.appendChild(el("div", { class: "health-card-head" }, [
    el("h2", { class: "health-card-title" }, ["Health Check"]),
    el("a", { class: "health-card-link", href: "#/health" }, ["View all findings →"]),
  ]));
  section.appendChild(el("p", { class: "muted health-card-sub" }, [
    total === 0 ? "No issues detected." : String(total) + " issue" + (total !== 1 ? "s" : "") + " across " + dims.length + " dimensions.",
  ]));
  section.appendChild(healthScorecard(dims));
  return section;
}

function healthScorecard(dims) {
  var cards = (dims || svc.healthDimensions()).map(function (d) {
    var label = HEALTH_DIM_LABELS[d.key] || healthLabel(d.key);
    var children = [
      el("span", { class: "score-name" }, [label]),
      el("span", { class: "score-num" }, [String(d.score), el("span", { class: "score-pct" }, ["%"])]),
      el("span", { class: "score-issues muted" }, [d.issues === 0 ? "clear" : String(d.issues) + " issue" + (d.issues !== 1 ? "s" : "")]),
    ];
    return el("a", {
      class: "score-chip " + healthScoreClass(d.score),
      href: "#/health?d=" + encodeURIComponent(d.key),
      "aria-label": label + ": " + d.score + "%, " + (d.issues === 0 ? "no issues" : d.issues + " issue" + (d.issues !== 1 ? "s" : "")),
    }, children);
  });
  return el("div", { class: "health-scorecard" }, cards);
}

function renderHealth(focusDim) {
  clear(app);
  var header = el("div", { class: "page-head" }, [
    el("h1", {}, ["Health Check"]),
    el("div", { class: "page-head-actions" }, [copyLinkButton()]),
  ]);
  app.appendChild(header);
  app.appendChild(el("p", { class: "description" }, [
    "Project health across the six ",
    el("a", { href: "https://dbt-labs.github.io/dbt-project-evaluator/", target: "_blank", rel: "noopener" }, ["dbt-project-evaluator"]),
    " dimensions, derived from your dbt artifacts.",
  ]));

  app.appendChild(healthScorecard());

  var note = svc.healthNote();
  if (note) app.appendChild(el("p", { class: "empty health-note" }, [note]));

  svc.healthDimensions().forEach(function (d) {
    app.appendChild(healthDimensionSection(d, focusDim));
  });

  if (focusDim) {
    var target = document.getElementById("health-" + focusDim);
    if (target) setTimeout(function () {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      var head = target.querySelector("summary");
      if (head) head.focus({ preventScroll: true });
    }, 0);
  }
}

function healthDimensionSection(d, focusDim) {
  var label = HEALTH_DIM_LABELS[d.key] || healthLabel(d.key);
  var summary = el("summary", { class: "health-section-head" }, [
    el("span", { class: "score-pill " + healthScoreClass(d.score) }, [String(d.score) + "%"]),
    el("span", { class: "health-section-title" }, [label]),
    el("span", { class: "health-cat-count muted" }, [
      d.issues === 0 ? " — no issues" : " — " + d.issues + " issue" + (d.issues !== 1 ? "s" : ""),
    ]),
  ]);
  var body = el("div", { class: "health-section-body" });
  body.appendChild(el("p", { class: "muted" }, [HEALTH_DIM_DESC[d.key] || ""]));

  if (!d.findings.length) {
    body.appendChild(el("p", { class: "empty" }, ["No issues detected in this dimension."]));
  } else {
    groupBy(d.findings, "rule").forEach(function (group) {
      body.appendChild(healthRuleBlock(group.key, group.items));
    });
  }

  var attrs = { class: "health-section", id: "health-" + d.key };
  if (d.issues > 0 || d.key === focusDim) attrs.open = "";
  return el("details", attrs, [summary, body]);
}

function healthRuleBlock(rule, items) {
  var rows = items.map(function (f) {
    return el("tr", {}, [
      el("td", {}, [healthNodeCell(f.node)]),
      el("td", {}, [f.message ? el("span", {}, [f.message]) : el("span", { class: "muted" }, ["—"])]),
    ]);
  });
  var head = el("div", { class: "health-rule-head" }, [
    el("code", { class: "health-rule-name" }, [healthLabel(rule)]),
    el("span", { class: "health-cat-count muted" }, [" (" + items.length + ")"]),
    items[0] && items[0].docs_url ? el("a", { class: "health-rule-docs muted", href: items[0].docs_url, target: "_blank", rel: "noopener" }, ["docs"]) : null,
  ]);
  return el("div", { class: "health-rule" }, [
    head,
    el("table", {}, [
      el("thead", {}, [el("tr", {}, [th("Node"), th("Detail")])]),
      el("tbody", {}, rows),
    ]),
  ]);
}

function healthNodeCell(nodeId) {
  var short = svc.shortName(nodeId);
  if (svc.nodeOrNull(nodeId)) {
    return el("a", { href: "#/node/" + encodeURIComponent(nodeId), title: nodeId }, [short]);
  }
  return el("code", { title: nodeId }, [short]);
}


function dataTestTable(tests) {
  var rows = tests.map(function (f) {
    return el("tr", {}, [
      el("td", {}, [el("code", {}, [f.test_type || "custom"])]),
      el("td", {}, [f.column ? el("code", {}, [f.column]) : el("span", { class: "muted" }, ["—"])]),
      el("td", {}, [statusBadge(f.status)]),
      el("td", { class: "muted" }, [String(f.failures || 0)]),
      el("td", {}, [testDetailsCell(f)]),
      el("td", {}, [f.message ? el("span", {}, [f.message]) : el("span", { class: "muted" }, ["—"])]),
    ]);
  });
  return el("table", {}, [
    el("thead", {}, [el("tr", {}, [th("Test"), th("Column"), th("Status"), th("Failures"), th("Details"), th("Message")])]),
    el("tbody", {}, rows),
  ]);
}

function testDetailsCell(f) {
  var hasDesc = f.description && String(f.description).trim();
  var kwargs = f.kwargs || {};
  var kwargKeys = Object.keys(kwargs);
  if (!hasDesc && !kwargKeys.length) return el("span", { class: "muted" }, ["—"]);
  var children = [];
  if (hasDesc) children.push(el("div", { class: "test-desc" }, [String(f.description)]));
  if (kwargKeys.length) {
    children.push(el("div", { class: "test-kwargs" }, kwargKeys.map(function (k) {
      var raw = kwargs[k];
      var val = Array.isArray(raw) ? raw.join(", ") : String(raw);
      return el("span", { class: "kwarg-chip" }, [
        el("span", { class: "kwarg-key" }, [k + ": "]),
        el("code", { class: "kwarg-val" }, [val]),
      ]);
    })));
  }
  return el("div", { class: "test-details" }, children);
}

function unitTestTable(tests) {
  var rows = tests.map(function (f) {
    return el("tr", {}, [
      el("td", {}, [el("code", {}, [f.rule])]),
      el("td", {}, [statusBadge(f.status)]),
      el("td", {}, [f.message ? el("span", {}, [f.message]) : el("span", { class: "muted" }, ["—"])]),
    ]);
  });
  return el("table", {}, [
    el("thead", {}, [el("tr", {}, [th("Unit test"), th("Status"), th("Message")])]),
    el("tbody", {}, rows),
  ]);
}

function statusBadge(status) {
  var cls = "badge health-status ";
  if (status === "pass") cls += "health-pass";
  else if (status === "warn") cls += "health-warn";
  else if (status === "fail") cls += "health-fail";
  else if (status === "error") cls += "health-error";
  else cls += "health-skip";
  return el("span", { class: cls }, [status]);
}

function groupBy(items, prop) {
  var order = [];
  var map = {};
  items.forEach(function (it) {
    var k = it[prop];
    if (!map[k]) { map[k] = []; order.push(k); }
    map[k].push(it);
  });
  return order.map(function (k) { return { key: k, items: map[k] }; });
}

function renderReadme(md) {
  var box = el("section", { class: "readme" });
  var body = el("div", { class: "markdown-body" });
  try {
    body.innerHTML = marked.parse(md, { breaks: false, gfm: true });
  } catch (e) {
    body.appendChild(el("pre", { class: "code" }, [md]));
  }
  body.querySelectorAll("img[src]").forEach(function (img) {
    img.src = svc.repoUrl(img.getAttribute("src"), "raw") || img.src;
  });
  body.querySelectorAll("a[href]").forEach(function (a) {
    var fixed = svc.repoUrl(a.getAttribute("href"), "blob");
    if (fixed) a.setAttribute("href", fixed);
    if (/^https?:/.test(a.getAttribute("href") || "")) { a.target = "_blank"; a.rel = "noopener"; }
  });
  box.appendChild(body);
  return box;
}

function resourceCards(counts) {
  return svc.cardTypes(counts).map(function (t) { return card(counts[t], svc.pluralize(t), t); });
}
function card(num, lbl, rtype) {
  var ic = icon(KNOWN_ICONS[rtype] ? rtype : "graph", 18);
  ic.classList.add("card-ic", rtype);
  var head = el("div", { class: "card-head" }, [ic, el("div", { class: "num" }, [String(num)])]);
  return el("div", { class: "card" }, [head, el("div", { class: "lbl" }, [lbl])]);
}

function nodeDetailsBlock(n) {
  var rows = [];
  function addRow(label, value) {
    rows.push(el("dt", {}, [label]));
    rows.push(el("dd", {}, [value]));
  }
  if (n.materialization) addRow("Materialization", n.materialization);
  if (n.access) addRow("Access", n.access);
  if (n.group) addRow("Group", n.group);
  if (n.resource_type === "model" || n.contract_enforced) {
    addRow("Contract", n.contract_enforced ? "enforced" : "not enforced");
  }
  if (n.version) {
    var vtext = String(n.version);
    if (n.latest_version) vtext += "  (latest: " + n.latest_version + ")";
    addRow("Version", vtext);
  }
  if (n.owner) addRow("Owner", n.owner);
  if (n.original_file_path) {
    var repoHref = svc.repoUrl(n.original_file_path, "blob");
    var fileEl = repoHref
      ? el("a", { href: repoHref, target: "_blank", rel: "noopener" }, [n.original_file_path])
      : el("span", {}, [n.original_file_path]);
    addRow("File", fileEl);
  }
  var stats = n.stats || {};
  Object.keys(stats).forEach(function (k) {
    var s = stats[k];
    addRow(s.label || k, String(s.value == null ? "" : s.value));
  });
  var meta = n.meta || {};
  var metaKeys = Object.keys(meta);
  if (metaKeys.length) {
    var metaItems = metaKeys.map(function (k) {
      return el("li", { class: "meta-item" }, [k + ": " + JSON.stringify(meta[k])]);
    });
    addRow("Meta", el("ul", { class: "meta-list" }, metaItems));
  }
  if (!rows.length) return null;
  return el("div", { class: "node-details" }, [el("dl", {}, rows)]);
}

function detailsList(rows) {
  if (!rows.length) return null;
  var dl = el("dl", {});
  rows.forEach(function (pair) { dl.appendChild(pair[0]); dl.appendChild(pair[1]); });
  return el("div", { class: "node-details" }, [dl]);
}

function depChipList(items) {
  if (!items || !items.length) return null;
  var chips = items.map(function (d) {
    return el("a", { class: "dep-chip", href: "#/node/" + encodeURIComponent(d.id), title: d.id }, [
      el("span", { class: "dot " + d.rtype }), d.label,
    ]);
  });
  return el("div", { class: "dep-chips" }, chips);
}

function _depSection(label, items, nodeId, sectionId) {
  if (!items.length) return null;
  return nodeSection({
    nodeId: nodeId, id: sectionId, title: label,
    count: items.length, defaultOpen: true,
    body: depChipList(items),
  });
}

function _appendDepsSections(n) {
  var upSec = _depSection("Depends on", svc.dependsOn(n.id), n.id, "depends-on");
  if (upSec) app.appendChild(upSec);
  var dnSec = _depSection("Referenced by", svc.referencedBy(n.id), n.id, "referenced-by");
  if (dnSec) app.appendChild(dnSec);
}

function nodePageHeader(n) {
  app.appendChild(el("h1", {}, [n.label, " ", el("span", { class: "page-id" }, ["`" + n.resource_type + "`"])]));
  app.appendChild(el("div", { class: "page-id" }, [n.id]));
  var badges = el("div", { class: "badges" }, [el("span", { class: "badge rtype " + n.resource_type }, [n.resource_type])]);
  if (n.relation_name) badges.appendChild(el("span", { class: "badge" }, ["⌗ " + n.relation_name]));
  (n.tags || []).forEach(function (t) { badges.appendChild(el("span", { class: "badge tag" }, ["#" + t])); });
  var viewDag = el("a", { class: "badge", href: "#/dag?focus=" + encodeURIComponent(n.id) });
  viewDag.appendChild(icon("graph")); viewDag.appendChild(document.createTextNode(" View in DAG"));
  badges.appendChild(viewDag);
  badges.appendChild(copyLinkButton());
  badges.appendChild(expandCollapseBtn());
  app.appendChild(badges);
  app.appendChild(n.description
    ? el("p", { class: "description", html: svc.mdInline(n.description) }, [])
    : el("p", { class: "description muted" }, ["No description provided."]));
}

var SECTION_STATE_CAP = 100;
var _SECTION_LS_KEY = "dbdocs-node-sections";

function _loadSectionState() {
  try {
    var raw = localStorage.getItem(_SECTION_LS_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (e) { return {}; }
}

function _saveSectionState(state) {
  try { localStorage.setItem(_SECTION_LS_KEY, JSON.stringify(state)); } catch (e) {}
}

function _getSectionOpen(nodeId, sectionId, defaultOpen) {
  var state = _loadSectionState();
  var nodeState = state[nodeId];
  if (!nodeState || nodeState[sectionId] == null) return defaultOpen;
  return !!nodeState[sectionId];
}

function _setSectionOpen(nodeId, sectionId, open) {
  var state = _loadSectionState();
  if (!state._order) state._order = [];
  if (!state[nodeId]) {
    state._order.push(nodeId);
    state[nodeId] = {};
  } else {
    var idx = state._order.indexOf(nodeId);
    if (idx > -1) state._order.splice(idx, 1);
    state._order.push(nodeId);
  }
  state[nodeId][sectionId] = open;
  while (state._order.length > SECTION_STATE_CAP) {
    var oldest = state._order.shift();
    delete state[oldest];
  }
  _saveSectionState(state);
}

function nodeSection(opts) {
  var nodeId = opts.nodeId || "";
  var sectionId = opts.id || "";
  var isOpen = _getSectionOpen(nodeId, sectionId, !!opts.defaultOpen);

  var summaryTitle = el("span", { class: "node-section-title" }, [opts.title]);
  var summaryChildren = [summaryTitle];
  if (opts.count != null) {
    summaryChildren.push(el("span", { class: "node-section-count" }, [String(opts.count)]));
  }
  var actionList = opts.actions ? (Array.isArray(opts.actions) ? opts.actions.slice() : [opts.actions]) : [];
  if (nodeId && sectionId) actionList.unshift(sectionLinkButton(nodeId, sectionId));
  if (actionList.length) {
    var actionsWrap = el("span", { class: "node-section-summary-actions" });
    actionList.forEach(function (a) {
      a.addEventListener("click", function (e) { e.stopPropagation(); });
      actionsWrap.appendChild(a);
    });
    summaryChildren.push(actionsWrap);
  }

  var summary = el("summary", { class: "node-section-summary" }, summaryChildren);
  var bodyChildren = Array.isArray(opts.body) ? opts.body : [opts.body];
  var bodyEl = el("div", { class: "node-section-body" }, bodyChildren.filter(Boolean));

  var attrs = { class: "node-section", id: "node-sec-" + sectionId };
  if (isOpen) attrs.open = "";
  var details = el("details", attrs, [summary, bodyEl]);

  details.addEventListener("toggle", function () {
    _setSectionOpen(nodeId, sectionId, details.open);
  });
  return details;
}

function expandCollapseBtn() {
  var btn = el("button", { class: "fs-btn expand-collapse-btn", type: "button" });
  function refresh() {
    var sections = Array.prototype.slice.call(app.querySelectorAll(".node-section"));
    var allOpen = sections.length > 0 && sections.every(function (s) { return s.open; });
    btn.textContent = allOpen ? "Collapse all" : "Expand all";
  }
  btn.addEventListener("click", function () {
    var sections = Array.prototype.slice.call(app.querySelectorAll(".node-section"));
    var allOpen = sections.every(function (s) { return s.open; });
    sections.forEach(function (s) { s.open = !allOpen; });
    refresh();
  });
  if (expandCollapseRefresh) app.removeEventListener("toggle", expandCollapseRefresh, true);
  expandCollapseRefresh = refresh;
  app.addEventListener("toggle", refresh, true);
  setTimeout(refresh, 0);
  return btn;
}

function renderNode(n) {
  clear(app);
  if (n.resource_type === "metric") { renderMetricNode(n); return; }
  if (n.resource_type === "semantic_model") { renderSemanticModelNode(n); return; }
  if (n.resource_type === "saved_query") { renderSavedQueryNode(n); return; }
  if (n.resource_type === "unit_test") { renderUnitTestNode(n); return; }
  if (n.resource_type === "exposure") { renderExposureNode(n); return; }
  if (n.resource_type === "analysis" || n.resource_type === "operation") { renderCodeOnlyNode(n); return; }
  renderPhysicalNode(n);
}

function _physicalDetailsSection(n) {
  var det = nodeDetailsBlock(n);
  if (!det) return null;
  return nodeSection({ nodeId: n.id, id: "details", title: "Details", defaultOpen: true, body: det });
}

function _columnsSection(n) {
  var colLin = svc.columnLineageMap(n.id);
  var dnLin = svc.downstreamMap(n.id);
  var body;
  if (n.columns && n.columns.length) {
    var rows = n.columns.map(function (c) {
      return el("tr", { "data-col": String(c.name).toLowerCase() }, [
        el("td", {}, [el("code", {}, [c.name])]),
        el("td", { class: "muted" }, [c.type || ""]),
        el("td", {}, (c.tags || []).map(function (t) { return el("span", { class: "badge tag" }, ["#" + t]); })),
        el("td", {}, (c.tests || []).map(function (t) { return el("span", { class: "badge test" }, [t]); })),
        el("td", { html: String(c.description || "") }, []),
        el("td", {}, upstreamChips(colLin[String(c.name).toLowerCase()])),
        el("td", {}, downstreamChips(dnLin[String(c.name).toLowerCase()])),
      ]);
    });
    body = el("table", {}, [
      el("thead", {}, [el("tr", {}, [th("Column"), th("Type"), th("Tags"), th("Tests"), th("Description"), th("Upstream lineage"), th("Downstream impact")])]),
      el("tbody", {}, rows),
    ]);
  } else {
    body = el("p", { class: "empty" }, ["No columns found in the catalog for this entity."]);
  }
  return nodeSection({
    nodeId: n.id, id: "columns", title: "Columns",
    count: svc.columnCount(n), defaultOpen: true, body: body,
  });
}

function _testsSection(n) {
  var tr = svc.testResultsForNode(n.id);
  if (!tr) return null;
  var bodies = [healthPills(tr.summary)];
  if (tr.data.length) {
    bodies.push(el("h3", {}, ["Data tests"]));
    bodies.push(dataTestTable(tr.data));
  }
  if (tr.unit.length) {
    bodies.push(el("h3", {}, ["Unit tests"]));
    bodies.push(unitTestTable(tr.unit));
  }
  return nodeSection({
    nodeId: n.id, id: "tests", title: "Tests",
    count: tr.summary.total, defaultOpen: tr.summary.total > 0, body: bodies,
  });
}

function _erdSection(n) {
  var host = el("div", { class: "erd-section-host" });
  var mounted = false;
  var fsBtn = el("button", {
    class: "fs-btn", type: "button", title: "Toggle full screen",
    onclick: function () { toggleFullscreen(host); },
  }, [icon("fullscreen", 15), " Full screen"]);
  var sec = nodeSection({
    nodeId: n.id, id: "erd", title: "Related ERD",
    defaultOpen: true, actions: fsBtn, body: host,
  });
  function ensureMounted() {
    if (sec.open && !mounted) {
      mounted = true;
      var g = graphMount("erd-node", n.id);
      host.appendChild(g);
    }
  }
  sec.addEventListener("toggle", ensureMounted);
  if (sec.open) setTimeout(ensureMounted, 0);
  return sec;
}

function _sqlSection(n) {
  if (!n.compiled_code && !n.raw_code) return null;
  var macroCount = svc.macroCount(n);
  var bodies = [codeTabs(n)];
  if (macroCount > 0) {
    var macroSec = nodeSection({
      nodeId: n.id, id: "macros", title: "Macros used",
      count: macroCount, defaultOpen: false,
      body: n.macros.map(function (m) {
        return el("details", { class: "macro" }, [
          el("summary", {}, [m.name + (m.package ? "  (" + m.package + ")" : "")]),
          el("pre", { class: "code" }, [m.sql || ""]),
        ]);
      }),
    });
    bodies.push(macroSec);
  }
  return nodeSection({ nodeId: n.id, id: "sql", title: "Transformation logic", defaultOpen: false, body: bodies });
}

function renderPhysicalNode(n) {
  nodePageHeader(n);
  var detSec = _physicalDetailsSection(n);
  if (detSec) app.appendChild(detSec);

  app.appendChild(_columnsSection(n));

  var testSec = _testsSection(n);
  if (testSec) app.appendChild(testSec);

  app.appendChild(_erdSection(n));

  _appendDepsSections(n);

  var sqlSec = _sqlSection(n);
  if (sqlSec) app.appendChild(sqlSec);
}

function renderCodeOnlyNode(n) {
  nodePageHeader(n);
  var detRows = [];
  if (n.original_file_path) {
    var repoHref = svc.repoUrl(n.original_file_path, "blob");
    var fileEl = repoHref
      ? el("a", { href: repoHref, target: "_blank", rel: "noopener" }, [n.original_file_path])
      : el("span", {}, [n.original_file_path]);
    detRows.push([el("dt", {}, ["File"]), el("dd", {}, [fileEl])]);
  }
  if (n.package) detRows.push([el("dt", {}, ["Package"]), el("dd", {}, [n.package])]);
  var detSec = detailsList(detRows);
  if (detSec) {
    app.appendChild(nodeSection({ nodeId: n.id, id: "details", title: "Details", defaultOpen: true, body: detSec }));
  }

  _appendDepsSections(n);

  if (n.compiled_code || n.raw_code) {
    app.appendChild(nodeSection({ nodeId: n.id, id: "code", title: "Code", defaultOpen: true, body: codeTabs(n) }));
  }
}

function metricNameLink(name) {
  var resolved = svc.metricByName(name);
  return resolved
    ? el("a", { class: "dep-chip", href: "#/node/" + encodeURIComponent(resolved.id), title: resolved.id }, [
        el("span", { class: "dot metric" }), resolved.label,
      ])
    : el("code", {}, [name]);
}

function measureNameLink(measureName) {
  var resolved = svc.semanticModelForMeasure(measureName);
  return resolved
    ? el("a", { class: "dep-chip", href: "#/node/" + encodeURIComponent(resolved.id), title: "measure " + measureName + " on " + resolved.id }, [
        el("span", { class: "dot semantic_model" }), resolved.label + "." + measureName,
      ])
    : el("code", {}, [measureName]);
}

function renderMetricNode(n) {
  nodePageHeader(n);
  var m = svc.metricPayload(n);
  var rows = [];
  if (m.type) rows.push([el("dt", {}, ["Type"]), el("dd", {}, [el("code", {}, [m.type])])]);
  if (m.label) rows.push([el("dt", {}, ["Label"]), el("dd", {}, [m.label])]);
  if (m.filter) rows.push([el("dt", {}, ["Filter"]), el("dd", {}, [el("code", {}, [m.filter])])]);
  var tp = m.type_params || {};
  var LINKED_METRIC_KEYS = { metrics: true };
  var LINKED_MEASURE_KEYS = { measure: true, numerator: true, denominator: true, input_measures: true };
  Object.keys(tp).forEach(function (k) {
    var v = tp[k];
    var dd;
    if (LINKED_METRIC_KEYS[k] && Array.isArray(v)) {
      dd = el("dd", {}, [el("div", { class: "dep-chips" }, v.map(metricNameLink))]);
    } else if (LINKED_MEASURE_KEYS[k]) {
      if (Array.isArray(v)) {
        dd = el("dd", {}, [el("div", { class: "dep-chips" }, v.map(measureNameLink))]);
      } else {
        dd = el("dd", {}, [measureNameLink(String(v))]);
      }
    } else {
      dd = el("dd", {}, [el("code", {}, [String(v)])]);
    }
    rows.push([el("dt", {}, [k]), dd]);
  });
  var det = detailsList(rows);
  if (det) app.appendChild(nodeSection({ nodeId: n.id, id: "details", title: "Details", defaultOpen: true, body: det }));

  _appendDepsSections(n);
}

function renderSemanticModelNode(n) {
  nodePageHeader(n);
  var sm = svc.semanticModelPayload(n);
  var detRows = [];
  if (sm.model) {
    var nd = svc.node(sm.model);
    var modelLink = nd
      ? el("a", { href: "#/node/" + encodeURIComponent(sm.model) }, [nd.label || nd.name])
      : el("code", {}, [sm.model]);
    detRows.push([el("dt", {}, ["Underlying model"]), el("dd", {}, [modelLink])]);
  }
  var det = detailsList(detRows);
  if (det) app.appendChild(nodeSection({ nodeId: n.id, id: "details", title: "Details", defaultOpen: true, body: det }));

  if (sm.entities && sm.entities.length) {
    app.appendChild(nodeSection({ nodeId: n.id, id: "entities", title: "Entities", count: sm.entities.length, defaultOpen: true, body: smTable(sm.entities, ["name", "type"]) }));
  }
  if (sm.dimensions && sm.dimensions.length) {
    app.appendChild(nodeSection({ nodeId: n.id, id: "dimensions", title: "Dimensions", count: sm.dimensions.length, defaultOpen: true, body: smTable(sm.dimensions, ["name", "type"]) }));
  }
  if (sm.measures && sm.measures.length) {
    app.appendChild(nodeSection({ nodeId: n.id, id: "measures", title: "Measures", count: sm.measures.length, defaultOpen: true, body: smTable(sm.measures, ["name", "agg", "expr"]) }));
  }
  var builtMetrics = svc.metricsForSemanticModel(n.id);
  if (builtMetrics.length) {
    var metricChips = el("div", { class: "dep-chips" }, builtMetrics.map(function (m) {
      return el("a", { class: "dep-chip", href: "#/node/" + encodeURIComponent(m.id), title: m.id }, [
        el("span", { class: "dot metric" }), m.label,
      ]);
    }));
    app.appendChild(nodeSection({ nodeId: n.id, id: "metrics-built", title: "Metrics built on this model", count: builtMetrics.length, defaultOpen: true, body: metricChips }));
  }

  _appendDepsSections(n);
}

function smTable(items, cols) {
  var head = el("thead", {}, [el("tr", {}, cols.map(function (c) { return th(c.charAt(0).toUpperCase() + c.slice(1)); }))]);
  var body = el("tbody", {}, items.map(function (item) {
    return el("tr", {}, cols.map(function (c) {
      return el("td", {}, [item[c] ? el("code", {}, [item[c]]) : el("span", { class: "muted" }, ["—"])]);
    }));
  }));
  return el("table", {}, [head, body]);
}

function renderSavedQueryNode(n) {
  nodePageHeader(n);
  var sq = svc.savedQueryPayload(n);
  var rows = [];
  if (sq.label) rows.push([el("dt", {}, ["Label"]), el("dd", {}, [sq.label])]);
  var det = detailsList(rows);
  if (det) app.appendChild(nodeSection({ nodeId: n.id, id: "details", title: "Details", defaultOpen: true, body: det }));

  if (sq.metrics && sq.metrics.length) {
    app.appendChild(nodeSection({ nodeId: n.id, id: "metrics", title: "Metrics", count: sq.metrics.length, defaultOpen: true, body: el("div", { class: "dep-chips" }, sq.metrics.map(metricNameLink)) }));
  }
  if (sq.group_by && sq.group_by.length) {
    app.appendChild(nodeSection({ nodeId: n.id, id: "group-by", title: "Group by", count: sq.group_by.length, defaultOpen: true, body: el("div", { class: "dep-chips" }, sq.group_by.map(function (g) { return el("code", {}, [g]); })) }));
  }
  if (sq.where && sq.where.length) {
    app.appendChild(nodeSection({ nodeId: n.id, id: "where", title: "Where filters", count: sq.where.length, defaultOpen: true, body: el("div", { class: "dep-chips" }, sq.where.map(function (w) { return el("code", {}, [w]); })) }));
  }
  if (sq.exports && sq.exports.length) {
    var exportRows = sq.exports.map(function (e) {
      return el("tr", {}, [
        el("td", {}, [e.name ? el("code", {}, [e.name]) : el("span", { class: "muted" }, ["—"])]),
        el("td", {}, [e.export_as ? el("code", {}, [e.export_as]) : el("span", { class: "muted" }, ["—"])]),
        el("td", {}, [e.schema ? el("span", {}, [e.schema]) : el("span", { class: "muted" }, ["—"])]),
        el("td", {}, [e.alias ? el("code", {}, [e.alias]) : el("span", { class: "muted" }, ["—"])]),
      ]);
    });
    var exportTable = el("table", {}, [
      el("thead", {}, [el("tr", {}, [th("Export"), th("As"), th("Schema"), th("Alias")])]),
      el("tbody", {}, exportRows),
    ]);
    app.appendChild(nodeSection({ nodeId: n.id, id: "exports", title: "Exports", count: sq.exports.length, defaultOpen: true, body: exportTable }));
  }

  _appendDepsSections(n);
}

function fixtureBody(columns, data, sql, total) {
  if (sql) return el("pre", { class: "code" }, [sql]);
  if (!data || !data.length) return el("p", { class: "muted" }, ["No rows provided."]);
  var head = el("thead", {}, [el("tr", {}, columns.map(th))]);
  var body = el("tbody", {}, data.map(function (row) {
    return el("tr", {}, columns.map(function (c) {
      var v = row[c];
      return el("td", {}, [v != null && v !== "" ? el("code", {}, [v]) : el("span", { class: "muted" }, ["—"])]);
    }));
  }));
  var children = [el("div", { class: "table-scroll" }, [el("table", {}, [head, body])])];
  if (total != null && total > data.length) {
    children.push(el("p", { class: "muted fixture-more" }, ["Showing " + data.length + " of " + total + " rows."]));
  }
  return el("div", {}, children);
}

function renderUnitTestNode(n) {
  nodePageHeader(n);
  var ut = svc.unitTestPayload(n);
  var modelNode = ut.model ? svc.node(ut.model) : null;
  var rows = [];
  if (ut.model) {
    var modelEl = modelNode
      ? el("a", { href: "#/node/" + encodeURIComponent(ut.model) }, [modelNode.label || modelNode.name])
      : el("code", {}, [ut.model]);
    rows.push([el("dt", {}, ["Model under test"]), el("dd", {}, [modelEl])]);
  }
  var det = detailsList(rows);
  if (det) app.appendChild(nodeSection({ nodeId: n.id, id: "details", title: "Details", defaultOpen: true, body: det }));

  (ut.given || []).forEach(function (g, i) {
    var title = "Given: " + (g.ref || "input " + i);
    if (g.format) title += " (" + g.format + ")";
    app.appendChild(nodeSection({
      nodeId: n.id, id: "given-" + i, title: title, count: g.rows_count,
      defaultOpen: true, body: fixtureBody(g.columns || [], g.rows || [], g.sql || "", g.rows_count),
    }));
  });

  var hasExpect = (ut.expect_data && ut.expect_data.length) || ut.expect_sql;
  if (hasExpect) {
    var expectTitle = "Expected output";
    if (ut.expect_format) expectTitle += " (" + ut.expect_format + ")";
    app.appendChild(nodeSection({
      nodeId: n.id, id: "expect", title: expectTitle, count: ut.expect_rows,
      defaultOpen: true, body: fixtureBody(ut.expect_columns || [], ut.expect_data || [], ut.expect_sql || "", ut.expect_rows),
    }));
  }
}

function renderExposureNode(n) {
  nodePageHeader(n);
  var ex = svc.exposurePayload(n);
  var rows = [];
  if (ex.type) rows.push([el("dt", {}, ["Type"]), el("dd", {}, [el("code", {}, [ex.type])])]);
  if (ex.label) rows.push([el("dt", {}, ["Label"]), el("dd", {}, [ex.label])]);
  if (ex.maturity) rows.push([el("dt", {}, ["Maturity"]), el("dd", {}, [el("code", {}, [ex.maturity])])]);
  if (ex.url) rows.push([el("dt", {}, ["URL"]), el("dd", {}, [el("a", { href: ex.url, target: "_blank", rel: "noopener" }, [ex.url])])]);
  if (ex.owner_name || ex.owner_email) {
    rows.push([el("dt", {}, ["Owner"]), el("dd", {}, [ex.owner_name || ex.owner_email])]);
  }
  var det = detailsList(rows);
  if (det) app.appendChild(nodeSection({ nodeId: n.id, id: "details", title: "Details", defaultOpen: true, body: det }));

  _appendDepsSections(n);
}
function th(t) { return el("th", {}, [t]); }

function upstreamChips(upstream) {
  if (!upstream || !upstream.length) return [el("span", { class: "muted" }, ["—"])];
  var NODES = svc.nodes();
  return upstream.map(function (u) {
    var label = NODES[u.node] ? NODES[u.node].label : svc.shortName(u.node);
    return el("span", { class: "up-chip" }, [
      el("span", { class: "up-model" }, [label + "."]),
      el("a", {
        href: "#/node/" + encodeURIComponent(u.node) + "?col=" + encodeURIComponent(u.column),
        title: u.node,
      }, [u.column]),
    ]);
  });
}

function downstreamChips(downstream) {
  if (!downstream || !downstream.length) return [el("span", { class: "muted" }, ["—"])];
  var NODES = svc.nodes();
  return downstream.map(function (u) {
    var label = NODES[u.node] ? NODES[u.node].label : svc.shortName(u.node);
    return el("span", { class: "up-chip" }, [
      el("span", { class: "up-model" }, [label + "."]),
      el("a", {
        href: "#/node/" + encodeURIComponent(u.node) + "?col=" + encodeURIComponent(u.column),
        title: u.node,
      }, [u.column]),
    ]);
  });
}

function codeTabs(n) {
  var wrap = el("div", {});
  var tabs = el("div", { class: "tabs" });
  var panels = el("div", {});
  var defs = [];
  if (n.compiled_code) defs.push({ label: "Compiled SQL", code: n.compiled_code });
  if (n.raw_code) defs.push({ label: "Source", code: n.raw_code });
  defs.forEach(function (d, i) {
    var panel = el("div", { class: "tab-panel" + (i === 0 ? " active" : "") }, [el("pre", { class: "code" }, [d.code])]);
    var tab = el("div", { class: "tab" + (i === 0 ? " active" : ""), onclick: function () {
      tabs.querySelectorAll(".tab").forEach(function (t) { t.classList.remove("active"); });
      panels.querySelectorAll(".tab-panel").forEach(function (p) { p.classList.remove("active"); });
      tab.classList.add("active"); panel.classList.add("active");
    } }, [d.label]);
    tabs.appendChild(tab); panels.appendChild(panel);
  });
  wrap.appendChild(tabs); wrap.appendChild(panels);
  return wrap;
}

function renderDag(focusId, rtype, schema, layer) {
  clear(app);
  var resolvedFocus = focusId && svc.node(focusId) ? focusId : null;
  var host = graphMount("dag", resolvedFocus, rtype || "", schema || "", null, null, layer || "");
  var fsBtn = el("button", {
    class: "fs-btn", type: "button", title: "Toggle full screen",
    onclick: function () { toggleFullscreen(host); },
  }, [icon("fullscreen", 15), " Full screen"]);
  var header = el("div", { class: "page-head" }, [
    el("h1", {}, ["Lineage / DAG"]),
    el("div", { class: "page-head-actions" }, [copyLinkButton(), fsBtn]),
  ]);
  app.appendChild(header);
  app.appendChild(host);
}

function toggleFullscreen(host) {
  if (document.fullscreenElement) {
    document.exitFullscreen();
  } else if (host.requestFullscreen) {
    host.requestFullscreen().catch(function () { /* denied — ignore */ });
  }
}

function buildSearch() {
  var input = document.getElementById("search");
  var results = document.getElementById("search-results");
  var status = document.getElementById("search-status");
  if (typeof MiniSearch === "undefined") return;
  ensureSearchIndex();

  var isMac = isMacPlatform();
  var hintWrap = el("div", { class: "cmd-hint", "aria-hidden": "true" }, [
    el("kbd", {}, [isMac ? "⌘" : "Ctrl"]),
    el("kbd", {}, ["K"]),
  ]);
  input.parentNode.appendChild(hintWrap);

  function highlightNodes(text, terms) {
    var safe = (terms || []).map(function (t) { return String(t).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }).filter(Boolean);
    if (!safe.length) return [text];
    var re = new RegExp("(" + safe.join("|") + ")", "ig");
    return String(text).split(re).map(function (piece, i) {
      return i % 2 === 1 ? el("mark", null, [piece]) : piece;
    });
  }

  function snippetNode(h) {
    var snip = svc.searchSnippet(h.id, h.match, h.terms);
    if (!snip) return null;
    return el("span", { class: "sr-snippet" }, [
      el("span", { class: "sr-snippet-field" }, [snip.field]),
      el("span", { class: "sr-snippet-text" }, highlightNodes(snip.text, h.terms)),
    ]);
  }

  var activeIndex = -1;

  function setExpanded(open) {
    results.hidden = !open;
    input.setAttribute("aria-expanded", open ? "true" : "false");
    if (!open) {
      activeIndex = -1;
      input.removeAttribute("aria-activedescendant");
      status.textContent = "";
    }
  }

  function optionRows() { return results.querySelectorAll('[role="option"]'); }

  function moveActive(delta) {
    var rows = optionRows();
    if (!rows.length) return;
    if (activeIndex >= 0 && rows[activeIndex]) rows[activeIndex].setAttribute("aria-selected", "false");
    activeIndex = (activeIndex + delta + rows.length) % rows.length;
    rows.forEach(function (r, i) { r.classList.toggle("active", i === activeIndex); });
    var active = rows[activeIndex];
    active.setAttribute("aria-selected", "true");
    input.setAttribute("aria-activedescendant", active.id);
    active.scrollIntoView({ block: "nearest" });
  }

  function render(hits) {
    clear(results);
    activeIndex = -1;
    input.removeAttribute("aria-activedescendant");
    if (!hits.length) {
      var noMatches = "No matches.";
      results.appendChild(el("div", { class: "sr-empty" }, [noMatches]));
      status.textContent = noMatches;
      setExpanded(true);
      return;
    }
    var shown = Math.min(hits.length, SEARCH_RESULT_CAP);
    status.textContent = shown === 1 ? "1 result." : shown + " results.";
    hits.slice(0, SEARCH_RESULT_CAP).forEach(function (h, i) {
      var children = [
        el("span", { class: "sr-title" }, [
          el("span", { class: "dot " + h.resource_type }), " " + h.label,
          el("span", { class: "sr-meta" }, ["  " + h.resource_type + " · " + h.schema]),
        ]),
      ];
      var snip = snippetNode(h);
      if (snip) children.push(snip);
      results.appendChild(el("a", {
        id: "search-opt-" + i,
        role: "option",
        "aria-selected": "false",
        href: "#/node/" + encodeURIComponent(h.id),
        onclick: function () { closeSearch(); },
      }, children));
    });
    setExpanded(true);
  }

  function closeSearch() { setExpanded(false); input.value = ""; setSearchOpen(false); }

  function runQuery(raw) { return runSearchQuery(raw); }

  input.addEventListener("input", function () {
    var q = input.value.trim();
    if (!q) { setExpanded(false); return; }
    render(runQuery(q));
  });
  input.addEventListener("focus", function () { if (input.value.trim()) render(runQuery(input.value.trim())); });
  input.addEventListener("keydown", function (e) {
    if (results.hidden) return;
    if (e.key === "ArrowDown") { e.preventDefault(); moveActive(1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); moveActive(-1); }
    else if (e.key === "Enter") {
      var rows = optionRows();
      var target = rows[activeIndex >= 0 ? activeIndex : 0];
      if (target) { e.preventDefault(); location.hash = target.getAttribute("href"); closeSearch(); }
    } else if (e.key === "Escape") { setExpanded(false); }
  });
  document.addEventListener("click", function (e) { if (!results.contains(e.target) && e.target !== input) setExpanded(false); });
}

function initTheme() {
  var saved = null;
  try { saved = localStorage.getItem("dbdocs-theme"); } catch (e) { /* private mode */ }
  if (saved) document.documentElement.setAttribute("data-theme", saved);
  document.getElementById("theme-toggle").addEventListener("click", function () {
    var cur = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    document.documentElement.classList.add("theme-transition");
    document.documentElement.setAttribute("data-theme", cur);
    try { localStorage.setItem("dbdocs-theme", cur); } catch (e) { /* ignore */ }
    setTimeout(function () { document.documentElement.classList.remove("theme-transition"); }, 300);
    route();
  });
}

function currentVersionDir() {
  var parts = location.pathname.split("/").filter(Boolean);
  if (parts.length && /\.[a-z]+$/i.test(parts[parts.length - 1])) parts.pop();
  return parts.length ? parts[parts.length - 1] : "";
}

function initVersions() {
  if (!svc.isVersioned()) return;
  var sel = document.getElementById("version-switcher");
  fetch("../versions.json").then(function (r) { return r.ok ? r.json() : null; }).then(function (versions) {
    if (!versions || !versions.length) return;
    versions.forEach(function (v) {
      var label = v.title || v.version + (v.aliases && v.aliases.length ? " (" + v.aliases.join(", ") + ")" : "");
      sel.appendChild(el("option", { value: v.version }, [label]));
    });
    sel.hidden = false;
    var current = currentVersionDir();
    versions.forEach(function (v) { if (v.version === current || (v.aliases || []).indexOf(current) >= 0) sel.value = v.version; });
    sel.addEventListener("change", function () { location.href = "../" + sel.value + "/index.html"; });
    maybeWarnNotLatest(versions, current);
  }).catch(function () { /* versions.json missing: hide the switcher */ });
}

function maybeWarnNotLatest(versions, current) {
  var latest = versions[0];
  if (!latest) return;
  var isLatest = current === latest.version || (latest.aliases || []).indexOf(current) >= 0;
  var defaultAlias = (svc.meta().default_version || "latest");
  if (isLatest || current === defaultAlias) return;
  var target = "../" + ((latest.aliases || []).indexOf(defaultAlias) >= 0 ? defaultAlias : latest.version) + "/index.html";
  var banner = el("div", { class: "version-warning" }, [
    el("span", {}, ["You're viewing version "]), el("strong", {}, [current || "?"]),
    el("span", {}, [" — not the latest ("]), el("strong", {}, [latest.version]), el("span", {}, [")."]),
    el("a", { href: target }, ["Go to latest →"]),
  ]);
  document.body.insertBefore(banner, document.body.firstChild);
}

function setNavOpen(open) {
  document.body.classList.toggle("nav-open", open);
  var overlay = document.getElementById("nav-overlay");
  if (overlay) overlay.hidden = !open;
  var toggle = document.getElementById("nav-toggle");
  if (toggle) toggle.setAttribute("aria-expanded", open ? "true" : "false");
}

function setNavCollapsed(collapsed) {
  document.body.classList.toggle("nav-collapsed", collapsed);
  var btn = document.getElementById("nav-collapse");
  if (btn) btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
}

function initNav() {
  var toggle = document.getElementById("nav-toggle");
  var overlay = document.getElementById("nav-overlay");
  if (toggle) toggle.addEventListener("click", function () {
    setNavOpen(!document.body.classList.contains("nav-open"));
  });
  if (overlay) overlay.addEventListener("click", function () { setNavOpen(false); });
  if (sidebar) sidebar.addEventListener("click", function (e) {
    if (e.target.closest("a")) setNavOpen(false);
  });

  var collapse = document.getElementById("nav-collapse");
  var reopen = document.getElementById("nav-reopen");
  if (collapse) collapse.addEventListener("click", function () { setNavCollapsed(true); });
  if (reopen) reopen.addEventListener("click", function () { setNavCollapsed(false); });
}

function setSearchOpen(open) {
  document.body.classList.toggle("search-open", open);
  var toggle = document.getElementById("search-toggle");
  if (toggle) toggle.setAttribute("aria-expanded", open ? "true" : "false");
  if (open) {
    var input = document.getElementById("search");
    if (input) input.focus();
  }
}

function initSearchToggle() {
  var toggle = document.getElementById("search-toggle");
  if (toggle) toggle.addEventListener("click", function () {
    setSearchOpen(!document.body.classList.contains("search-open"));
  });
}

function initBranding() {
  var META = svc.meta();
  if (META.logo) {
    var mark = document.getElementById("brand-mark");
    if (mark) mark.setAttribute("src", META.logo);
  }
  if (META.favicon) {
    var link = document.querySelector('link[rel="icon"]');
    if (link) {
      link.setAttribute("href", META.favicon);
      link.removeAttribute("type");
    }
  }
}

function initRepo() {
  var META = svc.meta();
  if (!META.repo_url) return;
  var link = document.getElementById("repo-link");
  link.href = META.repo_url;
  document.getElementById("repo-name").textContent = META.repo_name || META.repo_url;
  link.hidden = false;
}

function initFooter() {
  var footer = document.getElementById("site-footer");
  if (!footer) return;
  clear(footer);
  if (svc.meta().show_about !== false) {
    footer.appendChild(el("a", { class: "about-link", href: "#/about" }, [icon("info"), "About"]));
  }
  footer.appendChild(el("div", { class: "footer-copy" }, [
    "2026 © ",
    el("a", { href: "https://github.com/datnguye", target: "_blank", rel: "noopener" }, ["@Dat Nguyen"]),
  ]));
  if (svc.meta().show_buy_me_a_coffee !== false) {
    footer.appendChild(el("a", {
      class: "bmc", href: "https://www.buymeacoffee.com/datnguye",
      target: "_blank", rel: "noopener", title: "Buy me a coffee",
    }, ["☕ Buy me a coffee"]));
  }
}

export function boot() {
  app = document.getElementById("app");
  sidebar = document.getElementById("sidebar");

  var META = svc.meta();
  document.getElementById("brand-name").textContent = META.site_name || "dbt docs";
  document.title = META.site_name || "dbt docs";
  if (META.generated_at) {
    var gen = document.getElementById("brand-generated");
    gen.textContent = "Generated " + META.generated_at;
    gen.hidden = false;
  }
  initBranding();
  initNav();
  initSearchToggle();
  initRepo();
  initFooter();
  initTheme();
  buildNav();
  buildSearch();
  initCommandPalette();
  initVersions();
  window.addEventListener("hashchange", route);
  route();
}
