/* dbdocs SPA — tier 2: service.

   Pure domain logic over the project data dict — NO DOM. Every export reads the
   normalized DATA (set once via init()) and returns plain values/strings that
   the ui tier turns into elements. Keep this file DOM-free. No build step. */

var DATA = { metadata: {}, nodes: {}, lineage: {}, columnLineage: {}, erd: {}, tree: { byDatabase: {} }, readme: "" };

export function init(data) { DATA = data; }

export function meta() { return DATA.metadata; }
export function nodes() { return DATA.nodes; }
export function node(id) { return DATA.nodes[id]; }
export function tree() { return (DATA.tree && DATA.tree.byDatabase) || {}; }
export function readme() { return DATA.readme || ""; }
export function counts() { return DATA.metadata.counts || {}; }

export function shortName(id) { return String(id).split(".").pop(); }

/* Minimal, XSS-safe inline markdown for author-controlled config text:
   escapes HTML first, then renders links, **bold**, _italic_/*italic*, `code`.
   Returns an HTML string (use with the el() "html" attr). */
export function mdInline(text) {
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

export function parseHash(hash) {
  var raw = String(hash || "").replace(/^#\/?/, "");
  var qIndex = raw.indexOf("?");
  var path = qIndex >= 0 ? raw.slice(0, qIndex) : raw;
  var query = {};
  if (qIndex >= 0) raw.slice(qIndex + 1).split("&").forEach(function (p) {
    var kv = p.split("="); query[decodeURIComponent(kv[0])] = decodeURIComponent(kv[1] || "");
  });
  var parts = path.split("/").filter(Boolean);
  return { view: parts[0] || "overview", id: parts[1] ? decodeURIComponent(parts[1]) : null, query: query };
}

/* "snowflake · N column-lineage edges" — the build metadata shown in the
   content footer. The "Generated X" part lives in the topbar (see boot). */
export function footerMeta() {
  var parts = [];
  if (DATA.metadata.adapter_type) parts.push(DATA.metadata.adapter_type);
  parts.push(Object.keys(DATA.columnLineage).length + " column-lineage edges");
  return parts.join(" · ");
}

/* { lowercased columnName: [{node, column}, …] } for one node.
   Keyed lowercase because sqlglot normalizes identifiers to lower case while
   the catalog may report them uppercase (Snowflake/BigQuery). */
export function columnLineageMap(nodeId) {
  var prefix = nodeId + ".";
  var out = {};
  Object.keys(DATA.columnLineage).forEach(function (k) {
    if (k.indexOf(prefix) === 0) out[k.slice(prefix.length).toLowerCase()] = DATA.columnLineage[k];
  });
  return out;
}

/* Resolve a README-relative path to an absolute GitHub URL; absolute/anchor
   URLs are returned unchanged (null = leave as-is). ``kind`` is raw|blob. */
export function repoUrl(href, kind) {
  if (!href) return null;
  if (/^(https?:|mailto:|#|data:)/i.test(href)) return null;
  var base = (DATA.metadata.repo_url || "").replace(/\/$/, "");
  if (!/^https:\/\/github\.com\//.test(base)) return null;
  var path = href.replace(/^\.?\//, ""); // drop leading ./ or /
  return base + "/" + kind + "/HEAD/" + path;
}

export function pluralize(rtype) {
  var label = String(rtype).replace(/_/g, " ");
  if (/[^aeiou]y$/.test(label)) return label.slice(0, -1) + "ies"; // query → queries
  if (/(s|x|z|ch|sh)$/.test(label)) return label + "es";
  return label + "s";
}

var RTYPE_ORDER = { model: 0, snapshot: 1, seed: 2, source: 3 };
var RTYPE_ORDER_CARDS = [
  "model", "source", "seed", "snapshot", "test", "unit_test",
  "metric", "semantic_model", "exposure", "saved_query", "operation", "macro",
];

/* Node ids for a schema, sorted by resource-type then label. */
export function sortedNodeIds(ids) {
  var N = DATA.nodes;
  return ids.slice().sort(function (a, b) {
    var ra = RTYPE_ORDER[N[a].resource_type], rb = RTYPE_ORDER[N[b].resource_type];
    if (ra !== rb) return ra - rb;
    return N[a].label.localeCompare(N[b].label);
  });
}

/* Resource-type keys with a positive count, in display order. */
export function cardTypes(c) {
  var types = Object.keys(c).filter(function (t) { return c[t] > 0; });
  types.sort(function (a, b) {
    var ia = RTYPE_ORDER_CARDS.indexOf(a), ib = RTYPE_ORDER_CARDS.indexOf(b);
    if (ia < 0) ia = 999; if (ib < 0) ib = 999;
    return ia - ib || a.localeCompare(b);
  });
  return types;
}
