# How It Works

dbdocs is a pure-Python pipeline with one renderer. It reads dbt artifacts,
derives the documentation data, and emits a small SPA shell plus an external,
compressed data payload the page fetches at load time.

## The pipeline

```
dbt artifacts  ──▶  extract  ──▶  one data dict  ──▶  external gzip payload
manifest.json       nodes          metadata            site/index.html (shell)
catalog.json        erd            nodes               site/dbdocs-data.json.gz
run_results.json    graph          lineage             site/api/v1/ (REST tree)
                    column_lineage  columnLineage
                    health          erd
                                    tree.byDatabase
                                    health
```

1. **Load** (`dbdocs/core/artifacts.py`) — dbt artifacts are parsed via the
   [dbterd](https://dbterd.datnguye.me/) Python API, with schema-version
   relaxation so newer dbt releases keep working.
2. **Extract** (`dbdocs/extract/`) — catalog nodes, the ERD, the node-level
   lineage graph, column-level lineage, and the project Health Check are each
   derived from the parsed artifacts.
3. **Build** (`dbdocs/site/builder.py`) — `ReportBuilder.build_data()` assembles
   exactly **one** dict (`metadata`, `nodes` keyed by `unique_id`, `lineage`,
   `columnLineage`, `erd`, `tree.byDatabase`, `health`, `readme`).
4. **Emit** (`dbdocs/site/builder.py`) — the bundled SPA shell is copied into the
   output dir, and that dict is serialized deterministically and written as an
   **external** `dbdocs-data.json.gz` (plus a plain `dbdocs-data.json` debug
   dump). It is never inlined into `index.html`, so the HTML stays tiny no matter
   how large the project is.
5. **Render** — a hand-written vanilla-JS SPA fetches `dbdocs-data.json.gz`,
   decompresses it client-side with the browser-native `DecompressionStream`, and
   renders everything. The interactive graphs (DAG + ERD) are a React Flow app
   shipped as a prebuilt bundle.

## Why an external payload, served over HTTP?

Keeping the data out of the HTML means the page weight is constant — a
3 000-model project loads the same lightweight shell as a 30-model one, then
streams and decompresses the rest. Vendored JS libraries are committed and
shipped, not pulled from a CDN, so the site runs offline behind any static host.

The trade-off: because the data loads over HTTP, the site **must be served**, not
opened straight off the filesystem. `dbdocs serve` handles that locally
(`http.server` over the output dir); any static host works for deployment.

## A static REST API for headless consumers

Alongside the SPA, `generate` writes an addressable JSON API tree under
`site/api/v1/` from the **same** data dict — one file per node, plus lineage,
health, column-lineage, and JSON Schema. AI agents and MCP servers can fetch it
without parsing any HTML. See the [REST API](./rest-api.md) guide.

## Column-level lineage, fail-soft

Each model's **compiled** SQL is parsed with sqlglot and qualified against a
schema built from the catalog (so `SELECT *` and unqualified columns resolve),
then each output column is traced to its source columns.

Per-model failures are **caught, logged, and skipped** — one unparseable model
never sinks the whole `generate`. The run reports how many models were skipped.

## Want the full architecture?

The package layout and the load-bearing design patterns are documented in the
repo: [`CLAUDE.md`](https://github.com/datnguye/dbt-docs/blob/main/CLAUDE.md) and
[`.claude/design_patterns.md`](https://github.com/datnguye/dbt-docs/blob/main/.claude/design_patterns.md).
