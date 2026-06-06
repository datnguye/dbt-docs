<p align="center">
  <img src="docs/assets/logo.svg" alt="dbdocs logo" width="220" height="88">
</p>

<p align="center"><b>An alternative dbt docs site — catalog + ERD + column-level lineage, baked into one file.</b></p>

<p align="center">
  <a href="https://dbdocs.datnguye.me/latest/demo/"><img src="https://img.shields.io/badge/live-demo-FF694A?style=flat&logo=rocket&logoColor=white" alt="live demo"></a>
  <a href="https://dbdocs.datnguye.me/"><img src="https://img.shields.io/badge/docs-visit%20site-blue?style=flat&logo=gitbook&logoColor=white" alt="docs"></a>
  <a href="https://pypi.org/project/dbdocs/"><img src="https://badge.fury.io/py/dbdocs.svg" alt="PyPI version"></a>
  <img src="https://img.shields.io/badge/CLI-Python-FFCE3E?labelColor=14354C&logo=python&logoColor=white" alt="python-cli">
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://www.python.org"><img src="https://img.shields.io/badge/Python-3.10|3.11|3.12|3.13-3776AB.svg?style=flat&logo=python&logoColor=white" alt="python"></a>
</p>

Turn your dbt artifacts into a single self-contained `index.html`: a browsable catalog, an interactive lineage DAG and ERD, and **column-level lineage** from your compiled SQL. No server, no database, no build step — just a file you can open or host anywhere.

| Catalog | Model page | Lineage DAG |
|---|---|---|
| ![catalog](docs/assets/img/demo-catalog.png) | ![model page](docs/assets/img/demo-model-page.png) | ![dag](docs/assets/img/demo-model-dag.png) |

## Install

```bash
pip install dbdocs --upgrade
```

Requires Python 3.10+.

## Quickstart

```bash
dbt docs generate     # writes target/manifest.json + target/catalog.json
dbdocs generate       # builds ./site/index.html with all data baked in
dbdocs serve          # static http server on http://127.0.0.1:8000
```

Full walkthrough, configuration, and architecture live in the **[documentation](https://dbdocs.datnguye.me/)**.

## Why dbdocs?

dbt's own docs are great until you want lineage at the *column* level — that's the gap this fills. Everything is derived from your dbt `manifest.json` / `catalog.json` and baked into one offline-friendly SPA: catalog navigation grouped by database/schema, per-model SQL and columns, interactive React Flow graphs, column-level lineage via sqlglot, client-side search, a dark/light theme, and versioned deploys with a built-in version switcher.

See the [docs](https://dbdocs.datnguye.me/) for the deep dives.

## Contributing

Contributions are welcome — bugs, features, docs, typos. See the **[Contributing Guide](https://dbdocs.datnguye.me/latest/nav/development/contributing-guide.html)**.

If dbdocs saves you some clicks, consider [buying me a coffee](https://www.buymeacoffee.com/datnguye).

<a href="https://www.buymeacoffee.com/datnguye"><img src="https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?logo=buy-me-a-coffee&logoColor=white&labelColor=ff813f&style=for-the-badge" alt="buy me a coffee"></a>

## License

[MIT](./LICENSE) © Dat Nguyen
