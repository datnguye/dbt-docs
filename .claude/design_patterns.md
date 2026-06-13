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
  - [Bundled SPA directory resolution](#bundled-spa-directory-resolution)
    - [Theory](#theory-8)
    - [Example](#example-8)
  - [Versioned deploy without mike](#versioned-deploy-without-mike)
    - [Theory](#theory-9)
    - [Example](#example-9)
  - [Click group entrypoint](#click-group-entrypoint)
    - [Theory](#theory-10)
    - [Example](#example-10)
  - [Singleton colored logger](#singleton-colored-logger)
    - [Theory](#theory-11)
    - [Example](#example-11)
  - [Always-built artifact-derived data-dict section (Health Check)](#always-built-artifact-derived-data-dict-section-health-check)
    - [Theory](#theory-12)
    - [Example](#example-12)

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
- SPA loader — `dbdocs/site/bundle/assets/js/data.js` (`loadData`)

## SPA 3-tier ES modules (data → service → ui)

### Theory

The bundled shell SPA (vanilla JS, no build step) is split into native ES modules
under `dbdocs/site/bundle/assets/js/`, with a strict one-way dependency
`ui → service → data` (mirroring the Python `core → extract → site` flow):
`data.js` loads + normalizes the payload, `service.js` is pure domain logic over
the data dict (zero DOM), `ui.js` is all DOM rendering, and `app.js` is the thin
entry that wires the three. `index.html` loads the entry as `<script
type="module" src="assets/js/app.js">`. The vendored UMD libs (`assets/vendor/`,
e.g. minisearch/marked) and the React Flow graph bundle (`assets/graph/`) stay
classic scripts setting globals (`MiniSearch`, `marked`, `window.dbdocsGraph`)
that the modules read directly — and `data.js` re-exposes the fetched payload on
`window.dbdocsData` so the graph bundle (a separate app) can read it. Keep the
service tier DOM-free and the ui tier the only DOM toucher; no bundler for the
shell. CSS lives under `assets/css/`; only `favicon.svg` sits loose in `assets/`.

### Example

```javascript
// dbdocs/site/bundle/assets/js/app.js — the entry wires the three tiers
import { loadData } from "./data.js";
import * as svc from "./service.js";
import { boot } from "./ui.js";

loadData().then(function (data) {
  svc.init(data);
  boot();
});
```

- `dbdocs/site/bundle/assets/js/` — `data.js`, `service.js`, `ui.js`, `app.js`
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

## Centralized artifact loading + the schema\_ gotcha

### Theory

All dbt-artifact access goes through `dbdocs/core/artifacts.py`: `load_artifacts`
returns dbterd-parsed `(manifest, catalog)` with schema-version relaxation;
`adapter_type` reads the warehouse from metadata (the default sqlglot dialect).
**Critical:** `dbt_artifacts_parser` aliases the `schema` field to `schema_` to
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

### Example

```python
# dbdocs/extract/nodes.py — manifest-base columns, catalog type enriches (case-insensitive)
catalog_by_lower = {str(name).lower(): col for name, col in catalog_columns.items()}
columns = []
seen_lower = set()
for name, manifest_column in manifest_columns.items():
    lower = str(name).lower()
    seen_lower.add(lower)
    catalog_column = catalog_by_lower.get(lower)
    col_type = getattr(catalog_column, "type", None) or getattr(manifest_column, "data_type", None)
    columns.append(_column_entry(name, manifest_column, col_type or ""))
# ... catalog-only columns appended afterwards
```

- `dbdocs/extract/nodes.py` — `def _columns`, `def _column_entry`

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
`assets/graph/` bundle) **windows large graphs before layout** so a 1000s-of-models
DAG never freezes the browser. The DAG renders only a focal node's bounded
neighborhood (`neighborhood(data, focus, maxDepth)`) or the dropdown-filtered set;
when unfocused and over `MAX_UNFOCUSED_DAG_NODES`, it shows a "focus a node"
placeholder instead of laying out every node. `buildDagFlow(data, keepIds)`
filters to the kept set up front, so dagre never sees the full graph. The per-node
ERD (`erd-node`) shows a placeholder naming the configured dbterd `erd_algo` (with
a docs link) when no relationships are detected. Graph-UI changes need a Node
rebuild (`task frontend:build`) of the committed bundle.

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

- `frontend/src/lib/data.ts` — `neighborhood`, `buildDagFlow`
- `frontend/src/components/GraphApp.tsx` — `MAX_UNFOCUSED_DAG_NODES`, `dagKeep`, `erdNodeEmpty`
- `dbdocs/site/builder.py` / `dbdocs/extract/erd.py` — `erd_algo` (metadata)

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
copies the build to each alias dir; the SPA reads `versions.json` and renders a
version dropdown. `--push` is opt-in (off by default, outward-facing) and shells
git to publish `gh-pages`, raising `DeployError` on a non-zero exit. Both
`deploy()` and `delete()` validate that `version` and every `alias` are safe
single path segments matching `^[A-Za-z0-9._-]+$` and are not `.` or `..`,
raising `DeployError` on violation — this includes aliases read back from
`versions.json` during deletion (preventing path traversal from a tampered index).

### Example

```python
# dbdocs/site/deploy.py — validate segments, then generate into site/<version>/
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
ReportBuilder(config).generate(output_dir=str(version_dir))
```

- `dbdocs/site/deploy.py` — `def deploy`, `def _upsert_version`, `def _push_gh_pages`, `def _validate_segment`

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
page** (split into Data tests / Unit tests), not on the Health page.

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
- `dbdocs/extract/health/extractor.py` — `class HealthCheckExtractor`, `TEST_CATEGORIES`, `_is_test_result`, `_is_unit_test`, `_resolve_metadata`, `_unit_test_model`, `_status_value`, `parse_run_results` (from `artifact_parser.dbt`)
- `dbdocs/extract/health/dimensions.py` — `class ManifestGraph` (adjacency + `threshold`/`layer`/`materialization`/`access`/`tests_for`), `class DimensionAnalyzer` (config wiring, plugin load, disable lists)
- `dbdocs/extract/health/rules/` — `base.py` (public `finding`, `docs_url`, `DEFAULT_THRESHOLDS`, `LAYER_PREFIXES`, `NON_PHYSICAL`), `dimensions/` (one module per dimension), `registry.py` (`DIMENSION_RULES`, `register_rule`, `reset_rules`, `load_entry_point_rules`, `load_rules_module`, `ENTRY_POINT_GROUP`), `__init__.py` (thin re-export facade)
- `pyproject.toml` — `artifact-parser[dbt]` runtime dependency
- `docs/dbdocs-demo.yml` — the documented `health:` block (all thresholds + every rule name under `disable`) + default `run_results`
- `tests/fixtures/jaffle_shop/run_results.json` — sanitized plain-dbt run (29 tests) whose ids match the committed manifest (co-located with the artifacts so the default `<target_dir>/run_results.json` resolves)
- `dbdocs/site/builder.py` — `def _resolve_run_results_path`, `def build_data` (health key, `config=config.health`)
- `dbdocs/site/bundle/assets/js/data.js` — `normalize()` health default (`dimensions`/`testResults`/`note`)
- `dbdocs/site/bundle/assets/js/service.js` — `healthDimensions`, `healthEnabled` (issues>0), `healthTotalIssues`, `testResultsForNode` (data/unit split)
- `dbdocs/site/bundle/assets/js/ui.js` — `renderHealth`, `healthScorecard`, `healthDimensionSection`, `nodeTestResults` (model-page Tests)
