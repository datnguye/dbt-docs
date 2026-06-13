/* dbdocs SPA — tier 2: service.

   Pure domain logic over the project data dict — NO DOM. Every export reads the
   normalized DATA (set once via init()) and returns plain values/strings that
   the ui tier turns into elements. Keep this file DOM-free. No build step. */

var DATA = { metadata: {}, nodes: {}, lineage: {}, columnLineage: {}, erd: {}, tree: { byDatabase: {} }, readme: "", health: { enabled: false } };
var DOWNSTREAM = null;

export function init(data) { DATA = data; DOWNSTREAM = null; }

export function meta() { return DATA.metadata; }
export function nodes() { return DATA.nodes; }
export function node(id) { return DATA.nodes[id]; }
export function tree() { return (DATA.tree && DATA.tree.byDatabase) || {}; }
export function readme() { return DATA.readme || ""; }
export function counts() { return DATA.metadata.counts || {}; }

export function shortName(id) { return String(id).split(".").pop(); }

/* The searchable text for a node in the sidebar tree filter: its table name and
   its fully-qualified database.schema.table, lowercased. Lets the tree filter
   match either "orders" or "shaman.jf.orders". DOM-free (ui does the show/hide). */
export function treeFilterText(id) {
  var n = DATA.nodes[id];
  if (!n) return String(id).toLowerCase();
  var fq = [n.database, n.schema, n.label || n.name].filter(Boolean).join(".");
  return (fq + " " + (n.label || "") + " " + id).toLowerCase();
}

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

/* Build (lazily, once per init) the inverted downstream index:
   { "srcNode.srcColLower": [{node: tgtNode, column: tgtCol}, …] }
   columnLineage keys are "{unique_id}.{column}" — unique_ids contain dots
   (e.g. model.shop.customers), so we split on the LAST dot only. */
function buildDownstreamIndex() {
  if (DOWNSTREAM !== null) return;
  DOWNSTREAM = {};
  Object.keys(DATA.columnLineage).forEach(function (tgtFull) {
    var dot = tgtFull.lastIndexOf(".");
    var tgtNode = tgtFull.slice(0, dot);
    var tgtCol = tgtFull.slice(dot + 1);
    (DATA.columnLineage[tgtFull] || []).forEach(function (src) {
      var key = src.node + "." + String(src.column).toLowerCase();
      if (!DOWNSTREAM[key]) DOWNSTREAM[key] = [];
      DOWNSTREAM[key].push({ node: tgtNode, column: tgtCol });
    });
  });
}

/* { lowercased columnName: [{node, column}, …] } for downstream dependents of
   one node's columns. Mirrors columnLineageMap but inverted: for each source
   column, which downstream output columns depend on it. Dedupes identical pairs. */
export function downstreamMap(nodeId) {
  buildDownstreamIndex();
  var prefix = nodeId + ".";
  var out = {};
  Object.keys(DOWNSTREAM).forEach(function (k) {
    if (k.indexOf(prefix) !== 0) return;
    var col = k.slice(prefix.length);
    var seen = {};
    var deduped = (DOWNSTREAM[k] || []).filter(function (u) {
      var key = u.node + "\0" + u.column;
      if (seen[key]) return false;
      seen[key] = true;
      return true;
    });
    if (deduped.length) out[col] = deduped;
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

/* Health Check accessors. DOM-free — pure data derivations.
   Shape: { enabled, dimensions:{<dim>:{issues,checked,findings}}, testResults, note } */
export function health() { return DATA.health || { enabled: false }; }

/* The six dimensions in display order (testing first), each with its issue count
   and a derived score = 1 - issues/checked (clamped). Returns [] when absent. */
var HEALTH_DIM_ORDER = ["testing", "documentation", "modeling", "structure", "performance", "governance"];
export function healthDimensions() {
  var dims = (DATA.health && DATA.health.dimensions) || {};
  return HEALTH_DIM_ORDER.filter(function (k) { return dims[k]; }).map(function (key) {
    var d = dims[key];
    var checked = d.checked || 0;
    var issues = d.issues || 0;
    var score = checked > 0 ? Math.max(0, Math.round((1 - issues / checked) * 100)) : 100;
    return { key: key, issues: issues, checked: checked, score: score, findings: d.findings || [] };
  });
}

/* The Health Check is always built; surface its nav entry + overview card when
   any dimension has findings. (Per-test pass/fail detail lives on model pages.) */
export function healthEnabled() {
  if (!(DATA.health && DATA.health.enabled)) return false;
  var dims = DATA.health.dimensions || {};
  return Object.keys(dims).some(function (k) { return (dims[k].issues || 0) > 0; });
}

/* Total issues across all dimensions (the headline number on the overview card). */
export function healthTotalIssues() {
  var dims = (DATA.health && DATA.health.dimensions) || {};
  return Object.keys(dims).reduce(function (sum, k) { return sum + (dims[k].issues || 0); }, 0);
}

/* Per-test pass/fail detail (or null when run_results.json was absent). */
export function healthTestResults() { return (DATA.health && DATA.health.testResults) || null; }
export function healthNote() { return (DATA.health && DATA.health.note) || ""; }

/* The dbt tests attached to one model, for its node page, split into data tests
   and unit tests. Returns { data:[...], unit:[...], summary } (each test sorted
   worst-status-first) or null when run_results.json was absent / the model has no
   tests. Test findings carry the tested model's short name (manifest
   attached_node / unit_test model), matched against this node's label / short id. */
var _STATUS_RANK = { fail: 0, error: 1, warn: 2, skipped: 3, pass: 4 };
function _rankStatus(s) { return _STATUS_RANK[s] != null ? _STATUS_RANK[s] : 9; }
export function testResultsForNode(nodeId) {
  var tr = DATA.health && DATA.health.testResults;
  if (!tr) return null;
  var node = DATA.nodes[nodeId];
  if (!node) return null;
  var short = shortName(nodeId);
  var data = [];
  var unit = [];
  Object.keys(tr.categories || {}).forEach(function (cat) {
    (tr.categories[cat] || []).forEach(function (f) {
      if (f.model !== node.label && f.model !== short) return;
      (f.kind === "unit" ? unit : data).push(f);
    });
  });
  if (!data.length && !unit.length) return null;
  var byStatus = function (a, b) { return _rankStatus(a.status) - _rankStatus(b.status); };
  data.sort(byStatus);
  unit.sort(byStatus);
  var summary = { pass: 0, warn: 0, fail: 0, error: 0, skipped: 0, total: 0 };
  data.concat(unit).forEach(function (f) {
    if (summary[f.status] != null) summary[f.status] += 1;
    summary.total += 1;
  });
  return { data: data, unit: unit, summary: summary };
}

/* Resolve a finding's node unique_id to its node record (or null). */
export function nodeOrNull(id) { return DATA.nodes[id] || null; }

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
