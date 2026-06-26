/* dbdocs SPA — tier 2: service.

   Pure domain logic over the project data dict — NO DOM. Every export reads the
   normalized DATA (set once via init()) and returns plain values/strings that
   the ui tier turns into elements. Keep this file DOM-free. No build step. */

var DATA = { metadata: {}, nodes: {}, lineage: {}, columnLineage: {}, erd: {}, tree: { byDatabase: {} }, readme: "", health: { enabled: false } };
var DOWNSTREAM = null;
// Cache of the per-node indexed search text, keyed by id, populated by
// searchDocs() and read by searchSnippet() (both pure, DOM-free). Reset on init().
var SEARCH_TEXT = null;
var METRIC_BY_NAME = null;
var MEASURE_TO_SM = null;
var NODES_BY_RTYPE = null;

export function init(data) { DATA = data; DOWNSTREAM = null; SEARCH_TEXT = null; METRIC_BY_NAME = null; MEASURE_TO_SM = null; NODES_BY_RTYPE = null; }

export function meta() { return DATA.metadata; }
export function nodes() { return DATA.nodes; }
export function node(id) { return DATA.nodes[id]; }
export function tree() { return (DATA.tree && DATA.tree.byDatabase) || {}; }
export function readme() { return DATA.readme || ""; }
export function counts() { return DATA.metadata.counts || {}; }

export function shortName(id) { return String(id).split(".").pop(); }

/* Flatten possibly-HTML-bearing text to plain words for the search index: drop
   tags, decode the entities mdInline emits, collapse whitespace. A node's own
   `description` is raw markdown (rendered through mdInline at display time), while
   a column's `description` is pre-escaped HTML carrying <br>; this handles both. */
function stripHtml(text) {
  return String(text == null ? "" : text)
    .replace(/<[^>]*>/g, " ")
    .replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"')
    .replace(/\s+/g, " ")
    .trim();
}

/* Above this node count we drop the SQL body (raw + compiled) from the search
   index. Indexing every model's SQL doubles that corpus into MiniSearch's
   in-memory inverted index; on a multi-thousand-model project that's tens of MB
   resident for a marginal-value field. Name/column/tag/macro coverage stays —
   only the full-SQL haystack is traded away at scale. */
var SQL_INDEX_NODE_CAP = 2000;

/* The indexed fields, ordered most→least human-relevant. The snippet builder
   walks this order to pick which matched field to excerpt, and ui mirrors it for
   the MiniSearch `fields` list. `label` is the result title (never excerpted as a
   snippet); the rest are the searchable surface: the human-facing text (name,
   description, tags) plus the structural surface a reader searches by — column
   names + descriptions, the warehouse relation, the package, the macros a model
   calls, and the model SQL (raw + compiled). Each excerptable entry carries a
   display label (what ui shows above a snippet, mkdocs-material style) so the
   dropdown can say *why* a result matched; label/name are the title itself and
   are never excerpted, so their display label is null. */
export var SEARCH_FIELDS = [
  { key: "label", label: null },
  { key: "name", label: null },
  { key: "columns", label: "Column" },
  { key: "columnDescriptions", label: "Column docs" },
  { key: "tags", label: "Tag" },
  { key: "description", label: "Description" },
  { key: "relation", label: "Relation" },
  { key: "package", label: "Package" },
  { key: "macros", label: "Macro" },
  { key: "code", label: "SQL" },
];

/* The documents fed to the full-text index (one per node). DOM-free — ui builds
   the MiniSearch instance from these. Indexes the fields in SEARCH_FIELDS; the
   SQL body (`code`) is dropped on large projects (see SQL_INDEX_NODE_CAP) to keep
   the index small. storeFields (label/resource_type/schema) are what the dropdown
   renders. The raw per-field text is cached in SEARCH_TEXT so searchSnippet() can
   excerpt the matched field without a second pass. */
