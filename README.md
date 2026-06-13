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

| Catalog | Model page | Lineage DAG | Health Check |
|---|---|---|---|
| ![catalog](docs/assets/img/demo-catalog.png) | ![model page](docs/assets/img/demo-model-page.png) | ![dag](docs/assets/img/demo-model-dag.png) | ![health check](docs/assets/img/demo-health.png) |

## Why dbdocs?

dbt's built-in docs stop short of telling you *which upstream column fed this downstream column*, *which tables relate to each other*, or *what changed between builds*. dbdocs fills those gaps — no documentation framework or separate ERD tool to install.

- **ERD + column-level lineage together.** Table relationships via [dbterd](https://github.com/datnguye/dbterd), plus column lineage traced from compiled SQL by [sqlglot](https://github.com/tobymao/sqlglot). Most tools give you one or the other.
- **Column impact analysis.** Select a column to see its downstream dependents project-wide — know what a schema change breaks before you run it.
- **Deep-link URLs.** Every focused node, column, and filtered DAG view has a shareable URL.
- **Any sqlglot dialect.** Auto-detected from your manifest's `adapter_type` (Snowflake, BigQuery, Redshift, DuckDB, Postgres, Databricks/Spark, Trino, …); override with `dialect:` in `dbdocs.yml`.
- **Scales without freezing.** Lineage parsing fans out across CPU cores above 500 models; the DAG is windowed by React Flow; the payload ships as an external gzip so `index.html` stays tiny.
- **Fail-soft.** An unparseable model is skipped and logged, never sinking the run.
- **Project Health Check.** A scorecard across the six [dbt-project-evaluator](https://dbt-labs.github.io/dbt-project-evaluator/) dimensions, computed from `manifest.json` — no extra package, no warehouse. Add a `run_results.json` (any `dbt build`/`dbt test`) and each test also shows as a pass/fail finding. dbdocs only reads artifacts; it never runs dbt.
- **Versioned deploys, no plugins.** `dbdocs deploy --version v1.2 --alias latest` writes a plain directory tree + `versions.json`, and the SPA renders a version dropdown. No mike, no external tooling.
- **Catalog navigation + client-side search.** Grouped by database and schema; full-text search, no backend.
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
