# dbdocs

<p align="center">
  <img src="assets/logo.svg" alt="dbdocs logo" width="220" height="88">
</p>

<p align="center"><b>An alternative dbt docs site — catalog + ERD + column-level lineage + versioned deploys, all in one CLI.</b></p>

Turn your dbt artifacts into a docs site: a browsable catalog, an entity-relationship diagram, an interactive lineage DAG, and **column-level lineage** traced from your compiled SQL — all in one `dbdocs generate`. No database, no build step. Serve it with `dbdocs serve`, or deploy versioned builds anywhere a static host will take them.

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

<a href="/latest/demo/latest/#/health" target="_blank">
  <img src="assets/img/demo-health.png" alt="The dbdocs Health Check page scoring six dbt-project-evaluator dimensions" loading="lazy">
</a>
<p align="center"><em>Project <strong>Health Check</strong> — a scorecard across the six <a href="https://github.com/dbt-labs/dbt-project-evaluator">dbt-project-evaluator</a> dimensions, derived straight from your dbt artifacts.</em></p>

---

## What you get

dbt's built-in docs stop short of telling you *which upstream column fed this downstream column*, *which tables relate to each other*, or *what changed between builds*. dbdocs fills those gaps — no documentation framework or separate ERD tool to install.

- **ERD + column-level lineage** — table relationships ([dbterd](https://github.com/datnguye/dbterd)) and column lineage from compiled SQL ([sqlglot](https://github.com/tobymao/sqlglot)).
- **Column impact analysis** — downstream dependents for any column.
- **Deep-link URLs** for every node, column, and DAG view.
- **Any sqlglot dialect**, auto-detected from your manifest.
- **Scales to 1 000s of models** without freezing the browser.
- **Fail-soft** — an unparseable model is skipped, not fatal.
- **Project Health Check** across the six [dbt-project-evaluator](https://dbt-labs.github.io/dbt-project-evaluator/) dimensions.
- **Versioned deploys** with a built-in version switcher, no plugins.
- **Full-text search** across names, columns, descriptions, tags, and SQL at the client-side, no backend.
- **Static REST API** (`api/v1/`) — addressable JSON for every node, lineage, and health, for headless / agent consumption.
- **Dark / light theme.**

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
