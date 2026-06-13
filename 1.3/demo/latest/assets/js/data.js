/* dbdocs SPA — tier 1: data.

   Fetches the project data dict (the site is served over HTTP), in priority
   order:
     1. dbdocs-data.json.gz — the gzipped payload, decompressed in-browser via
        the native DecompressionStream. Keeps the transfer small on large
        projects.
     2. dbdocs-data.json — uncompressed fallback (e.g. no DecompressionStream).

   Exports loadData() → Promise<DATA>. The shape is normalized so the service
   and ui tiers never have to null-check the top-level keys. No build step. */

var EMPTY_HEALTH = { enabled: false, dimensions: {}, testResults: null, note: "" };
var EMPTY = { metadata: {}, nodes: {}, lineage: {}, columnLineage: {}, erd: {}, tree: { byDatabase: {} }, health: EMPTY_HEALTH };

function normalize(data) {
  var d = data || {};
  var health = d.health || {};
  return {
    metadata: d.metadata || {},
    nodes: d.nodes || {},
    lineage: d.lineage || {},
    columnLineage: d.columnLineage || {},
    erd: d.erd || {},
    tree: (d.tree && d.tree.byDatabase) ? d.tree : { byDatabase: {} },
    readme: d.readme || "",
    health: {
      enabled: !!health.enabled,
      dimensions: health.dimensions || {},
      testResults: health.testResults || null,
      note: health.note || "",
    },
  };
}

async function fetchGzipped(url) {
  var res = await fetch(url);
  if (!res.ok) throw new Error("not ok");
  var stream = res.body.pipeThrough(new DecompressionStream("gzip"));
  return new Response(stream).json();
}

async function fetchJson(url) {
  var res = await fetch(url);
  if (!res.ok) throw new Error("not ok");
  return res.json();
}

async function fetchData() {
  if (typeof DecompressionStream !== "undefined") {
    try { return await fetchGzipped("dbdocs-data.json.gz"); } catch (e) { /* fall through */ }
  }
  try { return await fetchJson("dbdocs-data.json"); } catch (e) { /* fall through */ }
  return EMPTY;
}

export async function loadData() {
  var data = await fetchData();
  // Expose the raw dict on window for the React Flow graph bundle, which is a
  // separate app that reads window.dbdocsData when the SPA mounts a graph.
  window.dbdocsData = data;
  return normalize(data);
}
