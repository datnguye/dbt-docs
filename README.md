# dbt-docs

<!-- [![PyPI version](https://badge.fury.io/py/dbterd.svg)](https://pypi.org/project/dbterd/)
![python-cli](https://img.shields.io/badge/CLI-Python-FFCE3E?labelColor=14354C&logo=python&logoColor=white)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![python](https://img.shields.io/badge/Python-3.9|3.10|3.11-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)
[![codecov](https://codecov.io/gh/datnguye/dbterd/branch/main/graph/badge.svg?token=N7DMQBLH4P)](https://codecov.io/gh/datnguye/dbterd) -->

Alternative dbt docs site — **dbt docs + ERD + column-level lineage** 🚀

```bash
pip install dbdocs --upgrade
```

Verify installation:

```bash
dbdocs --version
```

## Table of contents

- [dbt-docs](#dbt-docs)
  - [Table of contents](#table-of-contents)
  - [Features](#features)
  - [Quickstart](#quickstart)
  - [Configuration](#configuration)
  - [CLI](#cli)

## Features

`dbdocs` reads your dbt artifacts and bakes everything into one self-contained
`index.html` — no server, no database, just a file you can open or host anywhere.

- **Multi-page-style navigation** grouped by database and schema.
- **Per-model detail**: columns (type / tags / description), compiled and raw
  SQL, and the macros each model resolves.
- **Interactive React Flow graphs** — a node-level lineage DAG and an ERD, both
  with pan / zoom / minimap, automatic [dagre](https://github.com/dagrejs/dagre)
  layout, filter-and-focus, and deep-links straight to a node. Tables show their
  columns with primary- and foreign-key badges, so the relationships aren't left
  to your imagination.
- **Column-level lineage** derived from each model's compiled SQL via sqlglot,
  shown inline as an "Upstream lineage" column right in the model's column table.
- **Client-side search** (no backend required).
- **Dark / light** theme.
- **Versioned deploy** with a built-in version dropdown — no mike, no plugins.

## Quickstart

First, produce dbt artifacts in your dbt project (the bit `dbdocs` reads):

```bash
dbt docs generate           # writes target/manifest.json + target/catalog.json
```

Then generate, serve, and open the site:

```bash
dbdocs generate             # builds ./site/index.html with data baked in
dbdocs serve                # static http server on http://127.0.0.1:8000
```

Open http://127.0.0.1:8000 and browse. Forgot to re-run `dbt docs generate`
after a model change? The docs won't know — re-`generate` and refresh.

## Configuration

All site settings live in an optional `dbdocs.yml` in your working directory.
Every key is optional; drop the file entirely to accept the defaults. See
[`dbdocs.yml.example`](./dbdocs.yml.example) for an annotated copy.

| Key               | Purpose                                                          |
|-------------------|------------------------------------------------------------------|
| `site_name`       | Site title shown in the header.                                  |
| `site_url`        | Canonical site URL.                                              |
| `site_author`     | Author metadata.                                                 |
| `site_description`| Site description metadata.                                       |
| `repo_name`       | Display name of the source repo.                                 |
| `repo_url`        | Link to the source repo.                                         |
| `project_name`    | dbt project display name.                                        |
| `target_dir`      | Where dbt artifacts are read from (default `target`).            |
| `output_dir`      | Where the generated site is written (default `site`).            |
| `dialect`         | SQL dialect override for column lineage (default: adapter type). |
| `default_version` | Alias the version switcher lands on (default `latest`).          |

## CLI

| Command           | What it does                                                    |
|-------------------|-----------------------------------------------------------------|
| `dbdocs generate` | Build the self-contained site into `output_dir`.                |
| `dbdocs serve`    | Serve `output_dir` over a static http server (`--port`).        |
| `dbdocs deploy`   | Build a versioned copy + update the version index (`--version`).|

Run `dbdocs --help` (or `dbdocs <command> --help`) for the full option list.