export function searchDocs() {
  var N = DATA.nodes;
  var ids = Object.keys(N);
  var indexCode = ids.length <= SQL_INDEX_NODE_CAP;
  SEARCH_TEXT = {};
  return ids.map(function (id) {
    var n = N[id];
    var cols = n.columns || [];
    var doc = {
      id: id,
      label: n.label,
      name: n.name,
      resource_type: n.resource_type,
      schema: n.schema,
      description: stripHtml(n.description),
      columns: cols.map(function (c) { return c.name; }).join(" "),
      columnDescriptions: cols.map(function (c) { return stripHtml(c.description); }).join(" "),
      tags: (n.tags || []).join(" "),
      relation: n.relation_name || "",
      package: n.package || "",
      macros: (n.macros || []).map(function (m) { return m.name; }).join(" "),
      code: indexCode ? stripHtml((n.raw_code || "") + " " + (n.compiled_code || "")) : "",
    };
    SEARCH_TEXT[id] = doc;
    return doc;
  });
}

/* The MiniSearch `match` object maps each matched document-term to the list of
   fields it hit. Collapse that to the single most-relevant matched field by
   walking SEARCH_FIELDS order (skipping `label`/`name` — the title already shows
   that). Returns the SEARCH_FIELDS entry ({ key, label }), or null when only
   `label`/`name` matched and the title already explains the hit. */
function topMatchedField(match) {
  var hitFields = {};
  Object.keys(match || {}).forEach(function (term) {
    (match[term] || []).forEach(function (f) { hitFields[f] = true; });
  });
  for (var i = 0; i < SEARCH_FIELDS.length; i++) {
    var f = SEARCH_FIELDS[i];
    if (f.key === "label" || f.key === "name") continue;
    if (hitFields[f.key]) return f;
  }
  return null;
}

/* A windowed excerpt of `text` centered on the first occurrence of any matched
   term, with ~`pad` chars of context either side and ellipses where clipped.
   Case-insensitive find; returns the head of the text when no term is located
   (e.g. a fuzzy/prefix hit whose surface term differs). Pure string work. */
function excerpt(text, terms, pad) {
  var hay = String(text || "");
  if (!hay) return "";
  var lower = hay.toLowerCase();
  var at = -1;
  for (var i = 0; i < terms.length; i++) {
    var p = lower.indexOf(String(terms[i]).toLowerCase());
    if (p !== -1 && (at === -1 || p < at)) at = p;
  }
  if (at === -1) return hay.length > pad * 2 ? hay.slice(0, pad * 2) + "…" : hay;
  var start = Math.max(0, at - pad);
  var end = Math.min(hay.length, at + pad);
  return (start > 0 ? "…" : "") + hay.slice(start, end).trim() + (end < hay.length ? "…" : "");
}

/* mkdocs-material-style match context for a search hit: which field matched and
   a short excerpt of it around the query term(s), so the dropdown explains *why*
   a result is there (e.g. searching "unique" surfaces the SQL line it lives on).
   `terms` are the matched document terms (hit.terms from MiniSearch). Returns
   { field, text } or null when only the title matched. DOM-free — ui highlights
   the terms and renders. */
export function searchSnippet(id, match, terms) {
  var field = topMatchedField(match);
  if (!field) return null;
  var doc = (SEARCH_TEXT && SEARCH_TEXT[id]) || {};
  var text = excerpt(doc[field.key], terms || [], 40);
  if (!text) return null;
  return { field: field.label, text: text };
}

/* Inline search operators (mkdocs-material style) the user types into the box:
     type:<resource_type>   restrict hits to a resource_type (model/source/…)
     label:<text> / name:<text>   match only against the name/label fields,
                                   skipping the SQL/description/column noise
   Operators combine with the free-text remainder: `type:model orders` finds
   models whose text matches "orders"; `label:stg` matches names containing
   "stg". A bare query (no operators) searches everything. */
var SEARCH_OPERATOR = /(\w+):(\S+)/g;
var NAME_FIELDS = ["label", "name"];

/* Parse a raw query into MiniSearch inputs. Returns:
     { text }                the free-text remainder to search (operators stripped)
     { fields }              restrict matching to these fields, or null for all
     { filterType }          restrict hits to this resource_type, or null
     { operators }           the recognized operators (for ui to echo as chips)
   DOM-free — ui owns running mini.search() and rendering. */
