# Design patterns

The load-bearing patterns of `dbdocs`. Extend the established pattern instead of
inventing a parallel one. Line numbers drift — the cited **symbol** is
authoritative; grep it.

## Table of contents

- [Design patterns](#design-patterns)
  - [Table of contents](#table-of-contents)
  - [Pipeline-stage package layout](#pipeline-stage-package-layout)
    - [Theory](#theory)
    - [Example](#example)
  - [One data dict + external gzip payload](#one-data-dict--external-gzip-payload)
    - [Theory](#theory-1)
    - [Example](#example-1)
  - [SPA 3-tier ES modules (data → service → ui)](#spa-3-tier-es-modules-data--service--ui)
    - [Theory](#theory-2)
    - [Example](#example-2)
  - [Config object from dbdocs.yml](#config-object-from-dbdocsyml)
    - [Theory](#theory-3)
    - [Example](#example-3)
  - [Centralized artifact loading + the schema\_ gotcha](#centralized-artifact-loading--the-schema_-gotcha)
    - [Theory](#theory-4)
    - [Example](#example-4)
  - [Manifest-base columns, catalog-enriched](#manifest-base-columns-catalog-enriched)
    - [Theory](#theory-5)
    - [Example](#example-5)
  - [Fail-soft, parallel column-level lineage](#fail-soft-parallel-column-level-lineage)
    - [Theory](#theory-6)
    - [Example](#example-6)
  - [Windowed graph rendering](#windowed-graph-rendering)
    - [Theory](#theory-7)
    - [Example](#example-7)
  - [Pluggable graph layout (dagre / radial registry)](#pluggable-graph-layout-dagre--radial-registry)
    - [Theory](#theory-8)
    - [Example](#example-8)
  - [Layer-band DAG filter (catalog / semantic / other / all)](#layer-band-dag-filter-catalog--semantic--other--all)
    - [Theory](#theory-8b)
    - [Example](#example-8b)
  - [ERD from dbterd's built-in json target](#erd-from-dbterds-built-in-json-target)
    - [Theory](#theory-9)
    - [Example](#example-9)
  - [Bundled SPA directory resolution](#bundled-spa-directory-resolution)
    - [Theory](#theory-10)
    - [Example](#example-10)
  - [Versioned deploy without mike](#versioned-deploy-without-mike)
    - [Theory](#theory-11)
    - [Example](#example-11)
  - [Click group entrypoint](#click-group-entrypoint)
    - [Theory](#theory-12)
    - [Example](#example-12)
  - [Singleton colored logger](#singleton-colored-logger)
    - [Theory](#theory-13)
    - [Example](#example-13)
  - [Always-built artifact-derived data-dict section (Health Check)](#always-built-artifact-derived-data-dict-section-health-check)
    - [Theory](#theory-14)
    - [Example](#example-14)
  - [Node detail fields + client-derived dependency lists](#node-detail-fields--client-derived-dependency-lists)
    - [Theory](#theory-15)
    - [Example](#example-15)
  - [Static REST /api/v1 surface](#static-rest-apiv1-surface)
    - [Theory](#theory-16)
    - [Example](#example-16)
  - [First-class non-physical resource nodes](#first-class-non-physical-resource-nodes)
    - [Theory](#theory-17)
    - [Example](#example-17)
  - [Semantic-layer enum + object cleanup and client-side cross-linking](#semantic-layer-enum--object-cleanup-and-client-side-cross-linking)
    - [Theory](#theory-18)
    - [Example](#example-18)
  - [Collapsible node-page sections (`nodeSection`)](#collapsible-node-page-sections-nodesection)
    - [Theory](#theory-19)
    - [Example](#example-19)

## Pipeline-stage package layout

### Theory

The package is grouped by what each module does in the generate pipeline:
`core/` (shared foundation: config, artifact loading, exceptions, logging) →
`extract/` (derive the documentation data from artifacts: nodes, ERDs,
node-level graph, column-level lineage) → `site/` (assemble + publish: the data
dict builder, the external gzip payload, versioned deploy, and the bundled SPA).
The CLI (`cli/`) wires user commands to `site/`. Dependencies flow one way:
`extract/` and `site/` import from `core/`, never the reverse.

### Example

```python
# dbdocs/site/builder.py — site/ imports from core/ and extract/, never the reverse
from dbdocs.core.artifacts import adapter_type, load_artifacts
from dbdocs.core.config import DbDocsConfig, _resolve_within_cwd
from dbdocs.core.log import logger
from dbdocs.extract.column_lineage import ColumnLineageExtractor
from dbdocs.extract.erd import build_erd, build_erd_data, erd_algo
from dbdocs.extract.nodes import build_nodes, build_tree
from dbdocs.site.inject import strip_marker
```

- `dbdocs/core/` — `config.py`, `artifacts.py`, `exceptions.py`, `log.py`
- `dbdocs/extract/` — `nodes.py`, `erd.py`, `graph.py`, `column_lineage.py`
- `dbdocs/site/` — `builder.py`, `inject.py`, `deploy.py`, `bundle/` (the SPA:
  `index.html` + `assets/{js,css,vendor,graph}/`)
- `frontend/` — the React Flow graph app (React+TS, Vite), built into the
  committed `dbdocs/site/bundle/assets/graph/`; `src/{components,lib}`,
  `test/{unit,e2e}`, `@/*`→`src/*` path alias

## One data dict + external gzip payload

### Theory

There is exactly one renderer. `ReportBuilder.build_data()` assembles a single
dict (`metadata`, `nodes` keyed by unique_id, `lineage`, `columnLineage`, `erd`,
`tree.byDatabase`, `readme`). `generate()` stages the bundled SPA and writes the
dict as an **external** `dbdocs-data.json.gz` (plus a plain `dbdocs-data.json`
debug dump) — it is never inlined into `index.html`. The data dict stays tiny in
the HTML regardless of project size; the SPA fetches and decompresses the gzip
client-side via the browser-native `DecompressionStream`. `inject.strip_marker`
removes the `<!-- DBDOCS_DATA -->` placeholder from the staged HTML. The JSON is
serialized with `sort_keys=True` and gzipped with `mtime=0` for deterministic,
reproducible output. Because the data loads over HTTP, the site must be served
(`dbdocs serve` or any static host) — opening `index.html` from `file://` won't
fetch the payload. Do not reintroduce inlining or invent a second render path —
extend the data dict and the SPA that consumes it.

### Example

```python
# dbdocs/site/builder.py — generate(): external gzip payload, deterministic
index = out / "index.html"
index.write_text(strip_marker(index.read_text(encoding="utf-8")), encoding="utf-8")
payload = json.dumps(
    data, separators=(",", ":"), sort_keys=True, default=self._json_default
).encode("utf-8")
(out / "dbdocs-data.json").write_bytes(payload)
# mtime=0 keeps the gzip header byte-for-byte reproducible across runs.
(out / "dbdocs-data.json.gz").write_bytes(gzip.compress(payload, mtime=0))
```

- `dbdocs/site/builder.py` — `class ReportBuilder`, `def build_data`, `def generate`
- `dbdocs/site/inject.py` — `INJECT_MARKER`, `def strip_marker`
- SPA loader — `dbdocs/site/bundle/assets/js/data/data.js` (`loadData`)

## SPA 3-tier ES modules (data → service → ui)

### Theory

The bundled shell SPA (vanilla JS, no build step) is split into native ES modules
under `dbdocs/site/bundle/assets/js/`, with a strict one-way dependency
`ui → service → data` (mirroring the Python `core → extract → site` flow):
the data tier loads + normalizes the payload, the service tier is pure domain
logic over the data dict (zero DOM), the ui tier is all DOM rendering, and
`app.js` is the thin entry that wires the three. **Each tier lives in its own
folder** under `assets/js/` — `data/`, `service/`, `ui/` — so the tier boundary is
a directory boundary even when a tier is a single file; only the entry (`app.js`)
sits loose at the `assets/js/` root:

- `data/data.js` — loads + normalizes the payload, re-exposes it on `window.dbdocsData`.
- `service/service.js` — DOM-free domain logic over the data dict.
- `ui/ui.js` (the renderer), `ui/dom.js` (shared DOM primitives:
  `el`/`clear`/`icon`/`KNOWN_ICONS`), `ui/overlays.js` (command palette + toasts +
  the shared MiniSearch index).

Cross-tier imports cross a folder: `app.js` imports `./data/data.js`,
`./service/service.js`, `./ui/ui.js`; the ui-folder files import service as
`../service/service.js` and each other as `./`. Within a tier, add new modules to
that tier's folder (e.g. a new ui module imports its siblings with `./`), not a new
top-level file. `index.html` loads the entry as `<script type="module"
src="assets/js/app.js">`. The vendored UMD libs (`assets/vendor/`, e.g.
minisearch/marked) and the React Flow graph bundle (`assets/graph/`) stay classic
scripts setting globals (`MiniSearch`, `marked`, `window.dbdocsGraph`) that the
modules read directly — and `data/data.js` re-exposes the fetched payload on
`window.dbdocsData` so the graph bundle (a separate app) can read it. Keep the
service tier DOM-free and the ui tier the only DOM toucher; no bundler for the
shell. CSS lives under `assets/css/`; only `favicon.svg` sits loose in `assets/`.

### Example

```javascript
// dbdocs/site/bundle/assets/js/app.js — the entry wires the three tiers
import { loadData } from "./data/data.js";
import * as svc from "./service/service.js";
import { boot } from "./ui/ui.js";

loadData().then(function (data) {
  svc.init(data);
  boot();
});
```

- `dbdocs/site/bundle/assets/js/app.js` — the entry (loose at root)
- `dbdocs/site/bundle/assets/js/data/` — `data.js` (data tier)
- `dbdocs/site/bundle/assets/js/service/` — `service.js` (service tier)
- `dbdocs/site/bundle/assets/js/ui/` — `ui.js`, `dom.js`, `overlays.js` (ui tier)
- `dbdocs/site/bundle/index.html` — `<script type="module">` entry

## Config object from dbdocs.yml

### Theory

Site metadata is a single `DbDocsConfig` dataclass loaded from an optional
`dbdocs.yml` (all fields default, so the file is optional). The builder pulls
display metadata from `config.render_context()` (which strips build-control
fields via `_NON_METADATA_FIELDS` — `target_dir`, `output_dir`, `dialect`,
`default_version`, `dbterd`, `readme`, plus `logo`/`favicon` which are *source*
paths, not display metadata) rather than hardcoding values. Unknown keys /
malformed YAML raise `DbDocsConfigError` — never a bare `Exception`. `target_path`
(artifacts in) and `output_path` (site out) resolve relative dirs against the cwd
at access time. Relative `target_dir`/`output_dir` values that escape the cwd via
`..` raise `DbDocsConfigError`; absolute paths are accepted as-is. The same
`..`-escape check applies to relative `readme`/`logo`/`favicon` paths — an
escaping path (or a missing file) is silently treated as absent (fail-soft). For
`logo`/`favicon`, `generate()` copies the resolved file into `assets/` and
injects its *deployed* URL into the metadata; the SPA swaps the header mark +
favicon, falling back to the bundled defaults when unset.

### Example

```python
# dbdocs/core/config.py — strip build-control fields from display metadata;
# reject relative paths that escape the cwd
def render_context(self) -> dict:
    context = asdict(self)
    for field_name in self._NON_METADATA_FIELDS:
        context.pop(field_name, None)
    return context

def _resolve_within_cwd(value: str, field_name: str) -> Path:
    base = Path.cwd().resolve()
    candidate = Path(value)
    resolved = (candidate if candidate.is_absolute() else (base / candidate)).resolve()
    if not candidate.is_absolute() and resolved != base and base not in resolved.parents:
        raise DbDocsConfigError(f"{field_name} {value!r} escapes the project directory ({base}).")
    return resolved
```

- `dbdocs/core/config.py` — `class DbDocsConfig`, `_NON_METADATA_FIELDS`, `def load`, `def render_context`, `def output_path`, `def _resolve_within_cwd`
- `dbdocs/site/builder.py` — `def _stage_branding`, `def _copy_branding_asset`
- `dbdocs/core/exceptions.py` — `DbDocsConfigError`, `LineageError`, `DeployError`
- `dbdocs/core/config.py` — `show_about` / `about_links` (display-metadata fields, *not* in `_NON_METADATA_FIELDS`, so they flow through `render_context()` → `metadata`); the distinction is the point — build-control fields are stripped, display-metadata like these is kept
- `dbdocs/site/bundle/assets/js/service/service.js` — `aboutLinks` (DOM-free accessor, guards `Array.isArray`)
- `dbdocs/site/bundle/assets/js/ui/ui.js` — `renderAbout` (the `#/about` page: JSON API section + CTA links), `initFooter` (pinned About link gated by `show_about !== false`), route branch `r.view === "about"`

## Centralized artifact loading + the schema\_ gotcha

### Theory

All dbt-artifact access goes through `dbdocs/core/artifacts.py`: `load_artifacts`
returns dbterd-parsed `(manifest, catalog)` with schema-version relaxation;
`adapter_type` reads the warehouse from metadata (the default sqlglot dialect).
**Critical:** `artifact_parser` aliases the `schema` field to `schema_` to
avoid clobbering Pydantic's `BaseModel.schema()`, so `entity.schema` is a *bound
method*, not the value. Always read `schema_`; `db_schema(entity)` centralizes
that with safe `_unknown` fallbacks. Never read `.schema` off a parsed node.

### Example

```python
# dbdocs/core/artifacts.py — read schema_ (the alias), not .schema (a bound method)
def db_schema(entity: Any) -> "tuple[str, str]":
    database = getattr(entity, "database", None) or UNKNOWN
    schema = getattr(entity, "schema_", None) or UNKNOWN
    return str(database), str(schema)


def load_artifacts(target_path: str) -> "tuple[Any, Any]":
    manifest = file.read_manifest(
        path=target_path, version=artifact_version(target_path, "manifest")
    )
    catalog = file.read_catalog(path=target_path, version=artifact_version(target_path, "catalog"))
    return manifest, catalog
```

- `dbdocs/core/artifacts.py` — `def load_artifacts`, `def adapter_type`, `def db_schema`, `NODE_PREFIXES`

## Manifest-base columns, catalog-enriched

### Theory

A node's columns come from the **manifest** (the dbt YAML decides which columns
are documented and carries their description/tags/`data_type`); the **catalog**
only *enriches* — it supplies the warehouse-confirmed type and appends any
columns the manifest never documented. It never replaces the manifest, so a model
absent from a stale/partial `catalog.json` still renders every documented column
(just without a warehouse type). Manifest columns come first in manifest order;
catalog-only columns are appended. The catalog keys columns by the warehouse's
casing (Snowflake upper-cases them) while the manifest keeps the modeled casing,
so the type lookup is **case-insensitive** and the displayed name stays the
manifest's casing. Type falls back to the manifest `data_type` when the catalog
has no entry. Don't reintroduce a catalog-driven loop that drops manifest columns
when the catalog is empty.

Each column record also carries its **defined dbt data tests** (e.g.
`not_null`, `unique`, `accepted_values`) as a sorted `tests: [test_type, ...]`
list. The list is built once per `build_nodes` call by
`build_column_tests_index(manifest)` (in `dbdocs/extract/tests_index.py`), which
scans every `test.*` node that has both an `attached_node` and a `column_name`
and groups test types by column, lowercase. The same primitive,
`manifest_test_node_metadata(node)`, is shared with `HealthCheckExtractor` —
both consumers read `test_metadata.name`, `attached_node`, and `column_name`
from a manifest test node through this single helper. Table-level tests (no
`column_name`) are intentionally excluded from the per-column index.

A companion helper, `manifest_test_node_details(node)`, extracts the
`(description, kwargs)` the SPA shows on the per-model Tests table —
`description` is the test's YAML docstring and `kwargs` is the user-supplied
`test_metadata.kwargs` (e.g. `accepted_values: [...]`) minus the `_KWARGS_HIDE`
noise keys (model/column already shown, plus severity/where/limit/warn_if/
error_if). It is read by `HealthCheckExtractor._resolve_details` so the test
detail and the per-column index stay one definition.

### Example

```python
# dbdocs/extract/nodes.py — manifest-base columns, catalog type enriches (case-insensitive);
# column_tests (from build_column_tests_index) annotates each column with its defined tests
catalog_by_lower = {str(name).lower(): col for name, col in catalog_columns.items()}
columns = []
seen_lower = set()
for name, manifest_column in manifest_columns.items():
    lower = str(name).lower()
    seen_lower.add(lower)
    catalog_column = catalog_by_lower.get(lower)
    col_type = getattr(catalog_column, "type", None) or getattr(manifest_column, "data_type", None)
    columns.append(_column_entry(name, manifest_column, col_type or "", column_tests.get(lower, [])))
# ... catalog-only columns appended afterwards
```

- `dbdocs/extract/nodes.py` — `def _columns`, `def _column_entry`
- `dbdocs/extract/tests_index.py` — `def build_column_tests_index`, `def manifest_test_node_metadata`, `def manifest_test_node_details`
- `dbdocs/extract/health/extractor.py` — `_resolve_metadata` (imports `manifest_test_node_metadata` + `manifest_test_node_details`)

## Fail-soft, parallel column-level lineage

### Theory

`ColumnLineageExtractor` parses each model's **compiled** SQL with sqlglot,
qualifies it against a schema built from the catalog (so `SELECT *` and
unqualified columns resolve), and traces each output column to its source
columns. The heavy lifting lives in a vendored, self-contained lineage module
(`_sqlglot_lineage.py`) so we don't depend on sqlglot's version-unstable internal
lineage API. **Per-model failures are caught, logged, and skipped** — one
unparseable model must never sink the whole `generate`; the run reports how many
were skipped via `self.skipped`.

**Scope is built once per model, not once per column.** Parse + qualify +
`build_scope` is the expensive half of lineage and is identical for every output
column of a model. `_extract_model_columns` calls `prepare_scope(compiled, …)`
once and passes the resulting `scope` to `lineage(column, …, scope=scope)` per
column — turning the per-model cost from `O(columns × parse)` into
`O(parse + columns)`.

**Parallel above a model-count threshold.** `extract()` builds a list of
**picklable** per-model work tuples (`unique_id`, compiled SQL, output columns,
schema dict, dialect, relation index) — never the Pydantic manifest/catalog. For
small projects it runs `_extract_model_task` serially; at or above
`_PARALLEL_THRESHOLD` models it fans the (CPU-bound) sqlglot work across a
`ProcessPoolExecutor`. Each worker gets its own pickled copy of the schema, so
sqlglot's in-place qualify mutations can't contaminate other workers — serial and
parallel results are identical. The leaf-mapping helpers (`_map_table`,
`_leaf_columns`) are module-level functions taking the relation index as an arg,
not instance methods, so they pickle cleanly. Don't reintroduce a per-column
re-parse, and don't pass manifest/catalog objects across the process boundary.

### Example

```python
# dbdocs/extract/column_lineage.py — serial under the threshold, pool above it
work = self._work_items()
if not work:
    return {}
if len(work) >= _PARALLEL_THRESHOLD:
    results = self._extract_parallel(work)
else:
    results = (_extract_model_task(item) for item in work)

# _extract_model_columns: scope built once, reused per column
scope = prepare_scope(compiled, schema=schema, dialect=dialect)
for column in output_columns:
    root = lineage(column, compiled, dialect=dialect, scope=scope)
    # ...
```

- `dbdocs/extract/column_lineage.py` — `class ColumnLineageExtractor`, `def extract`, `def _work_items`, `def _extract_parallel`, `_extract_model_task`, `_extract_model_columns`, `_PARALLEL_THRESHOLD`
- `dbdocs/extract/_sqlglot_lineage.py` — `def prepare_scope`, `def lineage`, `def to_node` (vendored; omitted from coverage)

## Windowed graph rendering

### Theory

The React Flow graph app (`frontend/`, React+TS, built into the committed
`assets/graph/` bundle) keeps 1000s-of-models graphs from freezing the browser,
but the **DAG and ERD use different strategies** — don't conflate them:

- **DAG — window before layout.** The DAG renders only a focal node's bounded
  neighborhood (`neighborhood(data, focus, maxDepth)`) or the dropdown-filtered
  set; when unfocused and over `MAX_UNFOCUSED_DAG_NODES`, it shows a "focus a
  node" placeholder instead of laying out every node. `buildDagFlow(data,
  keepIds)` filters to the kept set up front, so dagre never sees the full graph.
- **ERD — render all, lazily.** The overview ERD has **no node cap**: it lays out
  *every* table (schema-filtered) so the whole snowflake is visible, and relies on
  React Flow's `onlyRenderVisibleElements` (set only for the ERD) to mount just the
  nodes in the viewport — so DOM cost is bounded by what's on screen, not by N.
  Removing `onlyRenderVisibleElements` would regress this (and the per-column
  both-side handles make each ERD node ~2× the DOM, so the lazy render is
  load-bearing). Focusing a table (search box) narrows to its FK neighborhood
  (`erdNeighborhood`); the per-node ERD (`erd-node`) shows a placeholder naming
  the configured dbterd `erd_algo` (with a docs link) when no relationships are
  detected.

**Compact overview, full model-page.** `buildErdFlow(..., compact)` controls per
node column rendering: the overview ERD draws nodes **compact** (only PK/FK
columns, with a "+N more columns" row — `visibleColumns` / `erdRowCount`) so a
wide fact table stays a few rows tall and the radial snowflake reads; the
model-page ERD (`erd-node`) passes `compact = false` so a single model and its
1-hop neighbors show **every** column and edge (the neighborhood is small, so the
DOM stays bounded). The unfocused-ERD empty state is **split**: zero ERD nodes
shows the `erd_algo` "no relationships detected" placeholder (`erdNoTables`),
while a schema filter that matched nothing shows "clear the schema filter"
(`erdFilterEmpty`) — don't collapse the two.

**Focused DAG — top-down + tighter fit.** A focused DAG (`isDag && focusId`)
overrides the default left-right dagre rank direction with `"TB"` (top-to-bottom)
via the layout registry's `opts.direction` (the `dagre` engine forwards it to
`rankdir`; the unfocused DAG and the ERD radial layout ignore it), and uses the
tighter `DAG_FIT_FOCUSED` (`padding: 0.2`) for the initial / data-change /
fullscreen fit instead of the full-graph default. Don't hardcode `rankdir` at the
call site — thread it through `opts.direction` so the engine stays the single
layout authority (see **Pluggable graph layout**).

**`#/erd` jumps to the overview ERD.** The overview ERD lives on the
`renderOverview` page, but `#/erd` is a first-class hash route that renders that
page and then `_scrollToErd()`s the `#erd-heading` into view (and moves focus
there, `preventScroll`, for keyboard/AT users) — scroll target by element id, not
by matching the heading's English text. It carries the same `erd_focus`/
`erd_schema` query params as the overview default branch, so an ERD deep link
round-trips. Its producer is the command palette's "Entity-relationship diagram"
quick action (`action: "erd"`) — there is deliberately **no pinned nav CTA** for
it (the ERD lives on the overview page); `highlightNav` marks the **overview** nav
item active. Don't add a route branch without a producer — an orphaned `#/…` view
is dead UI.

Graph-UI changes need a Node rebuild (`task frontend:build`) of the committed
bundle.

### Example

```typescript
// frontend/src/components/GraphApp.tsx — window before layout; placeholder over the cap
const dagKeep = useMemo(() => {
  if (!isDag) return null;
  if (focusId) return neighborhood(data, focusId);
  const ids = Object.keys(data.nodes ?? {}).filter((id) => {
    const rec = data.nodes[id];
    if (rtype && rec.resource_type !== rtype) return false;
    if (schema && rec.schema !== schema) return false;
    return true;
  });
  if (ids.length > MAX_UNFOCUSED_DAG_NODES) return new Set<string>();
  return new Set(ids);
}, [isDag, focusId, data, rtype, schema]);
```

- `frontend/src/lib/data.ts` — `neighborhood`, `buildDagFlow`, `erdNeighborhood`, `buildErdFlow` (`compact`), `erdRowCount`
- `frontend/src/components/nodes/ErdTableNode.tsx` — `visibleColumns` (compact key-column filter + "+N more")
- `frontend/src/components/GraphApp.tsx` — `MAX_UNFOCUSED_DAG_NODES` (DAG-only), `dagKeep`, `erdKeep`, `erdNoTables`, `erdFilterEmpty`, `erdNodeEmpty`, `onlyRenderVisibleElements={isErd}`, `DAG_FIT_FOCUSED`, `dagFitOptions`, `direction: isDag && focusId ? "TB" : undefined`
- `frontend/src/lib/layout.ts` — `LayoutEngine` `opts.direction`, `layoutNodes(sized, edges, direction)` (`rankdir` override)
- `dbdocs/site/bundle/assets/js/ui/ui.js` — `route()` `r.view === "erd"` branch, `_scrollToErd` (`#erd-heading` id + focus), `renderOverview` (`erd-heading` id)
- `dbdocs/site/bundle/assets/js/ui/overlays.js` — the "Entity-relationship diagram" quick action (`action: "erd"`) — the `#/erd` producer
- `dbdocs/site/builder.py` / `dbdocs/extract/erd.py` — `erd_algo` (metadata)

## Pluggable graph layout (dagre / radial registry)

### Theory

The graph app picks a layout **by name from a registry**, not with a hardcoded
`if`. `frontend/src/lib/layout.ts` defines a `LayoutEngine` type
(`(sized, edges, opts?{centerId}) => Positions`), a name→engine map, and
`registerLayout(name, engine)` / `resolveLayout(name)` (falls back to `dagre` for
an unknown name). Two engines are registered at module load: **`dagre`** (the
hierarchical LR layout — the DAG and any non-centered case) and **`radial`** (the
ERD "snowflake": focus/hub at the center, FK neighbors fanning out on concentric
rings by BFS hop). `GraphApp` selects `isDag ? "dagre" : "radial"`; the radial
engine centers on the explicit focus or, unfocused, on `mostConnected(...)` (the
highest-degree table). Add a new layout by registering it — don't fork the
selection logic. The DAG stays dagre (flow direction matters); radial is
ERD-only.

Radial sizing keeps a tall fact table from overlapping a small focus: ring radius
clears the **larger of the neighbor's width/height** half-extent, and the
alternating half-slot angle offset is suppressed for rings of ≤2 (it would stack
the pair vertically over the center).

### Example

```typescript
// frontend/src/lib/layout.ts — engines register by name; resolve picks one
registerLayout("dagre", (sized, edges) => layoutNodes(sized, edges));
registerLayout("radial", (sized, edges, opts) => {
  const center = opts?.centerId ?? mostConnected(sized, edges);
  return center ? radialLayout(center, sized, edges) : layoutNodes(sized, edges);
});

// frontend/src/components/GraphApp.tsx — pick by name, never a hardcoded fn
const positions = resolveLayout(isDag ? "dagre" : "radial")(
  flow.sizes, asLayoutEdges(flow.edges), { centerId },
);
```

- `frontend/src/lib/layout.ts` — `LayoutEngine`, `registerLayout`, `resolveLayout`, `mostConnected`, `radialLayout`, `layoutNodes`
- `frontend/src/components/GraphApp.tsx` — `resolveLayout(isDag ? "dagre" : "radial")`

## Layer-band DAG filter (catalog / semantic / other / all)

### Theory

The DAG view filters in **two stages from a single layer source of truth**, never
with parallel rtype lists. A `DagLayer` (`"catalog" | "semantic" | "other" |
"all"`) picks a coarse band of resource types; an optional multi-select narrows
within it. The layer→types mapping lives **once** in `frontend/src/lib/data.ts`
as **three disjoint** `ReadonlySet`s:

- `CATALOG_RTYPES` — physical, database/schema-bearing: model/source/seed/
  snapshot/analysis/operation.
- `SEMANTIC_RTYPES` — the dbt **Semantic Layer proper**: metric/semantic_model/
  saved_query (and *only* these three — MetricFlow constructs).
- `OTHER_RTYPES` — typeless resources that are **not** Semantic Layer:
  unit_test/exposure.

`layerTypes(layer)` returns the matching band, or `ALL_RTYPES` (the union) for
`"all"`. The shell SPA's sidebar mirrors the **same** three bands
(`_SEMANTIC_TYPES`/`_OTHER_TYPES`/`_CATALOG_RTYPES` in `service.js`), so the graph
bundle and the sidebar agree on which resource type lands in which band without
duplicating membership. **Don't** lump unit_test/exposure under "semantic" — they
are the `"other"` band. Don't hardcode a layer's types at a call site; read
`layerTypes(layer)`.

`dagKeep` composes the filters in order: a **focused node wins** (its full
`neighborhood(data, focusId)` renders regardless of layer/type so cross-layer
edges stay visible); unfocused, it filters `data.nodes` by `layerTypes(layer)`
**first**, then the multi-select `rtype` Set (when non-empty), then `schema` —
still windowing before layout (over `MAX_UNFOCUSED_DAG_NODES` it returns an empty
Set and shows the placeholder, per **Windowed graph rendering**). The empty state
is split by `hasFilter` (`rtype.size > 0 || schema || layer !== "catalog"`):
`dagFilterEmpty` ("clear the filter") vs `dagTooLarge` (the "focus a node"
cap placeholder) — don't collapse the two.

The controls are real form elements: `LayerControl` is a segmented `<button>`
group of four bands (`aria-pressed`, `role="group"`); `RtypeDropdown` is a
`<button>`-triggered panel of `<label><input type="checkbox">` rows
(`aria-expanded`/`aria-controls`, Escape + click-outside close with focus restored
to the trigger). The `"all"` band renders three labelled groups
(Catalog/Semantic/Other via `CATALOG_ORDER`/`SEMANTIC_ORDER`/`OTHER_ORDER`); a
single band renders one flat list. `rtype` is a `Set<string>`, and
`buildDagHash(focus, rtype, schema, layer)` serializes it as a sorted comma list,
**omitting `layer` when it equals the `"catalog"` default** so common URLs stay
clean; the hash is written via `history.replaceState` (the no-`hashchange` remount
trick). Switching layer resets the `rtype` Set (a stale cross-band type can't
survive the band change), guarded by a mounted-ref so the reset doesn't fire on
initial mount.

Graph-UI changes need a Node rebuild (`task frontend:build`) of the committed
bundle.

### Example

```typescript
// frontend/src/lib/data.ts — one layer→types source of truth, three disjoint bands
export function layerTypes(layer: DagLayer): ReadonlySet<ResourceType> {
  if (layer === "semantic") return SEMANTIC_RTYPES;
  if (layer === "other") return OTHER_RTYPES;
  if (layer === "all") return ALL_RTYPES;
  return CATALOG_RTYPES;
}

// frontend/src/components/GraphApp.tsx — layer band first, then multi-select, then schema
const allowed = layerTypes(layer);
const ids = Object.keys(data.nodes ?? {}).filter((id) => {
  const rec = data.nodes[id];
  if (!allowed.has(rec.resource_type as ResourceType)) return false;
  if (rtype.size > 0 && !rtype.has(rec.resource_type)) return false;
  if (schema && rec.schema !== schema) return false;
  return true;
});
if (ids.length > MAX_UNFOCUSED_DAG_NODES) return new Set<string>();
```

- `frontend/src/lib/types.ts` — `DagLayer`, the extended `ResourceType` union
- `frontend/src/lib/data.ts` — `CATALOG_RTYPES`, `SEMANTIC_RTYPES`, `OTHER_RTYPES`, `layerTypes`, `buildDagFlow`
- `frontend/src/components/GraphApp.tsx` — `LayerControl` (4 bands), `RtypeDropdown`, `CATALOG_ORDER`/`SEMANTIC_ORDER`/`OTHER_ORDER`, `dagKeep`, `hasFilter`, `dagFilterEmpty`/`dagTooLarge`, `buildDagHash`, `MAX_UNFOCUSED_DAG_NODES`
- `frontend/src/main.tsx` — `parseLayer`, `data-layer` dataset → `initialLayer`
- `dbdocs/site/bundle/assets/js/service/service.js` — `_SEMANTIC_TYPES`/`_OTHER_TYPES`/`_CATALOG_RTYPES`, `resourceTabs`, `navSections`, `tabForRtype` (the sidebar mirror)
- `frontend/test/unit/layerTypes.test.ts`, `frontend/test/unit/RtypeDropdown.test.tsx`

## ERD from dbterd's built-in json target

### Theory

The SPA renders its ERD with React Flow, which needs structured node/edge data
— not the diagram *text* dbterd's other targets emit. dbterd ≥ 1.28 ships a
**built-in, schema-validated `json` target** that emits `{nodes, edges,
metadata}`; `build_erd(target="json")` forces it, and `build_erd_data` maps that
into the SPA's `{nodes, edges}`. Do **not** reintroduce a custom
`@register_target("json")` adapter — dbterd owns this contract now. Two dbterd
quirks `build_erd_data` patches (verify after any dbterd bump with
`task frontend:e2e`):

1. **Short-name edge ids.** With `entity_name_format` configured, dbterd emits
   edge `from_id`/`to_id` as the *formatted entity name* (e.g. `orders`), not the
   full unique_id (e.g. `model.jaffle_shop.orders`). `_resolve_edge_id` resolves
   those back through a `name_to_id` map (built from each node's `name`) so the
   SPA's `source`/`target` always reference a valid node `id`. An id already in
   `node_ids` passes through untouched (the no-`entity_name_format` case).
2. **Missing FK flags.** Some algos (e.g. `model_contract`) don't set
   `is_foreign_key` on node columns even when those columns appear in FK edges.
   `_backfill_fk_flags` sets `is_foreign_key=True` on any column named in an
   edge's `from_columns` (the FK/child side), indexed by node id so it's O(1) per
   column per edge.

**SPA edge direction:** `source` = the referenced/parent side (dbterd `to_id`),
`target` = the FK/child side (dbterd `from_id`). The graph bundle's per-column
connector handles (`buildErdFlow` in `frontend/src/lib/data.ts`) resolve each
handle against whichever endpoint actually owns the named column (`owned(...)`),
so a join whose FK/PK columns differ in name still lands on the right rows.

### Example

```python
# dbdocs/extract/erd.py — official {nodes, edges}; resolve short names + back-fill FK flags
payload = json.loads(erd.get_erd())
raw_nodes = payload.get("nodes", [])
nodes = [_build_node(n) for n in raw_nodes]
node_ids = {n["id"] for n in nodes}
name_to_id = {n.get("name"): n["id"] for n in raw_nodes if n.get("name")}
edges = [_build_edge(e, i, node_ids, name_to_id) for i, e in enumerate(payload.get("edges", []))]
_backfill_fk_flags(nodes, edges)
return {"nodes": nodes, "edges": edges}
```

- `dbdocs/extract/erd.py` — `def build_erd` (forces `target="json"`), `def build_erd_data`, `def _build_node`, `def _build_edge`, `def _resolve_edge_id`, `def _backfill_fk_flags`
- `frontend/src/lib/data.ts` — `buildErdFlow` (consumes `source`/`target`/`from_columns`/`to_columns`/`is_foreign_key`; `owned()` picks the handle column each endpoint owns)
- `pyproject.toml` — `dbterd>=1.28` (the built-in `json` target floor)

## Bundled SPA directory resolution

### Theory

`ReportBuilder` resolves the bundled SPA dir relative to the package
(`dbdocs/site/bundle/`) from `__file__`, so the assets are found whether running
from source or an installed wheel. `generate()` removes the output dir first
(`rmtree`) before `copytree`ing the whole bundle (shell + `assets/` incl.
vendored UMD libs) — guaranteeing a clean build with no stale assets from a
prior run. This is why the `artifacts` glob in `pyproject.toml` must ship
`dbdocs/site/bundle/**/*`.

### Example

```python
# dbdocs/site/builder.py — bundle dir resolves from __file__; clean rmtree + copytree
BUNDLE_DIR = Path(__file__).resolve().parent / "bundle"

# generate():
out = Path(output_dir) if output_dir else Path(self.config.output_path)
if out.exists():
    rmtree(out)
out.mkdir(parents=True)
copytree(src=BUNDLE_DIR, dst=out, dirs_exist_ok=True)
```

- `dbdocs/site/builder.py` — `BUNDLE_DIR = Path(__file__).resolve().parent / "bundle"`, `def generate`

## Versioned deploy without mike

### Theory

Versioning is a plain directory layout any static host serves as-is — no
external tooling. `deploy()` generates into `site/<version>/`, maintains
`site/versions.json` (moving a `--alias` to the new version and off others), and
copies the build to each alias dir. The SPA's version switcher is gated on an
explicit `metadata.versioned` flag: `generate(versioned=False)` (the default,
plain-generate path) writes `False`, while `deploy()` passes `versioned=True`.
The service tier's `isVersioned()` returns that flag; `initVersions()` in ui.js
early-exits when it is falsy, so a `generate`'d site makes zero `versions.json`
requests (no 404 noise). A `deploy`'d site always has a sibling `versions.json`,
so the fetch is safe. `--push` is opt-in (off by default, outward-facing) and
shells git to publish `gh-pages`, raising `DeployError` on a non-zero exit. Both
`deploy()` and `delete()` validate that `version` and every `alias` are safe
single path segments matching `^[A-Za-z0-9._-]+$` and are not `.` or `..`,
raising `DeployError` on violation — this includes aliases read back from
`versions.json` during deletion (preventing path traversal from a tampered index).

### Example

```python
# dbdocs/site/deploy.py — validate segments, then generate with versioned=True
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")

def _validate_segment(value: str, kind: str) -> None:
    if not _SAFE_SEGMENT.match(value) or value in {".", ".."}:
        raise DeployError(
            f"Invalid {kind} {value!r}: must match ^[A-Za-z0-9._-]+$ and not be '.' or '..'."
        )

# deploy():
_validate_segment(version, "version")
if alias is not None:
    _validate_segment(alias, "alias")
ReportBuilder(config).generate(output_dir=str(version_dir), versioned=True)

# dbdocs/site/builder.py — generate() writes the flag into metadata
data["metadata"]["versioned"] = versioned   # False by default, True from deploy()
```

```javascript
// service.js — DOM-free accessor
export function isVersioned() { return !!DATA.metadata.versioned; }

// ui.js — initVersions() gates the fetch on the flag
function initVersions() {
  if (!svc.isVersioned()) return;
  fetch("../versions.json")...
}
```

- `dbdocs/site/deploy.py` — `def deploy`, `def _upsert_version`, `def _push_gh_pages`, `def _validate_segment`
- `dbdocs/site/builder.py` — `def generate` (`versioned` kwarg, `metadata["versioned"]`)
- `dbdocs/site/bundle/assets/js/service/service.js` — `isVersioned`
- `dbdocs/site/bundle/assets/js/ui/ui.js` — `initVersions` (early-exit guard)

## Click group entrypoint

### Theory

The CLI is a `click.group` with `no_args_is_help=True` and a `--version` option;
subcommands attach via `@dbdocs.command(name=...)`. Commands are `generate`,
`serve` (stdlib `http.server` over the output dir), and `deploy`. dbdocs-level
errors are re-raised as `click.ClickException` for clean CLI output.
`dbdocs/main.py` is the thin console-script shim (`main()` → `cli.dbdocs()`).

### Example

```python
# dbdocs/cli/main.py — the click group; dbdocs errors → ClickException
@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
    no_args_is_help=True,
    epilog="Specify one of these sub-commands and you can find more help from there.",
)
@click.version_option(__version__)
@click.option("-c", "--config", "config_path", default=None, help="Path to dbdocs.yml.")
@click.pass_context
def dbdocs(ctx, config_path):
    """Alternative dbt docs site: dbt docs + ERD + column-level lineage."""
    try:
        ctx.obj = DbDocsConfig.load(config_path)
    except DbDocsError as exc:
        raise click.ClickException(str(exc)) from exc
```

- `dbdocs/cli/main.py` — `@click.group(...) def dbdocs`, `@dbdocs.command(name="generate")`
- `dbdocs/main.py` — `def main`

## Singleton colored logger

### Theory

A single module-level `logger` (name `"dbdocs"` — deliberately not `"dbterd"`,
to avoid colliding with the dbterd library's logger) with an ANSI-color
formatter, guarded so handlers attach only once (`if len(logger.handlers) ==
0`). Import and use it; do not create new loggers.

### Example

```python
# dbdocs/core/log.py — one named logger, handlers attached only once
logger = logging.getLogger("dbdocs")
logger.setLevel(logging.DEBUG)
logger.propagate = False

if len(logger.handlers) == 0:  # pragma: no cover - import-time handler guard
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(LogFormatter())
    logger.addHandler(ch)
```

- `dbdocs/core/log.py` — `class LogFormatter`, `logger = logging.getLogger("dbdocs")`

## Always-built artifact-derived data-dict section (Health Check)

### Theory

Some data-dict sections are derived from an **extra artifact** (e.g.
`run_results.json`) that isn't always present. The section is **always built**
(no opt-in flag) and **fail-soft to empty** when the artifact is missing; the SPA
decides whether to *surface* it based on whether it holds anything. The pattern:

1. An optional path field on `DbDocsConfig` (e.g. `run_results: str | None =
   None`) added to `_NON_METADATA_FIELDS` (build-control, not display metadata).
   No `bool` enable-flag — the section is unconditional.
2. A `--run-results` CLI option (path override) that writes back to the config
   object before `ReportBuilder` is called — same as the existing `--dialect`
   pattern. No `--evaluator/--no-evaluator` on/off flag.
3. A dedicated extractor class in `dbdocs/extract/` (e.g. `HealthCheckExtractor`)
   that reads the artifact and returns a plain dict ready for the data dict. The
   artifact is parsed with **`artifact-parser`** (`artifact_parser.dbt.parse_run_results`),
   a versioned-Pydantic parser covering run-results schema v1–v6 — *not* dbterd
   and *not* the manifest Pydantic parser; a schema/enum rename in a new dbt
   release then surfaces as a caught error rather than a silent mis-read. The
   parsed `Result.status` is an enum (`.value` is the plain string — never `str()`
   it). **Fail-soft**: every IO + parse error is caught with a *specific* type
   (`FileNotFoundError`/`OSError`, `json.JSONDecodeError`, and the parser's
   `ArtifactParserError`/Pydantic `ValidationError`), logged, and returns an
   empty-but-enabled section — a missing file must never sink `generate`. Health
   works from an **ordinary `dbt build`/`dbt test`** — no extra dbt package: every
   `test.*` result is a finding, bucketed by test type (`not_null`/`unique` →
   integrity, `relationships` → referential, `accepted_values` → validity, …). The
   type isn't in `run_results.json` — it lives in the **manifest**
   (`test_metadata.name`, `column_name`, `attached_node`), so the extractor is
   passed the dbterd-parsed manifest and enriches each finding from it, falling
   back to inferring the type from the `unique_id` when no manifest/node is found.
4. `ReportBuilder.build_data()` always resolves the path (via `_resolve_within_cwd`
   with fail-soft on escape, defaulting to `<target_dir>/<artifact>`), calls the
   extractor, and adds the top-level `health` key unconditionally.
5. The SPA's `data.js normalize()` defaults the key (`health: {enabled: false}`)
   so the ui tier never crashes if it's absent in an old payload. `service.js`
   exposes pure accessors (DOM-free); **`healthEnabled()` keys off `summary.total
   > 0`** (not a config flag) — so an empty section (no `run_results.json`) means
   no nav entry / overview card, while a populated one surfaces them. `ui.js`
   guards rendering behind `healthEnabled()`.

Do not invent a second data-hand-off channel. Extend the single data dict.

### Example

```python
# dbdocs/site/builder.py — health is always built; fail-soft path resolution
data = {
    # ... other sections ...
    "health": HealthCheckExtractor(
        self._resolve_run_results_path(), manifest
    ).extract(),
}

def _resolve_run_results_path(self) -> str:
    if self.config.run_results:
        try:
            return str(_resolve_within_cwd(self.config.run_results, "run_results"))
        except DbDocsConfigError:
            logger.warning("run_results path %r escapes the project directory ...", ...)
    return str(Path(self.config.target_path) / "run_results.json")
```

```python
# dbdocs/extract/health/extractor.py — parse via artifact-parser; specific exception types only
def _load_results(self) -> "list | None":
    try:
        text = self._path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("Health check: run_results.json not found at %s — skipping.", ...)
        return None
    except OSError as exc:
        logger.warning("Health check: could not read %s: %s — skipping.", ...)
        return None
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("Health check: could not parse %s: %s — skipping.", ...)
        return None
    try:
        run_results = parse_run_results(raw)  # artifact_parser.dbt
    except (ArtifactParserError, ValidationError) as exc:
        logger.warning("Health check: %s is not a valid run_results artifact ...", ...)
        return None
    return list(run_results.results)
```

The health data dict has three parts: `dimensions` (the six DPE dimensions, each
`{issues, checked, findings}`, computed from the manifest by the rule engine),
`testResults` (the per-test pass/fail detail from `run_results.json`, or `null`),
and `note` (set when `run_results.json` was absent). The SPA renders a **scorecard
+ collapsible dimension** page; the per-test detail is shown on each **model
page** (split into Data tests / Unit tests), not on the Health page. Each test
result's `status` is normalized through `_status_value`: the parsed enum's
`.value` is lowercased, and the adapter success aliases in `_PASS_ALIASES`
(`"success"`/`"ok"`, emitted by Snowflake and a few others for an asserting test
that returned 0 rows) collapse to `"pass"` so the summary pills tally correctly.
The per-test type/column/description/kwargs come from the manifest via the shared
`manifest_test_node_metadata` / `manifest_test_node_details` helpers (see
**Manifest-base columns**), falling back to inferring the type from the
`unique_id` when no manifest node is found.

The rule engine is **a package**: the dimension modules live under
`extract/health/rules/dimensions/{testing,modeling,documentation,structure,performance,governance}.py`,
with a shared `base.py` (public `finding()`/`docs_url()`, `DEFAULT_THRESHOLDS`,
`LAYER_PREFIXES`, `NON_PHYSICAL` — no cross-module private imports), `registry.py`
(the impl: `DIMENSION_RULES` + the plugin API), and a **thin** `__init__.py`
facade (re-export only — no impl). It is **configurable + pluggable** via
`dbdocs.yml` `health:` — `thresholds` (read through `graph.threshold(name)`),
`disable` / `disable_dimensions`, and `rules_module`; plus the `dbdocs.health_rules`
entry point. `register_rule(dimension)` (decorator or call) appends to the
module-global `DIMENSION_RULES` — tests must `reset_rules()` between cases (an autouse conftest
fixture does this).

- `dbdocs/core/config.py` — `run_results`, `health` fields, `_NON_METADATA_FIELDS` (no `evaluator` flag — health is always built)
- `dbdocs/cli/main.py` — `--run-results` path override (no on/off flag)
- `dbdocs/extract/health/extractor.py` — `class HealthCheckExtractor`, `TEST_CATEGORIES`, `_is_test_result`, `_is_unit_test`, `_resolve_metadata`, `_resolve_details`, `_unit_test_model`, `_status_value`, `_PASS_ALIASES`, `parse_run_results` (from `artifact_parser.dbt`)
- `dbdocs/extract/health/dimensions.py` — `class ManifestGraph` (adjacency + `threshold`/`layer`/`materialization`/`access`/`tests_for`), `class DimensionAnalyzer` (config wiring, plugin load, disable lists)
- `dbdocs/extract/health/rules/` — `base.py` (public `finding`, `docs_url`, `DEFAULT_THRESHOLDS`, `LAYER_PREFIXES`, `NON_PHYSICAL`), `dimensions/` (one module per dimension), `registry.py` (`DIMENSION_RULES`, `register_rule`, `reset_rules`, `load_entry_point_rules`, `load_rules_module`, `ENTRY_POINT_GROUP`), `__init__.py` (thin re-export facade)
- `pyproject.toml` — `artifact-parser[dbt]` runtime dependency
- `docs/dbdocs-demo.yml` — the documented `health:` block (all thresholds + every rule name under `disable`) + default `run_results`
- `tests/fixtures/jaffle_shop/run_results.json` — sanitized plain-dbt run (29 tests) whose ids match the committed manifest (co-located with the artifacts so the default `<target_dir>/run_results.json` resolves)
- `dbdocs/site/builder.py` — `def _resolve_run_results_path`, `def build_data` (health key, `config=config.health`)
- `dbdocs/site/bundle/assets/js/data/data.js` — `normalize()` health default (`dimensions`/`testResults`/`note`)
- `dbdocs/site/bundle/assets/js/service/service.js` — `healthDimensions`, `healthEnabled` (issues>0), `healthTotalIssues`, `testResultsForNode` (data/unit split)
- `dbdocs/site/bundle/assets/js/ui/ui.js` — `renderHealth`, `healthScorecard`, `healthDimensionSection`, `_testsSection` (model-page Tests node-section)

## Node detail fields + client-derived dependency lists

### Theory

Each node record in the data dict carries manifest-declared detail fields beyond
the core identity columns: **`materialization`** (from `config.materialized`),
**`meta`** (node-level, falling back to `config.meta`), **`access`**, **`group`**,
**`contract_enforced`** (from `contract.enforced`), **`version`** /
**`latest_version`**, **`owner`** (resolved to a display string: `name` then
`email`), **`original_file_path`**, **`patch_path`**, and **`stats`** (catalog
node stats filtered to `include=True` entries — warehouse statistics like row
count, last modified).

All reads are defensive (`getattr(..., None) or default`) so a missing attribute
on any node type (source, seed, snapshot, exposure) always returns a safe empty
value.

**Depends-on and Referenced-by are never re-shipped in the payload.** The lineage
graph (`DATA.lineage.parents` / `DATA.lineage.children`) is already in the data
dict. `service.js` exposes `dependsOn(id)` and `referencedBy(id)` that derive
these lists client-side — zero payload growth. `ui.js` renders them as chip lists
with resource-type color dots and deep links (`#/node/<id>`).

### Example

```python
# dbdocs/extract/nodes.py — defensive getattr reads; catalog stats filtered to include=True
def _catalog_stats(catalog_node: Any) -> dict:
    raw = getattr(catalog_node, "stats", {}) or {} if catalog_node else {}
    return {
        k: {"label": getattr(v, "label", k), "value": getattr(v, "value", None)}
        for k, v in raw.items()
        if getattr(v, "include", False)
    }

"materialization": getattr(config, "materialized", None) or "",
"meta": getattr(entity, "meta", None) or getattr(config, "meta", None) or {},
"contract_enforced": bool(getattr(contract, "enforced", False)),
"stats": _catalog_stats(catalog_node),
```

```javascript
// dbdocs/site/bundle/assets/js/service/service.js — derive deps from lineage, zero payload growth
export function dependsOn(id) {
  return resolveDeps((DATA.lineage.parents || {})[id]);
}
export function referencedBy(id) {
  return resolveDeps((DATA.lineage.children || {})[id]);
}
```

- `dbdocs/extract/nodes.py` — `_catalog_stats`, `_owner_string`, `_node_record` (all new detail fields)
- `dbdocs/site/bundle/assets/js/service/service.js` — `dependsOn`, `referencedBy`, `resolveDeps` (public — `ui.js` reads it cross-module)
- `dbdocs/site/bundle/assets/js/ui/ui.js` — `nodeDetailsBlock`, `depChipList`, `_depSection` (wraps deps in nodeSection)
- `dbdocs/site/bundle/assets/css/style.css` — `.node-details`, `.dep-chips`, `.dep-chip`

## Static REST /api/v1 surface

### Theory

`generate()` writes a static, addressable JSON API tree under `<output_dir>/api/v1/`
from the **same `data` dict** assembled for the SPA payload — not a second render
path. It gives external consumers a stable, addressable JSON API: any static host
serves the files as-is, and AI agents / MCP servers can fetch them headless
without parsing HTML.

Layout:

- `api/v1/schema/` — four JSON Schema (draft 2020-12) files, one per doc type,
  written from the `SCHEMA_FILES` dict in `dbdocs/site/api_schema.py`. They are
  hand-authored module-level literals (not generated from runtime data) so they
  are the normative contract. Schemas use `additionalProperties: true` on
  extension points so per-resource-type sub-dicts and future fields never fail
  validation.
- `api/v1/index.json` — entry-point index: `{$schema, metadata, counts,
  generated_at, nodes: [{$schema, id, name, label, resource_type, database,
  schema, description, node_url}]}`. `node_url` is relative (`nodes/<id>.json`)
  so the tree works on any base path.
- `api/v1/nodes/<unique_id>.json` — one file per node: the full node record
  enriched with `depends_on` (the node's parents list from `lineage.parents`),
  `referenced_by` (children), `columnLineage` (this node's upstream columns slice
  of `data["columnLineage"]`), and `column_referenced_by` (this node's downstream
  columns slice — which other columns depend on this node's columns). Both slices
  are bucketed by node id **once** up front (reusing `_index_column_lineage` on
  the upstream map and on `_invert_column_lineage(...)` for the downstream map),
  keeping `_write_api` linear on a 3000-model project instead of O(N²).
  Self-contained for an agent: single fetch, both directions, no graph traversal.
- `api/v1/lineage.json` — `{$schema, ...data["lineage"]}` (edges, parents, children).
- `api/v1/health.json` — `{$schema, ...data["health"]}`.
- `api/v1/column-lineage.json` — whole-graph column lineage: `{$schema, skipped, edges, children}`.
  `edges` is the upstream map verbatim (each key lists what it derives from);
  `children` is its inversion built by `_invert_column_lineage` (each upstream
  column lists the downstream columns that depend on it — the impact-analysis
  direction, mirroring `lineage.children` at the node level). `skipped` is the
  count of models `ColumnLineageExtractor` could not parse, captured in
  `data["columnLineageMeta"]["skipped"]` — a sibling key of `data["columnLineage"]`
  (not inside it, since the flat map's keys are all `unique_id.column`; mixing in
  a meta key would corrupt per-node bucketing).

`_invert_column_lineage(flat_map)` is a module-level pure helper O(edges): for
every `src.col → [{node, column}...]`, it appends `{node: owner, column: col}` to
`children["<upstream_node>.<upstream_col>"]`. The SPA's `normalize()` ignores
`columnLineageMeta` (it's not in the normalized shape) without crashing.

Every emitted doc carries a **relative `$schema` self-pointer** (e.g.
`"schema/index.schema.json"` for index.json, `"../schema/node.schema.json"` for
per-node files) so any JSON-Schema-aware tool can validate docs without a
network round-trip and the pointers survive versioned/aliased deploy base paths.
All files use `_serialize()` — the same deterministic serialization (compact
separators, `sort_keys=True`, `_json_default`) as the main gzip payload, so
output is reproducible across runs. The api/ dir is created after the
`rmtree`+`copytree` bundle stage so it is never clobbered by re-runs; it is
generated at runtime, not shipped in the wheel (the `pyproject.toml` artifacts
glob covers only `dbdocs/site/bundle/**/*`). Unique_ids that contain `/` or `\`
are skipped with a warning — dbt unique_ids never contain them, but the guard
prevents any path-traversal write.

A **drift test** wired into the 100%-coverage gate validates that every emitted
doc passes `Draft202012Validator.validate()` against its schema, that each schema
is itself valid (`check_schema`), and that the `SCHEMA_FILES` constants exactly
match what was written on disk — so a data-dict shape change that breaks the
schema surfaces as a test failure before a release.

### Example

```python
# dbdocs/site/api_schema.py — hand-authored normative schema literals
COLUMN_LINEAGE_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "column-lineage.schema.json",
    "required": ["$schema", "skipped", "edges", "children"],
    # edges / children: additionalProperties → array of {node, column} items
}
SCHEMA_FILES: dict = {
    "index.schema.json": INDEX_SCHEMA,
    "node.schema.json": NODE_SCHEMA,
    "lineage.schema.json": LINEAGE_SCHEMA,
    "health.schema.json": HEALTH_SCHEMA,
    "column-lineage.schema.json": COLUMN_LINEAGE_SCHEMA,
}

# dbdocs/site/builder.py — _invert_column_lineage: O(edges) downstream map
def _invert_column_lineage(column_lineage: dict) -> dict:
    children: dict = {}
    for key, upstream_refs in column_lineage.items():
        owner_node, owner_col = str(key).rsplit(".", 1)
        for ref in upstream_refs:
            upstream_key = f"{ref['node']}.{ref['column']}"
            children.setdefault(upstream_key, []).append({"node": owner_node, "column": owner_col})
    return children

# build_data(): capture extractor instance to read .skipped after .extract()
cl_extractor = ColumnLineageExtractor(manifest, catalog, dialect=dialect)
column_lineage = cl_extractor.extract()
data["columnLineageMeta"] = {"skipped": cl_extractor.skipped}

# _write_api(): bucket both directions once; write column-lineage.json
inverted_column_lineage = _invert_column_lineage(raw_column_lineage)
column_referenced_by_node = _index_column_lineage(inverted_column_lineage)
# enriched["column_referenced_by"] = column_referenced_by_node.get(node_id, {})
column_lineage_doc = {
    "$schema": "schema/column-lineage.schema.json",
    "skipped": column_lineage_meta.get("skipped", 0),
    "edges": raw_column_lineage,
    "children": inverted_column_lineage,
}
```

- `dbdocs/site/api_schema.py` — `INDEX_SCHEMA`, `NODE_SCHEMA` (`column_referenced_by`), `LINEAGE_SCHEMA`, `HEALTH_SCHEMA`, `_COLUMN_REF_ITEM`, `COLUMN_LINEAGE_SCHEMA`, `SCHEMA_FILES`
- `dbdocs/site/builder.py` — `_UNSAFE_ID_CHARS`, `def _index_column_lineage`, `def _invert_column_lineage`, `def _serialize`, `def _write_api`, `def generate`, `def build_data` (`cl_extractor`, `columnLineageMeta`)
- `pyproject.toml` — `jsonschema>=4.20` in the `dev` dependency group
- `tests/unit/site/test_builder.py` — `test_generate_writes_api_v1_files`, `test_api_index_lists_all_nodes`, `test_api_per_node_file_is_self_contained`, `test_api_output_is_deterministic`, `test_api_unsafe_id_skipped`, `test_api_schema_files_are_written`, `test_api_schema_files_are_valid_draft2020`, `test_api_doc_schema_pointer_exists`, `test_api_node_doc_schema_pointer_exists`, `test_api_doc_validates_against_schema`, `test_api_node_docs_validate_against_node_schema`, `test_api_schema_literals_match_emitted_files`, `test_invert_column_lineage_*`, `test_build_data_has_column_lineage_meta`, `test_generate_writes_column_lineage_json`, `test_column_lineage_json_*`, `test_api_per_node_has_column_referenced_by`, `test_api_per_node_column_referenced_by_slice`, `test_api_node_docs_with_column_referenced_by_validate_against_schema`

## First-class non-physical resource nodes

### Theory

Every dbt resource type that a user would want to navigate — metrics, semantic
models, saved queries, unit tests, exposures, analyses, and operations — is a
first-class entry in the `nodes` dict, not just a count. `build_nodes`
(`dbdocs/extract/nodes.py`) handles two categories:

**Physical resources** (models, seeds, snapshots, sources, analyses, operations)
are emitted through `_node_record`, which carries database/schema from the
manifest and the full column/code/stats envelope. Analyses and operations share
the same envelope but always receive `catalog_node=None` (they have no catalog
entry).

**Typeless resources** (metrics, semantic_models, saved_queries, unit_tests,
exposures) live in their own `manifest.<collection>` mappings and are emitted by
dedicated builder functions (`_metric_record`, `_semantic_model_record`,
`_saved_query_record`, `_unit_test_record`, `_exposure_record`). Each wraps
`_base_envelope` (id, name, label, resource_type, package, description, tags,
meta) and adds a type-specific payload sub-dict keyed by resource_type (e.g.
`metric: {type, label, filter, type_params}`, `exposure: {type, owner_name,
owner_email, maturity, url}`). Since they have no real database/schema they carry
`database=""` / `schema=""` and are **excluded from `build_tree`**. Navigation is
via a horizontal **resource-type tab strip** in the sidebar (not a fake db bucket).

**Sidebar 3-tab strip.** The sidebar mirrors the same three bands as the graph's
**Layer-band DAG filter** — `catalog`, `semantic` (the dbt Semantic Layer proper:
metrics/semantic models/saved queries), and `other` (typeless non-SL: unit
tests/exposures). `service.js` exposes `resourceTabs()` (up to 3 entries:
`{key:"catalog", ...}` always, plus `{key:"semantic", ...}` / `{key:"other", ...}`
each when its band has any node), `navSections(tabKey)` (ordered
`[{rtype, label, count, ids}]` for the non-empty types in that band), and
`tabForRtype(rtype)` (which band a resource type lives under). The band membership
lives once in `_SEMANTIC_TYPES`/`_OTHER_TYPES`/`_CATALOG_RTYPES` — **don't** put
unit_test/exposure under semantic. `ui.js` builds a `<div role="tablist">` with
`<button role="tab">` elements; the active tab is persisted via
`localStorage("dbdocs-nav-tab")` — valid values are `"catalog"`, `"semantic"`, and
`"other"` (`_NAV_TAB_KEYS`); any other stored value (e.g. an old per-type key)
falls back to `"catalog"`. The catalog tab renders the db→schema tree
(`_buildCatalogPanel`); a typeless tab renders one `<details open>` per section
(`_buildTypelessPanel(tabKey)`, same `nav-section nav-sl-section` idiom). On a
deep-link to a typeless node, `highlightNav` auto-switches to
`svc.tabForRtype(n.resource_type)` and force-opens the matching sub-section.
`filterNav` filters both the db-tree schema groups and the typeless sub-sections.

**`LineageGraph`** includes all surfaced types in its default node_ids so that
`parents`/`children` maps — consumed by `dependsOn`/`referencedBy` in the SPA —
resolve cross-type edges (e.g. metric → semantic_model → model). The visual DAG
is unchanged because the graph bundle's `data-rtype` filter drops non-physical
nodes from the rendered view. Macros are excluded from both nodes and the
lineage graph: a real project carries hundreds of package-vendor macros that
would flood the nav, and macros already render inline under models that depend on
them via `macros_used`.

**`service.js`** extends `RTYPE_ORDER` to rank the new types after physical ones
(analysis/operation before semantic-layer types), so `sortedNodeIds` never
returns `undefined`. Payload accessors (`metricPayload`, `semanticModelPayload`,
etc.) are DOM-free pure functions in the service tier.

**`ui.js renderNode`** dispatches by `resource_type` before the existing physical
branch: each new type gets a dedicated render function (`renderMetricNode`,
`renderSemanticModelNode`, `renderSavedQueryNode`, `renderUnitTestNode`,
`renderExposureNode`) plus a shared `renderCodeOnlyNode` for analysis/operation.
Physical resources (model, source, seed, snapshot) route to the renamed
`renderPhysicalNode` — behavior unchanged. New pages reuse `el`, `icon`,
`codeTabs`, and `nodeDepsBlock`; they do not render columns, tests, or an ERD
panel (types that have none of those). **Duplicate "Depends on" rule:** never call
`depChips(n.depends_on_nodes, …)` on typeless nodes — `nodeDepsBlock(n)` already
shows both upstream (`dependsOn`) and downstream (`referencedBy`) from the lineage
graph. Using both was a bug that rendered the section twice.

The `COLLECTION_ATTRS` dict (maps id-prefix → manifest attribute name, e.g.
`"saved_query." → "saved_queries"`) is the single authoritative mapping shared
between `nodes.py` (emit loop) and `graph.py` (default node_ids + _lookup).
It lives in `core/artifacts.py` alongside `NODE_PREFIXES` and `CODE_ONLY_PREFIXES`
so that both modules import it from `core` — never from each other. Don't derive
attribute names by string mutation — `saved_query.rstrip(".") + "s"` produces
`saved_querys`, not `saved_queries`.

### Example

```python
# dbdocs/core/artifacts.py — public constants shared across extract modules
CODE_ONLY_PREFIXES = ("analysis.", "operation.")
COLLECTION_ATTRS: "dict[str, str]" = {
    "metric.": "metrics",
    "semantic_model.": "semantic_models",
    "saved_query.": "saved_queries",
    "unit_test.": "unit_tests",
    "exposure.": "exposures",
}
```

```python
# dbdocs/extract/nodes.py — typeless resources carry empty database/schema; excluded from tree
_PHYSICAL_PREFIXES = NODE_PREFIXES + CODE_ONLY_PREFIXES + ("source.",)

# _metric_record — base envelope + type-specific payload; no synthetic db/schema
record = _base_envelope(unique_id, entity, "metric")
record["database"] = ""
record["schema"] = ""
record["metric"] = { "type": ..., "label": ..., "filter": ..., "type_params": ... }

# build_tree — skips any id not starting with a physical prefix
def build_tree(nodes):
    for unique_id, record in nodes.items():
        if not str(unique_id).startswith(_PHYSICAL_PREFIXES):
            continue
        # ... only physical nodes reach the db/schema grouping
```

```javascript
// service.js — resourceTabs for the sidebar 3-tab strip
export function resourceTabs() {
  // [{key:"catalog", label:"Catalog", count:N}, {key:"semantic", ...}, {key:"other", ...}]
  // semantic / other tabs are omitted when their band count == 0
}
export function navSections(tabKey) { /* [{rtype, label, count, ids}] for the band */ }
export function tabForRtype(rtype) { /* "semantic" | "other" | "catalog" */ }
export function isCatalogNode(id) { /* true for physical rtypes */ }

// ui.js — tab strip with keyboard nav + localStorage persistence
export function buildNav() {
  // ... nav-cta links (overview/dag/health) ...
  // tabStrip: role="tablist", each tab role="tab" aria-selected
  // renderSidebarBody(tabKey): catalog → db tree, else → _buildTypelessPanel(tabKey)
}
function highlightNav(r) {
  if (r.view === "node" && r.id && !svc.isCatalogNode(r.id)) {
    activateNavTab(svc.tabForRtype(n.resource_type)); // auto-switch to the node's band
  }
}
```

- `dbdocs/core/artifacts.py` — `CODE_ONLY_PREFIXES`, `COLLECTION_ATTRS` (public; both modules import from here)
- `dbdocs/extract/nodes.py` — `_PHYSICAL_PREFIXES`, `_COLLECTION_PREFIXES`, `_base_envelope`, `_metric_record`, `_metric_type_params`, `_semantic_model_record`, `_sm_items`, `_saved_query_record`, `_export_item`, `_fixture_rows` (unit-test given/expect data table, capped at `_FIXTURE_ROW_CAP` with the uncapped `total` kept), `_FIXTURE_ROW_CAP`, `_unit_test_given_item`, `_unit_test_record`, `_exposure_record`, `build_nodes` (extended), `build_tree` (physical-only)
- `dbdocs/extract/graph.py` — `_default_node_ids` (extended), `_lookup` (extended)
- `dbdocs/site/bundle/assets/js/service/service.js` — `RTYPE_ORDER` (extended), `_SEMANTIC_TYPES`/`_OTHER_TYPES`/`_TAB_TYPES`/`_CATALOG_RTYPES`, `resourceTabs`, `navSections`, `tabForRtype`, `isCatalogNode`, `metricPayload`, `semanticModelPayload`, `savedQueryPayload`, `unitTestPayload`, `exposurePayload`
- `dbdocs/site/bundle/assets/js/ui/ui.js` — `buildNav` (3-tab strip), `_NAV_TAB_KEYS`, `activateNavTab`, `renderSidebarBody`, `_buildTypelessPanel`, `filterNav`, `highlightNav` (auto-switch via `tabForRtype` + force-open sub-section), `renderNode` (dispatch), `renderPhysicalNode`, `renderCodeOnlyNode`, `renderMetricNode`, `renderSemanticModelNode`, `renderSavedQueryNode`, `renderUnitTestNode` (given/expect data tables via `fixtureBody`), `renderExposureNode`
- `tests/conftest.py` — `metric_entity`, `semantic_model_entity`, `saved_query_entity`, `unit_test_entity`, `exposure_entity`

## Semantic-layer enum + object cleanup and client-side cross-linking

### Theory

`artifact_parser` represents many semantic-layer fields as **Pydantic enums** and
**named sub-objects** rather than plain strings. Two module-level helpers in
`nodes.py` centralise the cleanup before any value lands in the data dict:

- **`_enum_value(val)`** — returns `val.value` when the value has a `value`
  attribute (a Pydantic enum), otherwise returns `val` as-is (plain strings pass
  through unchanged). Apply whenever you read a field that could be an enum:
  `metric.type`, `dimension.type`, `entity.type`, `measure.agg`,
  `exposure.type`/`maturity`, `export_config.export_as`.
- **`_object_name(val)`** — resolves a metric/measure/entity reference to a plain
  display name across the three shapes `artifact_parser` versions emit: an object
  with `.name` (a `Measure`/`MetricInput`) → `val.name`; a literal string repr
  like `Entity('customer')` / `Dimension("foo")` → the quoted inner name (matched
  by the module-level `_ENTITY_REPR` regex); a plain string → as-is. Apply
  whenever a `type_params` field might be a named object or such a repr rather than
  a plain string: `measure`, `numerator`, `denominator`, and items in `metrics` /
  `input_measures` / `group_by` / `where` lists.

The export config gotcha: dbt's `Config58` stores the target schema in
**`schema_name`**, not the `schema_`/`schema` aliases used by manifest nodes.
`_export_item` reads `schema_name` first, then falls back to `schema_` (the
manifest-node alias), so it works regardless of artifact version.

`_sm_items` applies `str(_enum_value(val))` to every extracted attribute, so all
dimension/entity/measure type enums are unwrapped in one place.

**Cross-linking is resolved client-side from the nodes dict, not pre-shipped.**
Three DOM-free accessors in `service.js` drive the linking:

- **`metricByName(name)`** — scans nodes for `resource_type === "metric"` with
  matching `name`; returns `{id, label}` or `null`. Used by the metric
  `type_params.metrics` list and the saved-query metrics list.
- **`semanticModelForMeasure(measureName)`** — scans nodes for
  `resource_type === "semantic_model"` that declares the named measure; returns
  `{id, label}` or `null`. Used by the metric `type_params.measure` /
  `numerator` / `denominator` / `input_measures` fields.
- **`metricsForSemanticModel(nodeId)`** — returns sorted `[{id, label}]` of all
  metrics whose `type_params.input_measures` overlap with the semantic model's
  declared measures (the reverse direction — "Metrics built on this model").

`input_measures` is the reliable cross-link key (Python always emits it from
`type_params.input_measures`; it's present even for simple/ratio/derived types and
lists every measure the metric touches, not just the primary one). `measure` /
`numerator` / `denominator` are the human-readable singular forms and link to the
owning semantic model.

**`ui.js`** renders the cross-links as `dep-chip` anchors with resource-type
color dots, consistent with the existing `depChips` style:

- `renderMetricNode` — `type_params.metrics` → `metricNameLink` chips (deep
  links to the referenced metric pages); `type_params.measure` / `numerator` /
  `denominator` / `input_measures` → `measureNameLink` chips (deep link to the
  owning semantic model, showing `<sm_label>.<measure_name>`).
- `renderSemanticModelNode` — "Metrics built on this model" section using
  `metricsForSemanticModel`.
- `renderSavedQueryNode` — metrics list → `metricNameLink` chips instead of plain
  `<code>` tags.

### Example

```python
# dbdocs/extract/nodes.py — enum + object cleanup helpers
def _enum_value(val: Any) -> Any:
    return val.value if hasattr(val, "value") else val

def _object_name(val: Any) -> str:
    name = getattr(val, "name", None)
    return str(name) if name is not None else str(val)

# _metric_type_params — extract .name from Measure/MetricInput objects
for attr in ("measure", "numerator", "denominator"):
    val = getattr(type_params, attr, None)
    if val is not None:
        result[attr] = _object_name(val)
for list_attr in ("metrics", "input_measures"):
    items = getattr(type_params, list_attr, None)
    if items:
        result[list_attr] = [_object_name(m) for m in items]

# _export_item — schema_name (Config58) not schema_ (manifest-node alias)
raw_schema = (
    getattr(config, "schema_name", None)
    or getattr(config, "schema_", None)
    or ""
)
raw_export_as = getattr(config, "export_as", None)
"export_as": str(_enum_value(raw_export_as)) if raw_export_as is not None else "",
```

```javascript
// dbdocs/site/bundle/assets/js/service/service.js — cross-link resolution, DOM-free
export function metricByName(name) { /* scan nodes, return {id, label} or null */ }
export function semanticModelForMeasure(measureName) { /* scan semantic_models for measure name */ }
export function metricsForSemanticModel(nodeId) {
  /* input_measures overlap: which metrics use this sm's measures? */
  var smMeasureNames = {};
  ((sm.semantic_model && sm.semantic_model.measures) || []).forEach(...);
  // key off input_measures — present for all metric types
  var inputMeasures = (n.metric && n.metric.type_params && n.metric.type_params.input_measures) || [];
  var linked = inputMeasures.some(function (name) { return smMeasureNames[name]; });
}
```

- `dbdocs/extract/nodes.py` — `_enum_value`, `_object_name`, `_ENTITY_REPR` (literal-repr fallback), `_metric_type_params` (`input_measures` added), `_sm_items` (uses `_enum_value`), `_export_item` (`schema_name`, enum `export_as`), `_exposure_record` (enum `type`/`maturity`)
- `dbdocs/site/bundle/assets/js/service/service.js` — `metricByName`, `semanticModelForMeasure`, `metricsForSemanticModel`
- `dbdocs/site/bundle/assets/js/ui/ui.js` — `metricNameLink`, `measureNameLink`, `renderMetricNode` (linked type_params), `renderSemanticModelNode` ("Metrics built on this model"), `renderSavedQueryNode` (metric deep links)
- `tests/unit/extract/test_nodes.py` — `_fake_enum`, `_fake_measure`, `test_enum_value_*`, `test_object_name_*`, `test_metric_type_is_unwrapped_from_enum`, `test_metric_type_params_*_object*`, `test_sm_items_enum_*`, `test_export_item_*`, `test_exposure_record_enum_*`

## Collapsible node-page sections (`nodeSection`)

### Theory

Every section on every node page is a native `<details class="node-section">` block returned by `nodeSection(opts)`. The pattern:

- `nodeSection({ id, title, count, defaultOpen, actions, body, nodeId })` returns a `<details id="node-sec-{id}">` whose `<summary>` shows the section title (at h3 visual weight), an optional muted count badge, and any action buttons right-aligned via `margin-left: auto`. Clicking an action stops propagation so it doesn't toggle the section.
- **Per-section copy-link anchor** — when both `nodeId` and `id` are present, `nodeSection` always prepends a `sectionLinkButton(nodeId, id)` to the actions slot (so *every* node-page section gets one, with no per-renderer wiring). It copies a `#/node/<id>?sec=<sectionId>` deep link (the same `?sec=` `focusSection` resolves), is icon-only (the `link` icon), and `.section-link-btn` CSS fades it in on summary hover/focus (always visible while `.copied` or print-hidden).
- **State persistence** — on each `toggle` event, `_setSectionOpen(nodeId, sectionId, open)` writes to `localStorage("dbdocs-node-sections")`: `{ [nodeId]: { [sectionId]: bool }, _order: [nodeId,…] }`, capped at 100 most-recently-touched node ids (LRU by `_order`). On render, `_getSectionOpen(nodeId, sectionId, defaultOpen)` restores the stored state or falls back to the render-time default.
- **Expand all / Collapse all** — `expandCollapseBtn()` queries all `.node-section` elements on the page; if any is closed it sets all open; if all are open it closes all. Added to the badges row in `nodePageHeader`. It registers a single capturing `app` `toggle` listener tracked at module scope (`expandCollapseRefresh`); each render and every non-node `route()` removes the prior listener before attaching a new one, so navigating between node pages never leaks accumulating `refresh` closures on the persistent `app` element. The button label (`Expand all`/`Collapse all`) is its own accessible name — no aggregate `aria-expanded` (each `<details>` already exposes its own open state to AT).
- **Deep-link `?sec=<suffix>`** — `route()` calls `focusSection(sec)` which forces `node-sec-{sec}` open and scrolls it into view after layout. `?col=` deep-links also force `node-sec-columns` open via `_forceNodeSectionOpen`.
- **Lazy ERD mount** — the Related ERD section starts default-closed; its `<details>` `toggle` listener mounts the React Flow bundle the first open and reuses the host thereafter. Navigation away cleans up via the existing `unmountGraph()` at the top of `route()`.
- **Heavy sections default-closed** — Related ERD and Transformation logic start closed; all data-bearing sections (Details, Depends on, Referenced by, Columns, Tests) start open when non-empty.
- **Scroll-spy active section** — on a node page, `_initSectionObserver()` wires an `IntersectionObserver` (rooted on `app`) over each open `details.node-section > summary`; the section currently in view carries `section-in-view`, which tints its summary with `--accent` (CSS `details.node-section.section-in-view > summary`). A capturing `toggle` listener (`sectionObserverRefresh`) re-observes summaries as sections open. Both the observer and that listener are torn down at the top of `route()` (alongside `expandCollapseRefresh`) so navigating between node pages never leaks observers or listeners on the persistent `app`. Guarded behind `window.IntersectionObserver` (no-op when absent).

### Example

```javascript
// dbdocs/site/bundle/assets/js/ui/ui.js — nodeSection factory; state persistence
function nodeSection(opts) {
  var isOpen = _getSectionOpen(opts.nodeId, opts.id, !!opts.defaultOpen);
  var summary = el("summary", { class: "node-section-summary" }, [
    el("span", { class: "node-section-title" }, [opts.title]),
    /* count badge, actions (stopPropagation-guarded) */
  ]);
  var details = el("details", { class: "node-section", id: "node-sec-" + opts.id, ...(isOpen ? {open:""} : {}) }, [summary, body]);
  details.addEventListener("toggle", function () {
    _setSectionOpen(opts.nodeId, opts.id, details.open);
  });
  return details;
}

// _erdSection: lazy mount (default-closed; mount on first open)
function _erdSection(n) {
  var host = el("div", { class: "erd-section-host" });
  var mounted = false;
  var sec = nodeSection({ nodeId: n.id, id: "erd", title: "Related ERD", defaultOpen: false, body: host });
  sec.addEventListener("toggle", function () {
    if (sec.open && !mounted) { mounted = true; host.appendChild(graphMount("erd-node", n.id)); }
  });
  return sec;
}
```

**`renderPhysicalNode` section order and defaults:**

| Section id | Title | Default | Count |
|---|---|---|---|
| `details` | Details | open | — |
| `columns` | Columns | open | `columnCount(n)` |
| `tests` | Tests | open if non-empty | `testResultsForNode(id).summary.total` |
| `erd` | Related ERD | **closed** | — |
| `depends-on` | Depends on | open if non-empty | N upstream |
| `referenced-by` | Referenced by | open if non-empty | N downstream |
| `sql` | Transformation logic | **closed** | — |
| (inside sql) `macros` | Macros used | **closed** | `macroCount(n)` |

The dependency sections (`depends-on` / `referenced-by`, via `_appendDepsSections`) sit **after** the ERD and **just before** Transformation logic — the columns/tests/ERD detail leads, the graph-derived dependency chip lists trail. Other renderer types (no SQL section) keep deps wherever `_appendDepsSections` is called in their renderer.

All other renderer types follow the same open-if-non-empty / always-open-for-primary defaults; none have heavy ERD/SQL sections.

- `dbdocs/site/bundle/assets/js/ui/ui.js` — `nodeSection`, `sectionLinkButton`, `_getSectionOpen`, `_setSectionOpen`, `_loadSectionState`, `_saveSectionState`, `expandCollapseBtn`, `focusSection`, `_forceNodeSectionOpen`, `_initSectionObserver` (scroll-spy + `sectionObserverRefresh`), `_depSection`, `_appendDepsSections`, `_physicalDetailsSection`, `_columnsSection`, `_testsSection`, `_erdSection`, `_sqlSection`, `renderPhysicalNode`, `renderCodeOnlyNode`, `renderMetricNode`, `renderSemanticModelNode`, `renderSavedQueryNode`, `renderUnitTestNode`, `renderExposureNode`
- `dbdocs/site/bundle/assets/js/service/service.js` — `columnCount`, `macroCount`
- `dbdocs/site/bundle/assets/css/style.css` — `details.node-section`, `.node-section-summary`, `.node-section-title`, `.node-section-count`, `.node-section-summary-actions`, `.section-link-btn`, `.section-in-view`, `.node-section-body`, `.expand-collapse-btn`, `.erd-section-host`, `@media print`
