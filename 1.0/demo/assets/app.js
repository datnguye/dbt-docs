/* dbdocs SPA — reads window.dbdocsData (base64-injected at generate time),
   renders the catalog and per-node pages. Graphs (lineage DAG + ERDs) are
   rendered by the React Flow bundle exposed as window.dbdocsGraph. No build step
   for this file. */
(function () {
  "use strict";

  var DATA = window.dbdocsData || { metadata: {}, nodes: {}, lineage: {}, columnLineage: {}, erd: {}, tree: { byDatabase: {} } };
  var NODES = DATA.nodes || {};
  var META = DATA.metadata || {};
  var COLLIN = DATA.columnLineage || {};
  var TREE = (DATA.tree && DATA.tree.byDatabase) || {};
  var README = DATA.readme || "";

  var app = document.getElementById("app");
  var sidebar = document.getElementById("sidebar");
  var mountedGraph = null;

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "class") node.className = attrs[k];
      else if (k === "html") node.innerHTML = attrs[k];
      else if (k === "text") node.textContent = attrs[k];
      else if (k.slice(0, 2) === "on" && typeof attrs[k] === "function") node.addEventListener(k.slice(2), attrs[k]);
      else if (attrs[k] != null) node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { if (c != null) node.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return node;
  }
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
  function shortName(id) { return String(id).split(".").pop(); }

  /* Minimal, XSS-safe inline markdown for author-controlled config text:
     escapes HTML first, then renders links, **bold**, _italic_/*italic*, `code`.
     Returns an HTML string (use with the el() "html" attr). */
  function mdInline(text) {
    var s = String(text == null ? "" : text).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>');
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/(^|[\s(])[*_]([^*_]+)[*_]/g, "$1<em>$2</em>");
    return s;
  }

  var ICONS = {
    catalog: '<path d="M3 5h18v2H3zM3 11h18v2H3zM3 17h12v2H3z"/>',
    dag: '<path d="M4 4h5v5H4zM15 15h5v5h-5zM9 6h6v2H9zM16 9v6h-2V9zM6 9v6h2v-6z"/>',
    database: '<path d="M12 3c-4 0-7 1.3-7 3v12c0 1.7 3 3 7 3s7-1.3 7-3V6c0-1.7-3-3-7-3zm5 15c0 .5-1.9 1.5-5 1.5S7 18.5 7 18v-2.3c1.3.7 3.1 1.1 5 1.1s3.7-.4 5-1.1V18zm0-5c0 .5-1.9 1.5-5 1.5S7 13.5 7 13v-2.3c1.3.7 3.1 1.1 5 1.1s3.7-.4 5-1.1V13zM12 9C8.9 9 7 8 7 7.5S8.9 6 12 6s5 1 5 1.5S15.1 9 12 9z"/>',
    schema: '<path d="M10 6L8.6 7.4 13.2 12l-4.6 4.6L10 18l6-6z"/>',
    graph: '<path d="M10 20H4v-6h2v2.6l3.3-3.3 1.4 1.4L7.4 18H10zM20 10h-2V7.4l-3.3 3.3-1.4-1.4L16.6 6H14V4h6z"/>',
    model: '<path d="M3 5h18v4H3zM3 10h18v4H3zM3 15h18v4H3z" opacity=".25"/><path d="M3 5h18v4H3z"/>',
    source: '<path d="M12 3c-4 0-7 1.3-7 3v12c0 1.7 3 3 7 3s7-1.3 7-3V6c0-1.7-3-3-7-3zm5 15c0 .5-1.9 1.5-5 1.5S7 18.5 7 18v-2.3c1.3.7 3.1 1.1 5 1.1s3.7-.4 5-1.1zm0-5c0 .5-1.9 1.5-5 1.5S7 13.5 7 13v-2.3c1.3.7 3.1 1.1 5 1.1s3.7-.4 5-1.1zM12 9C8.9 9 7 8 7 7.5S8.9 6 12 6s5 1 5 1.5S15.1 9 12 9z"/>',
    seed: '<path d="M12 2C7 6 5 10 5 14a7 7 0 0014 0c0-4-2-8-7-12zm0 17a5 5 0 01-5-5c0-2.6 1.3-5.5 5-9 3.7 3.5 5 6.4 5 9a5 5 0 01-5 5z"/>',
    snapshot: '<path d="M12 8a4 4 0 104 4 4 4 0 00-4-4zm8.94 3A9 9 0 0013 3.06V1h-2v2.06A9 9 0 003.06 11H1v2h2.06A9 9 0 0011 20.94V23h2v-2.06A9 9 0 0020.94 13H23v-2zM12 19a7 7 0 117-7 7 7 0 01-7 7z"/>',
    test: '<path d="M12 1L3 5v6c0 5 3.8 9.7 9 11 5.2-1.3 9-6 9-11V5l-9-4zm-1.2 14.2l-3.5-3.5 1.4-1.4 2.1 2.1 4.6-4.6 1.4 1.4-6 6z"/>',
    unit_test: '<path d="M9 2v2h1v6.2L4.3 19A2 2 0 006 22h12a2 2 0 001.7-3L14 10.2V4h1V2H9zm3 11l3.3 5H8.7L12 13z"/>',
    metric: '<path d="M12 4a9 9 0 00-9 9 8.9 8.9 0 002 5.6l1.5-1.3A7 7 0 0112 6a7 7 0 015.5 11.3L19 18.6A8.9 8.9 0 0021 13a9 9 0 00-9-9zm-1 5v5a1.5 1.5 0 103 0c0-.6-.3-1-.7-1.3L11 9z"/>',
    semantic_model: '<path d="M12 2L2 7l10 5 10-5-10-5zm0 7.5L4.2 6 12 2.5 19.8 6 12 9.5zM2 12l10 5 10-5-2.3-1.2L12 14.5 4.3 10.8 2 12zm0 5l10 5 10-5-2.3-1.2L12 19.5 4.3 15.8 2 17z"/>',
    exposure: '<path d="M12 5C6.5 5 2 9 1 12c1 3 5.5 7 11 7s10-4 11-7c-1-3-5.5-7-11-7zm0 11a4 4 0 110-8 4 4 0 010 8zm0-6a2 2 0 100 4 2 2 0 000-4z"/>',
    saved_query: '<path d="M6 2a2 2 0 00-2 2v18l8-4 8 4V4a2 2 0 00-2-2H6zm6 4a4 4 0 013.2 6.4l2.2 2.2-1.4 1.4-2.2-2.2A4 4 0 1112 6zm0 2a2 2 0 100 4 2 2 0 000-4z"/>',
    operation: '<path d="M3 4h18v16H3V4zm2 4l4 3-4 3 1.3 1L12 11 6.3 7 5 8zm7 6h6v-1.5h-6V14z"/>',
    fullscreen: '<path d="M4 9V4h5v2H6v3H4zm11-5h5v5h-2V6h-3V4zM4 15h2v3h3v2H4v-5zm14 0h2v5h-5v-2h3v-3z"/>',
  };
  function icon(name, size) {
    var span = el("span", { class: "ic" });
    var s = size || 16;
    span.innerHTML = '<svg viewBox="0 0 24 24" width="' + s + '" height="' + s + '" fill="currentColor">' + (ICONS[name] || "") + "</svg>";
    return span;
  }

  function parseHash() {
    var raw = location.hash.replace(/^#\/?/, "");
    var qIndex = raw.indexOf("?");
    var path = qIndex >= 0 ? raw.slice(0, qIndex) : raw;
    var query = {};
    if (qIndex >= 0) raw.slice(qIndex + 1).split("&").forEach(function (p) {
      var kv = p.split("="); query[decodeURIComponent(kv[0])] = decodeURIComponent(kv[1] || "");
    });
    var parts = path.split("/").filter(Boolean);
    return { view: parts[0] || "overview", id: parts[1] ? decodeURIComponent(parts[1]) : null, query: query };
  }

  function unmountGraph() {
    if (mountedGraph && window.dbdocsGraph) {
      try { window.dbdocsGraph.unmount(mountedGraph); } catch (e) { /* ignore */ }
    }
    mountedGraph = null;
  }

  function graphMount(mode, focus) {
    var root = el("div", { class: "graph-host", id: "graph-root", "data-mode": mode });
    if (focus) root.setAttribute("data-focus", focus);
    setTimeout(function () {
      if (window.dbdocsGraph) { mountedGraph = root; window.dbdocsGraph.mount(root); }
      else root.appendChild(el("p", { class: "empty" }, ["Graph bundle not loaded."]));
    }, 0);
    return root;
  }

  function route() {
    unmountGraph();
    var r = parseHash();
    if (r.view === "node" && r.id && NODES[r.id]) renderNode(NODES[r.id]);
    else if (r.view === "dag") renderDag(r.query.focus);
    else renderOverview();
    if (r.view !== "dag") app.appendChild(contentFooter());
    highlightNav(r);
    app.focus();
    app.scrollTop = 0;
  }

  function contentFooter() {
    var foot = el("div", { class: "content-foot" });
    var left = el("span", { class: "cf-left" }, [
      icon("catalog", 14),
      el("span", {}, ["Generated by "]),
      el("a", { href: "https://github.com/datnguye/dbt-docs", target: "_blank", rel: "noopener" }, ["dbdocs"]),
    ]);
    var right = el("a", { class: "cf-top", href: "#", onclick: function (e) { e.preventDefault(); app.scrollTop = 0; } }, ["↑ Back to top"]);
    foot.appendChild(left);
    foot.appendChild(right);
    return foot;
  }

  var RTYPE_ORDER = { model: 0, snapshot: 1, seed: 2, source: 3 };

  function buildNav() {
    clear(sidebar);
    sidebar.appendChild(el("a", { class: "nav-cta", href: "#/overview", "data-nav": "overview" }, [icon("catalog"), "Catalog overview"]));
    sidebar.appendChild(el("a", { class: "nav-cta", href: "#/dag", "data-nav": "dag" }, [icon("dag"), "Lineage / DAG"]));

    Object.keys(TREE).forEach(function (db) {
      var dbDetails = el("details", { class: "nav-section nav-db", open: "" }, [
        el("summary", {}, [icon("database"), el("span", {}, [db])]),
      ]);
      Object.keys(TREE[db]).forEach(function (schema) {
        var ids = TREE[db][schema].slice().sort(function (a, b) {
          var ra = RTYPE_ORDER[NODES[a].resource_type], rb = RTYPE_ORDER[NODES[b].resource_type];
          if (ra !== rb) return ra - rb;
          return NODES[a].label.localeCompare(NODES[b].label);
        });
        var items = el("ul", { class: "nav-items" }, ids.map(function (id) {
          var n = NODES[id];
          return el("li", {}, [el("a", { href: "#/node/" + encodeURIComponent(id), "data-node": id }, [
            el("span", { class: "dot " + n.resource_type }), n.label,
          ])]);
        }));
        var schemaDetails = el("details", { class: "nav-section nav-schema", open: "" }, [
          el("summary", {}, [icon("schema"), el("span", {}, [schema])]), items,
        ]);
        dbDetails.appendChild(schemaDetails);
      });
      sidebar.appendChild(dbDetails);
    });
  }

  function highlightNav(r) {
    sidebar.querySelectorAll("[data-node], [data-nav]").forEach(function (a) { a.classList.remove("active"); });
    if (r.view === "node" && r.id) {
      var a = sidebar.querySelector('[data-node="' + (window.CSS && CSS.escape ? CSS.escape(r.id) : r.id) + '"]');
      if (a) a.classList.add("active");
    } else {
      var nav = sidebar.querySelector('[data-nav="' + (r.view === "dag" ? "dag" : "overview") + '"]');
      if (nav) nav.classList.add("active");
    }
  }

  function renderOverview() {
    clear(app);
    var counts = META.counts || {};
    app.appendChild(el("h1", {}, [META.project_name || "dbt docs"]));
    if (META.site_description) app.appendChild(el("p", { class: "description", html: mdInline(META.site_description) }, []));

    app.appendChild(el("div", { class: "cards" }, resourceCards(counts)));

    app.appendChild(el("h2", {}, ["Entity-relationship diagram"]));
    app.appendChild(graphMount("erd", null));

    if (README) app.appendChild(renderReadme(README));
  }

  function renderReadme(md) {
    var box = el("section", { class: "readme" });
    var body = el("div", { class: "markdown-body" });
    try {
      body.innerHTML = marked.parse(md, { breaks: false, gfm: true });
    } catch (e) {
      body.appendChild(el("pre", { class: "code" }, [md]));
    }
    // README paths are relative to the repo, not the docs site. Rewrite relative
    // image/link URLs to absolute GitHub URLs (raw for images, blob for links)
    // so they don't 404, and open external links in a new tab.
    body.querySelectorAll("img[src]").forEach(function (img) {
      img.src = repoUrl(img.getAttribute("src"), "raw") || img.src;
    });
    body.querySelectorAll("a[href]").forEach(function (a) {
      var fixed = repoUrl(a.getAttribute("href"), "blob");
      if (fixed) a.setAttribute("href", fixed);
      if (/^https?:/.test(a.getAttribute("href") || "")) { a.target = "_blank"; a.rel = "noopener"; }
    });
    box.appendChild(body);
    return box;
  }

  /* Resolve a README-relative path to an absolute GitHub URL; absolute/anchor
     URLs are returned unchanged (null = leave as-is). ``kind`` is raw|blob. */
  function repoUrl(href, kind) {
    if (!href) return null;
    if (/^(https?:|mailto:|#|data:)/i.test(href)) return null;
    var base = (META.repo_url || "").replace(/\/$/, "");
    if (!/^https:\/\/github\.com\//.test(base)) return null;
    var path = href.replace(/^\.?\//, ""); // drop leading ./ or /
    return base + "/" + kind + "/HEAD/" + path;
  }
  var RTYPE_ORDER_CARDS = [
    "model", "source", "seed", "snapshot", "test", "unit_test",
    "metric", "semantic_model", "exposure", "saved_query", "operation", "macro",
  ];
  function resourceCards(counts) {
    var types = Object.keys(counts).filter(function (t) { return counts[t] > 0; });
    types.sort(function (a, b) {
      var ia = RTYPE_ORDER_CARDS.indexOf(a), ib = RTYPE_ORDER_CARDS.indexOf(b);
      if (ia < 0) ia = 999; if (ib < 0) ib = 999;
      return ia - ib || a.localeCompare(b);
    });
    return types.map(function (t) { return card(counts[t], pluralize(t), t); });
  }
  function pluralize(rtype) {
    var label = String(rtype).replace(/_/g, " ");
    if (/[^aeiou]y$/.test(label)) return label.slice(0, -1) + "ies"; // query → queries
    if (/(s|x|z|ch|sh)$/.test(label)) return label + "es";
    return label + "s";
  }
  function card(num, lbl, rtype) {
    var ic = icon(ICONS[rtype] ? rtype : "graph", 18);
    ic.classList.add("card-ic", rtype);
    var head = el("div", { class: "card-head" }, [ic, el("div", { class: "num" }, [String(num)])]);
    return el("div", { class: "card" }, [head, el("div", { class: "lbl" }, [lbl])]);
  }

  function renderNode(n) {
    clear(app);
    app.appendChild(el("h1", {}, [n.label, " ", el("span", { class: "page-id" }, ["`" + n.resource_type + "`"])]));
    app.appendChild(el("div", { class: "page-id" }, [n.id]));

    var badges = el("div", { class: "badges" }, [el("span", { class: "badge rtype " + n.resource_type }, [n.resource_type])]);
    if (n.relation_name) badges.appendChild(el("span", { class: "badge" }, ["⌗ " + n.relation_name]));
    (n.tags || []).forEach(function (t) { badges.appendChild(el("span", { class: "badge tag" }, ["#" + t])); });
    var viewDag = el("a", { class: "badge", href: "#/dag?focus=" + encodeURIComponent(n.id) });
    viewDag.appendChild(icon("graph")); viewDag.appendChild(document.createTextNode(" View in DAG"));
    badges.appendChild(viewDag);
    app.appendChild(badges);

    app.appendChild(n.description
      ? el("p", { class: "description", html: mdInline(n.description) }, [])
      : el("p", { class: "description muted" }, ["No description provided."]));

    /* Columns — with an inline upstream-lineage column. */
    var colLin = columnLineageMap(n.id);
    app.appendChild(el("h2", {}, ["Columns"]));
    if (n.columns && n.columns.length) {
      var rows = n.columns.map(function (c) {
        return el("tr", {}, [
          el("td", {}, [el("code", {}, [c.name])]),
          el("td", { class: "muted" }, [c.type || ""]),
          el("td", {}, (c.tags || []).map(function (t) { return el("span", { class: "badge tag" }, ["#" + t]); })),
          el("td", { html: String(c.description || "") }, []),
          el("td", {}, upstreamChips(colLin[String(c.name).toLowerCase()])),
        ]);
      });
      app.appendChild(el("table", {}, [
        el("thead", {}, [el("tr", {}, [th("Column"), th("Type"), th("Tags"), th("Description"), th("Upstream lineage")])]),
        el("tbody", {}, rows),
      ]));
    } else {
      app.appendChild(el("p", { class: "empty" }, ["No columns found in the catalog for this entity."]));
    }

    /* Related ERD — before the transformation logic. */
    app.appendChild(el("h2", {}, ["Related ERD"]));
    app.appendChild(graphMount("erd-node", n.id));

    /* Transformation logic. */
    if (n.compiled_code || n.raw_code) {
      app.appendChild(el("h2", {}, ["Transformation logic"]));
      app.appendChild(codeTabs(n));
      if (n.macros && n.macros.length) {
        app.appendChild(el("h2", {}, ["Macros used"]));
        n.macros.forEach(function (m) {
          app.appendChild(el("details", { class: "macro" }, [
            el("summary", {}, [m.name + (m.package ? "  (" + m.package + ")" : "")]),
            el("pre", { class: "code" }, [m.sql || ""]),
          ]));
        });
      }
    }
  }
  function th(t) { return el("th", {}, [t]); }

  /* { lowercased columnName: [{node, column}, …] } for one node.
     Keyed lowercase because sqlglot normalizes identifiers to lower case while
     the catalog may report them uppercase (Snowflake/BigQuery). */
  function columnLineageMap(nodeId) {
    var prefix = nodeId + ".";
    var out = {};
    Object.keys(COLLIN).forEach(function (k) {
      if (k.indexOf(prefix) === 0) out[k.slice(prefix.length).toLowerCase()] = COLLIN[k];
    });
    return out;
  }
  function upstreamChips(upstream) {
    if (!upstream || !upstream.length) return [el("span", { class: "muted" }, ["—"])];
    return upstream.map(function (u) {
      var label = NODES[u.node] ? NODES[u.node].label : shortName(u.node);
      // Link the column (the lineage target the user cares about); the model
      // name is plain context. The href still deep-links to the upstream node.
      return el("span", { class: "up-chip" }, [
        el("span", { class: "up-model" }, [label + "."]),
        el("a", { href: "#/node/" + encodeURIComponent(u.node), title: u.node }, [u.column]),
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

  function renderDag(focusId) {
    clear(app);
    var host = graphMount("dag", focusId && NODES[focusId] ? focusId : null);
    var fsBtn = el("button", {
      class: "fs-btn", type: "button", title: "Toggle full screen",
      onclick: function () { toggleFullscreen(host); },
    }, [icon("fullscreen", 15), " Full screen"]);
    var header = el("div", { class: "page-head" }, [el("h1", {}, ["Lineage / DAG"]), fsBtn]);
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
    if (typeof MiniSearch === "undefined") return;
    var docs = Object.keys(NODES).map(function (id) {
      var n = NODES[id];
      return { id: id, label: n.label, resource_type: n.resource_type, schema: n.schema,
        description: n.description, columns: (n.columns || []).map(function (c) { return c.name; }).join(" ") };
    });
    var mini = new MiniSearch({ fields: ["label", "description", "columns"], storeFields: ["label", "resource_type", "schema"], searchOptions: { prefix: true, fuzzy: 0.2, boost: { label: 3 } } });
    mini.addAll(docs);

    function render(hits) {
      clear(results);
      if (!hits.length) { results.hidden = true; return; }
      hits.slice(0, 12).forEach(function (h) {
        results.appendChild(el("a", { href: "#/node/" + encodeURIComponent(h.id), onclick: function () { results.hidden = true; input.value = ""; } }, [
          el("span", { class: "dot " + h.resource_type }), " " + h.label,
          el("span", { class: "sr-meta" }, ["  " + h.resource_type + " · " + h.schema]),
        ]));
      });
      results.hidden = false;
    }
    input.addEventListener("input", function () {
      var q = input.value.trim();
      if (!q) { results.hidden = true; return; }
      render(mini.search(q));
    });
    input.addEventListener("focus", function () { if (input.value.trim()) render(mini.search(input.value.trim())); });
    document.addEventListener("click", function (e) { if (!results.contains(e.target) && e.target !== input) results.hidden = true; });
  }

  function initTheme() {
    var saved = null;
    try { saved = localStorage.getItem("dbdocs-theme"); } catch (e) { /* private mode */ }
    if (saved) document.documentElement.setAttribute("data-theme", saved);
    document.getElementById("theme-toggle").addEventListener("click", function () {
      var cur = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", cur);
      try { localStorage.setItem("dbdocs-theme", cur); } catch (e) { /* ignore */ }
      route();
    });
  }

  /* The version directory the site is served from, e.g. ".../latest/index.html"
     → "latest". Drops a trailing file segment (index.html) when present. */
  function currentVersionDir() {
    var parts = location.pathname.split("/").filter(Boolean);
    if (parts.length && /\.[a-z]+$/i.test(parts[parts.length - 1])) parts.pop();
    return parts.length ? parts[parts.length - 1] : "";
  }

  function initVersions() {
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
    }).catch(function () { /* unversioned build: no switcher */ });
  }

  function maybeWarnNotLatest(versions, current) {
    var latest = versions[0]; // versions.json is sorted newest-first
    if (!latest) return;
    var isLatest = current === latest.version || (latest.aliases || []).indexOf(current) >= 0;
    var defaultAlias = (META.default_version || "latest");
    if (isLatest || current === defaultAlias) return;
    var target = "../" + ((latest.aliases || []).indexOf(defaultAlias) >= 0 ? defaultAlias : latest.version) + "/index.html";
    var banner = el("div", { class: "version-warning" }, [
      el("span", {}, ["You're viewing version "]), el("strong", {}, [current || "?"]),
      el("span", {}, [" — not the latest ("]), el("strong", {}, [latest.version]), el("span", {}, [")."]),
      el("a", { href: target }, ["Go to latest →"]),
    ]);
    document.body.insertBefore(banner, document.body.firstChild);
  }

  function initRepo() {
    if (!META.repo_url) return;
    var link = document.getElementById("repo-link");
    link.href = META.repo_url;
    document.getElementById("repo-name").textContent = META.repo_name || META.repo_url;
    link.hidden = false;
  }

  function initTopbarMeta() {
    var box = document.getElementById("topbar-meta");
    if (!box) return;
    var parts = [];
    if (META.generated_at) parts.push("Generated " + META.generated_at);
    if (META.adapter_type) parts.push(META.adapter_type);
    parts.push(Object.keys(COLLIN).length + " column-lineage edges");
    box.textContent = parts.join(" · ");
    box.hidden = false;
  }

  function initFooter() {
    var footer = document.getElementById("site-footer");
    if (!footer) return;
    clear(footer);
    footer.appendChild(el("div", { class: "footer-copy" }, [
      "2026 © ",
      el("a", { href: "https://github.com/datnguye", target: "_blank", rel: "noopener" }, ["@Dat Nguyen"]),
    ]));
    if (META.show_buy_me_a_coffee !== false) {
      footer.appendChild(el("a", {
        class: "bmc", href: "https://www.buymeacoffee.com/datnguye",
        target: "_blank", rel: "noopener", title: "Buy me a coffee",
      }, ["☕ Buy me a coffee"]));
    }
  }

  function boot() {
    document.getElementById("brand-name").textContent = META.site_name || "dbt docs";
    document.title = META.site_name || "dbt docs";
    initRepo();
    initTopbarMeta();
    initFooter();
    initTheme();
    buildNav();
    buildSearch();
    initVersions();
    window.addEventListener("hashchange", route);
    route();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();
