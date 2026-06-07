# Design patterns

The load-bearing patterns of `dbdocs`. Extend the established pattern instead of
inventing a parallel one. Line numbers drift — the cited **symbol** is
authoritative; grep it.

## Table of contents

- [Design patterns](#design-patterns)
  - [Table of contents](#table-of-contents)
  - [Pipeline-stage package layout](#pipeline-stage-package-layout)
  - [One data dict + base64 injection](#one-data-dict--base64-injection)
  - [Config object from dbdocs.yml](#config-object-from-dbdocsyml)
  - [Centralized artifact loading + the schema\_ gotcha](#centralized-artifact-loading--the-schema_-gotcha)
  - [Fail-soft column-level lineage](#fail-soft-column-level-lineage)
  - [Bundled SPA directory resolution](#bundled-spa-directory-resolution)
  - [Versioned deploy without mike](#versioned-deploy-without-mike)
  - [Click group entrypoint](#click-group-entrypoint)
  - [Singleton colored logger](#singleton-colored-logger)

## Pipeline-stage package layout

The package is grouped by what each module does in the generate pipeline:
`core/` (shared foundation: config, artifact loading, exceptions, logging) →
`extract/` (derive the documentation data from artifacts: nodes, ERDs,
node-level graph, column-level lineage) → `site/` (assemble + publish: the data
dict builder, base64 injection, versioned deploy, and the bundled SPA). The CLI
(`cli/`) wires user commands to `site/`. Dependencies flow one way: `extract/`
and `site/` import from `core/`, never the reverse.

- `dbdocs/core/` — `config.py`, `artifacts.py`, `exceptions.py`, `log.py`
- `dbdocs/extract/` — `nodes.py`, `erd.py`, `graph.py`, `column_lineage.py`
- `dbdocs/site/` — `builder.py`, `inject.py`, `deploy.py`, `bundle/`

## One data dict + base64 injection

There is exactly one renderer. `ReportBuilder.build_data()` assembles a single
dict (`metadata`, `nodes` keyed by unique_id, `lineage`, `columnLineage`, `erd`,
`tree.byDatabase`); `generate()` stages the bundled SPA, then base64-injects that
dict into `index.html` as `window.dbdocsData` (the marker `<!-- DBDOCS_DATA -->`,
falling back to before `</head>`). The SPA reads `window.dbdocsData` and renders
everything client-side. base64 keeps the quote/newline-laden JSON from breaking
out of the `<script>` string. The dict is serialized with `sort_keys=True` for
deterministic, reproducible output (both the injected payload and the
`dbdocs-data.json` debug dump). Do not invent a second render path — extend the
data dict and the SPA that consumes it.

- `dbdocs/site/builder.py` — `class ReportBuilder`, `def build_data`, `def generate`
- `dbdocs/site/inject.py` — `INJECT_MARKER`, `def data_script`, `def inject`

## Config object from dbdocs.yml

Site metadata is a single `DbDocsConfig` dataclass loaded from an optional
`dbdocs.yml` (all fields default, so the file is optional). The builder pulls
display metadata from `config.render_context()` (which strips build-control
fields — `target_dir`, `output_dir`, `dialect`, `default_version`) rather than
hardcoding values. Unknown keys / malformed YAML raise `DbDocsConfigError` —
never a bare `Exception`. `target_path` (artifacts in) and `output_path` (site
out) resolve relative dirs against the cwd at access time. Relative
`target_dir`/`output_dir` values that escape the cwd via `..` raise
`DbDocsConfigError`; absolute paths are accepted as-is. The same `..`-escape
check applies to a relative `readme` path — an escaping path is silently
treated as absent (fail-soft, returns "").

- `dbdocs/core/config.py` — `class DbDocsConfig`, `def load`, `def render_context`, `def output_path`, `def _resolve_within_cwd`
- `dbdocs/core/exceptions.py` — `DbDocsConfigError`, `LineageError`, `DeployError`

## Centralized artifact loading + the schema\_ gotcha

All dbt-artifact access goes through `dbdocs/core/artifacts.py`: `load_artifacts`
returns dbterd-parsed `(manifest, catalog)` with schema-version relaxation;
`adapter_type` reads the warehouse from metadata (the default sqlglot dialect).
**Critical:** `dbt_artifacts_parser` aliases the `schema` field to `schema_` to
avoid clobbering Pydantic's `BaseModel.schema()`, so `entity.schema` is a *bound
method*, not the value. Always read `schema_`; `db_schema(entity)` centralizes
that with safe `_unknown` fallbacks. Never read `.schema` off a parsed node.

- `dbdocs/core/artifacts.py` — `def load_artifacts`, `def adapter_type`, `def db_schema`, `NODE_PREFIXES`

## Fail-soft column-level lineage

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
column of a model. `_extract_model` calls `prepare_scope(compiled, …)` once and
passes the resulting `scope` to `lineage(column, …, scope=scope)` per column —
turning the per-model cost from `O(columns × parse)` into `O(parse + columns)`.
This is what keeps `generate` tractable on 1000–3000+ model projects (a 50-column
model goes from 50 qualify passes to 1). The shared scope is read-only across
columns — `to_node` builds fresh `Node`s and a fresh `visited` set per call — so
reuse is safe. Don't reintroduce a per-column `lineage(column, compiled, …)` call
that re-parses.

- `dbdocs/extract/column_lineage.py` — `class ColumnLineageExtractor`, `def extract`, `def _extract_model`
- `dbdocs/extract/_sqlglot_lineage.py` — `def prepare_scope`, `def lineage`, `def to_node` (vendored; omitted from coverage)

## Bundled SPA directory resolution

`ReportBuilder` resolves the bundled SPA dir relative to the package
(`dbdocs/site/bundle/`) from `__file__`, so the assets are found whether running
from source or an installed wheel. `generate()` removes the output dir first
(`rmtree`) before `copytree`ing the whole bundle (shell + `assets/` incl.
vendored UMD libs) — guaranteeing a clean build with no stale assets from a
prior run. This is why the `artifacts` glob in `pyproject.toml` must ship
`dbdocs/site/bundle/**/*`.

- `dbdocs/site/builder.py` — `BUNDLE_DIR = Path(__file__).resolve().parent / "bundle"`, `def generate`

## Versioned deploy without mike

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

- `dbdocs/site/deploy.py` — `def deploy`, `def _upsert_version`, `def _push_gh_pages`, `def _validate_segment`

## Click group entrypoint

The CLI is a `click.group` with `no_args_is_help=True` and a `--version` option;
subcommands attach via `@dbdocs.command(name=...)`. Commands are `generate`,
`serve` (stdlib `http.server` over the output dir), and `deploy`. dbdocs-level
errors are re-raised as `click.ClickException` for clean CLI output.
`dbdocs/main.py` is the thin console-script shim (`main()` → `cli.dbdocs()`).

- `dbdocs/cli/main.py` — `@click.group(...) def dbdocs`, `@dbdocs.command(name="generate")`
- `dbdocs/main.py` — `def main`

## Singleton colored logger

A single module-level `logger` (name `"dbdocs"` — deliberately not `"dbterd"`,
to avoid colliding with the dbterd library's logger) with an ANSI-color
formatter, guarded so handlers attach only once (`if len(logger.handlers) ==
0`). Import and use it; do not create new loggers.

- `dbdocs/core/log.py` — `class LogFormatter`, `logger = logging.getLogger("dbdocs")`
