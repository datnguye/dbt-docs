<p align="center">
  <img src="docs/assets/logo.svg" alt="dbdocs logo" width="220" height="88">
</p>

<p align="center"><b>An alternative dbt docs site — catalog + ERD + column-level lineage + versioned deploys, all in one CLI.</b></p>

<p align="center">
  <a href="https://dbdocs.datnguye.me/latest/demo/latest/"><img src="https://img.shields.io/badge/live-demo-FF694A?style=flat&logo=rocket&logoColor=white" alt="live demo"></a>
  <a href="https://dbdocs.datnguye.me/"><img src="https://img.shields.io/badge/docs-visit%20site-blue?style=flat&logo=gitbook&logoColor=white" alt="docs"></a>
  <a href="https://pypi.org/project/dbdocs/"><img src="https://badge.fury.io/py/dbdocs.svg" alt="PyPI version"></a>
  <img src="https://img.shields.io/badge/CLI-Python-FFCE3E?labelColor=14354C&logo=python&logoColor=white" alt="python-cli">
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://www.python.org"><img src="https://img.shields.io/badge/Python-3.10|3.11|3.12|3.13-3776AB.svg?style=flat&logo=python&logoColor=white" alt="python"></a>
</p>

Turn your dbt artifacts into a self-contained docs site: a browsable catalog, an entity-relationship diagram, an interactive lineage DAG, and **column-level lineage** traced from your compiled SQL — all in one `dbdocs generate`. Serve it with `dbdocs serve`, or deploy versioned builds anywhere a static host will take them.

| Catalog | Model page | Lineage DAG |
|---|---|---|
| ![catalog](docs/assets/img/demo-catalog.png) | ![model page](docs/assets/img/demo-model-page.png) | ![dag](docs/assets/img/demo-model-dag.png) |

## Why dbdocs?

dbt's built-in docs are great — right up until you want to know *which upstream column fed this downstream column*, or *which tables relate to each other*, or *what changed between last week's docs and today's*. dbdocs fills all three gaps without asking you to install a documentation framework or maintain a separate ERD tool.

**What you get that nothing else bundles together:**

- **ERD + column-level lineage, side by side.** The entity-relationship diagram (powered by [dbterd](https://github.com/datnguye/dbterd)) shows table relationships; column lineage (traced by [sqlglot](https://github.com/tobymao/sqlglot) from compiled SQL) shows exactly which column fed which. Most alternatives give you one or the other — dbdocs gives you both.
- **Column impact analysis.** Select any column and see its downstream dependents across the project, so you know what a schema change will break before you run it.
- **Deep-link URLs.** Every focused node, column, and filtered DAG view has a shareable URL. Paste it in Slack and your teammate lands on exactly the right model, column, or graph state.
- **Any sqlglot-supported dialect.** The dialect for column-lineage parsing is auto-detected from your manifest's `adapter_type` (Snowflake, BigQuery, Redshift, DuckDB, PostgreSQL, Databricks/Spark, Trino, and more — anything sqlglot understands). Override it per-project with `dialect:` in `dbdocs.yml` when auto-detection isn't enough.
- **Scales without freezing.** Column-lineage parsing fans out across CPU cores automatically above 500 models, so large projects finish in roughly the same wall-clock time as small ones. The DAG is windowed by React Flow, so a 1 000-model graph doesn't turn your browser into a space heater. The payload ships as an external gzip (`dbdocs-data.json.gz`, decompressed client-side) so `index.html` stays tiny regardless of project size.
- **Fail-soft.** One model with SQL sqlglot can't parse gets skipped and logged — it never sinks the whole generate run.
- **Project Health Check.** A scorecard across the six [dbt-project-evaluator](https://dbt-labs.github.io/dbt-project-evaluator/) dimensions (testing, modeling, documentation, structure, performance, governance), computed straight from your `manifest.json` — no extra dbt package, no warehouse. When a `run_results.json` is also present (any `dbt build`/`dbt test`; default `<target_dir>/run_results.json`, override with `--run-results`), each test additionally shows up as a pass/fail finding grouped by what it checks (integrity, referential, validity, business logic, freshness). dbdocs only reads the artifacts — it never runs dbt or touches your warehouse. Fail-soft: a missing `run_results.json` just drops the per-test detail; the dimensions still render.
- **Versioned deploys, no plugins.** `dbdocs deploy --version v1.2 --alias latest` generates into a plain directory tree, writes a `versions.json` index, and the SPA renders a version dropdown. No mike, no external tooling, no surprise dependencies.
- **Catalog navigation + client-side search.** Models, seeds, and snapshots grouped by database and schema; full-text search without a backend.
- **Dark / light theme.**

## Install

```bash
pip install dbdocs --upgrade
```

Requires Python 3.10+.

## Quickstart

```bash
dbt docs generate     # writes target/manifest.json + target/catalog.json
dbdocs generate       # builds ./site/ with index.html + dbdocs-data.json.gz
dbdocs serve          # static http server on http://127.0.0.1:8000
```

The site must be served over HTTP (not opened as a local file) because it fetches the data payload at load time. `dbdocs serve` handles that locally; any static host works for deployment.

Full walkthrough, configuration, and architecture live in the **[documentation](https://dbdocs.datnguye.me/)**.

## Contributing

Contributions are welcome — bugs, features, docs, typos. See the **[Contributing Guide](https://dbdocs.datnguye.me/latest/nav/development/contributing-guide.html)**.

If dbdocs saves you some clicks, consider [buying me a coffee](https://www.buymeacoffee.com/datnguye).

<a href="https://www.buymeacoffee.com/datnguye"><img src="https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?logo=buy-me-a-coffee&logoColor=white&labelColor=ff813f&style=for-the-badge" alt="buy me a coffee"></a>

## License

[MIT](./LICENSE) © Dat Nguyen