export function parseSearchQuery(raw) {
  var fields = null;
  var filterType = null;
  var operators = [];
  var text = String(raw || "").replace(SEARCH_OPERATOR, function (m, key, val) {
    var k = key.toLowerCase();
    if (k === "type" || k === "resource_type") {
      filterType = val.toLowerCase();
      operators.push({ key: "type", value: filterType });
      return " ";
    }
    if (k === "label" || k === "name") {
      fields = NAME_FIELDS;
      operators.push({ key: "label", value: val });
      return " " + val + " "; // the operator's value is still the text to match
    }
    return m; // unrecognized prefix (e.g. a "schema:foo" the index doesn't carry) — leave it as a literal term
  }).replace(/\s+/g, " ").trim();
  return { text: text, fields: fields, filterType: filterType, operators: operators };
}

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

export function aboutLinks() {
  var links = DATA.metadata.about_links;
  return Array.isArray(links) && links.length > 0 ? links : [];
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
   Shape: { enabled, dimensions:{<dim>:{issues,checked,findings}}, testResults, note }

   The six dimensions in display order (testing first), each with its issue count
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

var RTYPE_ORDER = {
  model: 0, snapshot: 1, seed: 2, source: 3,
  analysis: 4, operation: 5,
  metric: 6, semantic_model: 7, saved_query: 8, unit_test: 9, exposure: 10,
};
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

export function resolveDeps(ids) {
  var N = DATA.nodes;
  return (ids || [])
    .filter(function (id) { return !!N[id]; })
    .map(function (id) {
      var n = N[id];
      return { id: id, label: n.label || n.name, rtype: n.resource_type, resolved: true };
    })
    .sort(function (a, b) { return a.label.localeCompare(b.label); });
}

export function dependsOn(id) {
  return resolveDeps((DATA.lineage.parents || {})[id]);
}

export function referencedBy(id) {
  return resolveDeps((DATA.lineage.children || {})[id]);
}

export function metricPayload(n) { return n.metric || {}; }
export function semanticModelPayload(n) { return n.semantic_model || {}; }
export function savedQueryPayload(n) { return n.saved_query || {}; }
export function unitTestPayload(n) { return n.unit_test || {}; }
export function exposurePayload(n) { return n.exposure || {}; }

/* Semantic-layer cross-link accessors — all DOM-free, resolved from the nodes dict.

   metricByName:          metric short name → { id, label } or null.
   semanticModelForMeasure: measure name → { id, label } of the owning semantic_model,
                            or null when no semantic model declares that measure.
   metricsForSemanticModel: semantic_model node id → sorted array of { id, label } for
                            every metric whose input_measures overlap with the measures
                            defined on this semantic model. */

function buildMetricByNameIndex() {
  if (METRIC_BY_NAME !== null) return;
  METRIC_BY_NAME = {};
  var N = DATA.nodes;
  Object.keys(N).forEach(function (id) {
    var n = N[id];
    if (n.resource_type === "metric") METRIC_BY_NAME[n.name] = { id: id, label: n.label || n.name };
  });
}

function buildMeasureToSmIndex() {
  if (MEASURE_TO_SM !== null) return;
  MEASURE_TO_SM = {};
  var N = DATA.nodes;
  Object.keys(N).forEach(function (id) {
    var n = N[id];
    if (n.resource_type !== "semantic_model") return;
    var measures = (n.semantic_model && n.semantic_model.measures) || [];
    measures.forEach(function (m) {
      if (m.name) MEASURE_TO_SM[m.name] = { id: id, label: n.label || n.name };
    });
  });
}

export function metricByName(name) {
  buildMetricByNameIndex();
  return METRIC_BY_NAME[name] || null;
}

export function semanticModelForMeasure(measureName) {
  buildMeasureToSmIndex();
  return MEASURE_TO_SM[measureName] || null;
}

export function metricsForSemanticModel(nodeId) {
  var sm = DATA.nodes[nodeId];
  if (!sm || sm.resource_type !== "semantic_model") return [];
  var smMeasureNames = {};
  ((sm.semantic_model && sm.semantic_model.measures) || []).forEach(function (m) {
    if (m.name) smMeasureNames[m.name] = true;
  });
  var N = DATA.nodes;
  var results = [];
  Object.keys(N).forEach(function (id) {
    var n = N[id];
    if (n.resource_type !== "metric") return;
    var inputMeasures = (n.metric && n.metric.type_params && n.metric.type_params.input_measures) || [];
    var linked = inputMeasures.some(function (name) { return smMeasureNames[name]; });
    if (linked) results.push({ id: id, label: n.label || n.name });
  });
  results.sort(function (a, b) { return a.label.localeCompare(b.label); });
  return results;
}

/* Sidebar tab bands. Mirrors the CATALOG/SEMANTIC/OTHER_RTYPES partitioning in
   the graph bundle (frontend/src/lib/data.ts) so the two apps agree on which
   resource type lands in which band. "semantic" is the dbt Semantic Layer proper
   (metrics/semantic models/saved queries); "other" is the typeless resources that
   aren't Semantic Layer (unit tests, exposures). */
var _SEMANTIC_TYPES = ["metric", "semantic_model", "saved_query"];
var _OTHER_TYPES = ["unit_test", "exposure"];
var _TAB_TYPES = { semantic: _SEMANTIC_TYPES, other: _OTHER_TYPES };
var _TAB_LABELS = { catalog: "Catalog", semantic: "Semantic", other: "Other" };
var _RTYPE_LABELS = {
  metric: "Metrics", semantic_model: "Semantic models",
  saved_query: "Saved queries", unit_test: "Unit tests", exposure: "Exposures",
};

/* Physical resource types that belong in the Catalog tab. */
var _CATALOG_RTYPES = { model: 1, seed: 1, snapshot: 1, source: 1, analysis: 1, operation: 1 };

function buildNodesByRtypeIndex() {
  if (NODES_BY_RTYPE !== null) return;
  NODES_BY_RTYPE = {};
  var N = DATA.nodes;
  Object.keys(N).forEach(function (id) {
    var rtype = N[id].resource_type;
    if (!NODES_BY_RTYPE[rtype]) NODES_BY_RTYPE[rtype] = [];
    NODES_BY_RTYPE[rtype].push(id);
  });
  Object.keys(NODES_BY_RTYPE).forEach(function (rtype) {
    NODES_BY_RTYPE[rtype].sort(function (a, b) {
      return (N[a].label || "").localeCompare(N[b].label || "");
    });
  });
}

/* Sum of node counts for a band's resource types. */
function _bandCount(types) {
  return types.reduce(function (sum, rtype) {
    return sum + (NODES_BY_RTYPE[rtype] || []).length;
  }, 0);
}

/* Up to three tab descriptors: Catalog (always) + Semantic + Other (each when its
   band has any node). Valid tab keys are "catalog", "semantic", and "other". */
export function resourceTabs() {
  buildNodesByRtypeIndex();
  var catalogCount = _bandCount(Object.keys(_CATALOG_RTYPES));
  var tabs = [{ key: "catalog", label: _TAB_LABELS.catalog, count: catalogCount }];
  ["semantic", "other"].forEach(function (key) {
    var count = _bandCount(_TAB_TYPES[key]);
    if (count > 0) tabs.push({ key: key, label: _TAB_LABELS[key], count: count });
  });
  return tabs;
}

/* Ordered sub-section descriptors for a typeless tab panel ("semantic"/"other").
   One entry per non-empty resource type in the band, in canonical display order. */
export function navSections(tabKey) {
  buildNodesByRtypeIndex();
  var sections = [];
  (_TAB_TYPES[tabKey] || []).forEach(function (rtype) {
    var ids = NODES_BY_RTYPE[rtype] || [];
    if (ids.length > 0) {
      sections.push({ rtype: rtype, label: _RTYPE_LABELS[rtype] || rtype, count: ids.length, ids: ids });
    }
  });
  return sections;
}

/* The tab a resource type lives under: "semantic", "other", or "catalog". */
export function tabForRtype(rtype) {
  if (_SEMANTIC_TYPES.indexOf(rtype) !== -1) return "semantic";
  if (_OTHER_TYPES.indexOf(rtype) !== -1) return "other";
  return "catalog";
}

/* Returns true if a node id belongs to a physical (catalog) resource type. */
export function isCatalogNode(id) {
  var n = DATA.nodes[id];
  return n ? !!_CATALOG_RTYPES[n.resource_type] : false;
}

/* Section-count helpers (DOM-free; consumed by ui nodeSection badges). */
export function columnCount(n) { return (n && n.columns) ? n.columns.length : 0; }
export function macroCount(n) { return (n && n.macros) ? n.macros.length : 0; }
