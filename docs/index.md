# dbdocs

<p align="center">
  <img src="assets/logo.svg" alt="dbdocs logo" width="220" height="88">
</p>

<p align="center"><b>An alternative dbt docs site — catalog + ERD + column-level lineage + versioned deploys, all in one CLI.</b></p>

Turn your dbt artifacts into a self-contained docs site: a browsable catalog, an entity-relationship diagram, an interactive lineage DAG, and **column-level lineage** traced from your compiled SQL — all in one `dbdocs generate`. No server, no database, no build step. Serve it with `dbdocs serve`, or deploy versioned builds anywhere a static host will take them.

[:rocket: Try the live demo](/latest/demo/latest/){ .md-button .md-button--primary target="_blank" }
[Quickstart](./nav/guide/quickstart.md){ .md-button }

The demo is a real dbdocs site built from the
[jaffle_shop](https://github.com/dbt-labs/jaffle_shop) dbt project — poke around
the catalog, the lineage DAG, the ERD, and column-level lineage.

<a href="/latest/demo/latest/" target="_blank">
  <img src="assets/img/demo-catalog.png" alt="The dbdocs catalog overview, with project counts and the entity-relationship diagram" loading="lazy">
</a>
<p align="center"><em>The catalog overview — project counts and the entity-relationship diagram, grouped by database and schema.</em></p>

<a href="/latest/demo/latest/#/dag" target="_blank">
  <img src="assets/img/demo-model-dag.png" alt="The interactive lineage DAG in dbdocs" loading="lazy">
</a>
<p align="center"><em>The interactive lineage DAG — pan, zoom, filter, and deep-link to any node.</em></p>

<a href="/latest/demo/latest/#/node/model.jaffle_shop.orders" target="_blank">
  <img src="assets/img/demo-model-page.png" alt="A dbdocs model page showing the column table with upstream column-level lineage" loading="lazy">
</a>
<p align="center"><em>Per-model detail — every column with its type, description, and <strong>upstream column-level lineage</strong> traced from compiled SQL.</em></p>

---

## What you get

dbt's built-in docs are great — right up until you want to know *which upstream column fed this downstream column*, or *which tables relate to each other*, or *what changed between last week's docs and today's*. dbdocs fills all three gaps without asking you to install a documentation framework or maintain a separate ERD tool.

### ERD + column-level lineage, side by side

The entity-relationship diagram (powered by [dbterd](https://github.com/datnguye/dbterd)) shows table relationships; column lineage (traced by [sqlglot](https://github.com/tobymao/sqlglot) from compiled SQL) shows exactly which column fed which. Most alternatives give you one or the other — dbdocs gives you both, in the same site, from the same artifacts.

### Column impact analysis

Select any column and see its downstream dependents across the project. Know what a schema change will break before you run it — not after.

### Deep-link URLs

Every focused node, column, and filtered DAG view has a shareable URL. Paste it in Slack and your teammate lands on exactly the right model, column, or graph state — no "go to the DAG and find orders and then…" required.

### Any sqlglot-supported dialect

The dialect for column-lineage parsing is auto-detected from your manifest's `adapter_type` (Snowflake, BigQuery, Redshift, DuckDB, PostgreSQL, Databricks/Spark, Trino, and more — anything [sqlglot](https://github.com/tobymao/sqlglot) understands). Override it per-project with `dialect:` in `dbdocs.yml` when auto-detection isn't enough.

### Scales without freezing

Column-lineage parsing fans out across CPU cores automatically above 500 models, so large projects finish in roughly the same wall-clock time as small ones. The React Flow DAG is windowed, so a 1 000-model graph doesn't turn your browser into a space heater. The data payload ships as an external gzip (`dbdocs-data.json.gz`, decompressed client-side by the browser's native `DecompressionStream`) — `index.html` stays tiny regardless of project size.

### Fail-soft

One model with SQL sqlglot can't parse gets logged and skipped. It never sinks the whole generate run, so a single dialect quirk or macro-heavy model doesn't block you from seeing the rest of your project.

### Project Health Check

The SPA always includes a Health Check page: a scorecard across the six [dbt-project-evaluator](https://dbt-labs.github.io/dbt-project-evaluator/) dimensions — testing, modeling, documentation, structure, performance, and governance — computed entirely from your `manifest.json`. No extra dbt package, no warehouse, no intermediate models: dbdocs reimplements the rules over the static artifact you already have. Each dimension gets a score and a collapsible list of flagged nodes (root models, model fanout, undocumented sources, chained views, public-but-uncontracted models, and the rest), every finding linking out to the matching DPE rule docs.

When a `run_results.json` is also present (from any `dbt build`/`dbt test`; default `<target_dir>/run_results.json`, override with `--run-results`), the page additionally surfaces per-test pass/fail detail on each model page, grouped by what each test checks — integrity (not-null/unique), referential (relationships), validity (accepted values), business logic (expressions), and freshness. The test type, tested model, and column come from your `manifest.json`. dbdocs only reads the static artifacts; it never runs dbt and never touches your warehouse, so the page reflects exactly your last build. Missing or malformed `run_results.json`? Fail-soft: the dimensions still render, the per-test detail is simply skipped, and a warning is logged — never a stack trace.

### Versioned deploys, no plugins

`dbdocs deploy --version v1.2 --alias latest` generates into a plain directory tree, writes a `versions.json` index, and the SPA renders a version dropdown. No mike, no external tooling, no surprise dependencies — any static host can serve the output.

### Everything else you'd expect

- **Catalog navigation** grouped by database and schema, with client-side full-text search (no backend).
- **Per-model detail** — columns (type / tags / description), compiled and raw SQL, and the macros each model resolves.
- **Interactive graphs** — both the lineage DAG and the ERD are built on [React Flow](https://reactflow.dev/): pan / zoom / minimap, automatic [dagre](https://github.com/dagrejs/dagre) layout, and filter-and-focus.
- **Dark / light** theme.

---

## Installation

!!! warning "Requires Python 3.10+"
    dbdocs leans on the dbt artifact parser and sqlglot, both of which long ago moved past Python 3.9 — so we did too. Upgrading your interpreter is the way forward (it's worth it).

<div class="termynal" data-termynal data-ty-typeDelay="40" data-ty-lineDelay="700">
    <span data-ty="input">pip install dbdocs --upgrade</span>
    <span data-ty="progress"></span>
    <span data-ty>Successfully installed dbdocs</span>
    <a href="#" data-terminal-control="">restart ↻</a>
</div>

Verify installation:

```bash
dbdocs --version
```

---

## Quickstart

First, produce dbt artifacts in your dbt project (the bit dbdocs reads):

```bash
dbt docs generate           # writes target/manifest.json + target/catalog.json
```

Then generate, serve, and open the site:

```bash
dbdocs generate             # builds ./site/ with index.html + dbdocs-data.json.gz
dbdocs serve                # static http server on http://127.0.0.1:8000
```

The site must be served over HTTP (not opened as a local file) because it fetches
the data payload at load time. `dbdocs serve` handles that locally; any static host
works for deployment.

Head to the [Quickstart guide](./nav/guide/quickstart.md) for the full walkthrough.

---

## Contributing

Contributions are welcome — bugs, features, docs, typos. See the
**[Contributing Guide](./nav/development/contributing-guide.md)**.

If dbdocs saves you some clicks, consider
[buying me a coffee](https://www.buymeacoffee.com/datnguye).

[![buy me a coffee](https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?logo=buy-me-a-coffee&logoColor=white&labelColor=ff813f&style=for-the-badge)](https://www.buymeacoffee.com/datnguye)

---

<div align="center">

**Made with ❤️ by Dat Nguyen**

</div>
