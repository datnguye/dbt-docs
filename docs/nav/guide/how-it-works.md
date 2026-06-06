# How It Works

dbdocs is a pure-Python pipeline with one renderer. It reads dbt artifacts,
derives the documentation data, and bakes it into a single self-contained SPA.

## The pipeline

```
dbt artifacts  ──▶  extract  ──▶  one data dict  ──▶  base64-injected SPA
manifest.json       nodes          metadata            site/index.html
catalog.json        erd            nodes
                    graph          lineage
                    column_lineage  columnLineage
                                    erd
                                    tree.byDatabase
```

1. **Load** (`dbdocs/core/artifacts.py`) — dbt artifacts are parsed via the
   [dbterd](https://dbterd.datnguye.me/) Python API, with schema-version
   relaxation so newer dbt releases keep working.
2. **Extract** (`dbdocs/extract/`) — catalog nodes, the ERD, the node-level
   lineage graph, and column-level lineage are each derived from the parsed
   artifacts.
3. **Build** (`dbdocs/site/builder.py`) — `ReportBuilder.build_data()` assembles
   exactly **one** dict (`metadata`, `nodes` keyed by `unique_id`, `lineage`,
   `columnLineage`, `erd`, `tree.byDatabase`).
4. **Inject** (`dbdocs/site/inject.py`) — that dict is base64-encoded and
   injected into `index.html` as `window.dbdocsData`. base64 keeps the
   quote/newline-laden JSON from breaking out of the `<script>` string.
5. **Render** — a hand-written vanilla-JS SPA reads `window.dbdocsData` and
   renders everything client-side. The interactive graphs (DAG + ERD) are a
   React Flow app shipped as a prebuilt bundle.

## Why one self-contained file?

Because "open it and it works" beats "stand up a server first." The generated
`index.html` has no external dependencies — vendored JS libraries are committed
and shipped, not pulled from a CDN — so it runs offline, off the filesystem, or
behind any static host.

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
