---
name: spa-site
description: Use when changing how dbdocs assembles or presents the generated single-page-app — the project data dict, the base64 window.dbdocsData injection, the bundled vanilla-JS SPA (index.html + assets), the React Flow graph bundle (frontend/), the vendored minisearch, or the versioned deploy layout.
---

# The generated single-page-app (SPA)

`dbdocs` is an **alternative dbt docs site = dbt docs + ERD + column-level
lineage**. Instead of dbt's bundle (or any mkdocs site), it bakes the whole
project into **one self-contained `index.html`**: a hand-written vanilla-JS SPA
with all project data base64-injected as `window.dbdocsData`. No mkdocs, no mike,
no Jinja2.

The one piece of compiled JS is the **graph UI**: an interactive React Flow app
(`frontend/`, React + TypeScript, Vite) that renders the lineage DAG and the ERDs.
It is built into a **committed** bundle at
`dbdocs/site/bundle/assets/graph/{index.js,index.css}` and shipped in the wheel —
so `dbdocs generate` itself stays build-step-free (it copies the prebuilt bundle).
Node is needed only when you change the graph UI (see [The graph bundle](#the-graph-bundle-react-flow)).

## Command lifecycle

Three CLI commands (`dbdocs/cli/main.py`):

| Command           | What it does                                                          |
|-------------------|----------------------------------------------------------------------|
| `dbdocs generate` | Load artifacts → build the data dict → stage the bundle → inject → write `index.html` (+ `dbdocs-data.json`). |
| `dbdocs serve`    | Serve `output_dir` with a stdlib `http.server` (`--port`). No live reload — re-`generate` to refresh. |
| `dbdocs deploy`   | Generate a versioned copy into `output_dir/<version>/`, update `versions.json`, copy to the alias dir; `--push` publishes to gh-pages. |

`ReportBuilder.generate` (`dbdocs/site/builder.py`) is the whole `generate`
pipeline; `dbdocs/site/deploy.py` is the versioned wrapper around it.

## Config

Site metadata comes from `DbDocsConfig` (`dbdocs/core/config.py`), loaded from an
optional `dbdocs.yml` in the cwd (see `dbdocs.yml.example`). The data dict's
`metadata` pulls from `config.render_context()` — never hardcode `site_name`
etc. `config.target_path` is where artifacts are read; `config.output_path` is
where the site is written. `version` is **not** config — it's a `deploy
--version` argument.

dbterd ERD options come from a nested **`dbterd:` block** inside `dbdocs.yml`
(`DbDocsConfig.dbterd`), **not** a separate `.dbterd.yml`. Use underscore keys
(`algo`, `entity_name_format`, `resource_type`, `select`, …) — they are passed
straight through to `DbtErd`.

## The single data dict

`ReportBuilder.build_data()` returns one dict — the single source of truth the
SPA reads from `window.dbdocsData`:

```
{
  "metadata":     { ...render_context(), generated_at, adapter_type, dialect, counts },
  "nodes":        { "<unique_id>": { id, name, label, resource_type, database, schema,
                                     package, description, tags, relation_name,
                                     columns:[{name,type,tags,description}],
                                     language, raw_code, compiled_code,
                                     macros:[{name,package,sql}] }, ... },
  "lineage":      { edges:[{source,target}], parents:{id:[...]}, children:{id:[...]} },
  "columnLineage":{ "<model unique_id>": <per-column upstream map>, ... },
  "erd":          { nodes:[{id,label,database,schema,resource_type,
                            columns:[{name,type,is_primary_key,is_foreign_key,description}]}],
                    edges:[{id,source,target,from_columns,to_columns,label,type}] },
  "tree":         { byDatabase: { db: { schema: [ids...] } } }
}
```

- `nodes` is keyed by dbt `unique_id` and covers models + sources (+ seeds /
  snapshots) — `dbdocs/extract/nodes.py` (`build_nodes`).
- `tree.byDatabase` is the `database → schema → [ids]` nav tree
  (`build_tree`).
- `lineage` is the node-level DAG over surfaced nodes —
  `dbdocs/extract/graph.py` (`LineageGraph`).
- `columnLineage` is built per model from its **compiled** SQL via sqlglot —
  `dbdocs/extract/column_lineage.py` (`ColumnLineageExtractor`), with the
  vendored lineage engine in `dbdocs/extract/_sqlglot_lineage.py`. The dialect
  defaults to the artifact's `adapter_type` (override via `--dialect` /
  `dbdocs.yml`). Extraction is fail-soft: a model that won't parse is skipped
  and logged, not fatal. The SPA renders `columnLineage` **inline** as an
  "Upstream lineage" column in each node's Columns table — not a separate
  section.
- `erd` is **structured** `{nodes, edges}` (no more Mermaid). `nodes` are
  entities with their columns (`is_primary_key` / `is_foreign_key` flags),
  `edges` are foreign-key relationships — all keyed by dbt `unique_id`. Built by
  `dbdocs/extract/erd.py` (`build_erd` / `build_erd_data`), which runs dbterd's
  `json` target — a custom `@register_target("json")` adapter in
  `dbdocs/extract/erd_json.py` that emits `{tables, relationships}`. The React
  Flow bundle derives all three graph surfaces (full DAG, global ERD, per-node
  ERD) from `lineage` + `erd`.

## Injection (`dbdocs/site/inject.py`)

The data dict is JSON-serialized, **base64-encoded**, and embedded as
`<script>window.dbdocsData = JSON.parse(atob("…"));</script>`. base64 means the
(quote- and newline-laden) SQL payload can never break out of the string
literal. The bundled shell carries a `<!-- DBDOCS_DATA -->` marker as the
insertion point (falling back to before `</head>`). `generate` also writes the
same dict to `dbdocs-data.json` for debugging — **compact** (no indentation), so
it stays cheap on large projects; pipe it through `jq` to read it.

## Bundle layout

The SPA ships in the wheel under `dbdocs/site/bundle/`:

```
dbdocs/site/bundle/
├── index.html                    # the shell with the DBDOCS_DATA marker
└── assets/
    ├── app.js                    # hand-written vanilla-JS app (nav, search, node pages)
    ├── style.css                 # dark/light styling
    ├── favicon.svg               # dbt-style favicon
    ├── graph/                    # committed React Flow bundle (built from frontend/)
    │   ├── index.js              #   the @xyflow/react graph app
    │   └── index.css
    └── vendor/
        └── minisearch.min.js     # client-side search index
```

`generate` `copytree`s this whole dir into `output_dir`, then rewrites
`index.html` with the injected data.

## The graph bundle (React Flow)

The interactive graphs are a separate compiled app under `frontend/` (React +
TypeScript, `@xyflow/react` + `@dagrejs/dagre` for layout), built by **Vite**
into the committed `dbdocs/site/bundle/assets/graph/` bundle.

The vanilla SPA owns navigation; this bundle only renders graphs. The hand-off
is a small global API the bundle exposes from `frontend/src/main.tsx`:

```js
window.dbdocsGraph.mount(el)    // render a React root into el
window.dbdocsGraph.unmount(el)  // tear it down
```

`app.js` creates the host element and reads the project data from
`window.dbdocsData`:

```html
<div id="graph-root" data-mode="dag|erd|erd-node" data-focus="<unique_id>">
```

Three **modes** (read from `el.dataset`):

| `data-mode` | Surface                                                   |
|-------------|-----------------------------------------------------------|
| `dag`       | full node-level lineage DAG (from `data.lineage`).        |
| `erd`       | global ERD — all entities + FK edges (from `data.erd`).   |
| `erd-node`  | per-node ERD focused on `data-focus` (table nodes with columns + PK/FK badges). |

Building the bundle needs **Node** and is only required when you change the
graph UI:

```bash
task frontend:install   # npm install in frontend/
task frontend:build     # tsc + vite build → dbdocs/site/bundle/assets/graph/
```

The output is **committed** (and shipped in the wheel via the
`dbdocs/site/bundle/**/*` artifacts glob), so a plain `dbdocs generate` never
touches Node — it copies the prebuilt bundle like any other asset.

## Versioned deploy (no mike)

`dbdocs/site/deploy.py` does versioning by **plain directories** that any static
host serves as-is:

```
site/
  versions.json          # [{version, title, aliases}]
  <version>/index.html   # one generated site per version
  <alias>/               # copy of the version a moving alias points at (e.g. latest)
```

`deploy --version X.Y [--alias latest] [--title T]` generates into
`site/<version>/`, upserts `versions.json` (moving the alias off older
versions), and copies the build to the alias dir. The SPA reads `versions.json`
to render its version dropdown. `--push` is **opt-in** (off by default) since it
force-commits + force-pushes `output_dir` to the `gh-pages` branch —
outward-facing.

## Rules

1. **Templates own presentation.** All HTML/CSS/JS lives in the bundle assets;
   the Python only assembles the data dict. Don't render markup in Python.
2. **One data dict.** Add new surface area by extending `build_data()`'s dict
   and reading it in `app.js` — keep the producer (extract/builder) and the
   consumer (SPA) in sync, and prefer extending the dict over inventing a
   second hand-off channel.
3. **Graphs are React Flow.** ERDs and the DAG are rendered by the `frontend/`
   React Flow app via `window.dbdocsGraph.mount/unmount`; the data is the
   structured `erd` `{nodes, edges}` from `DbtErd(target="json")`. Don't
   reintroduce Mermaid or render diagram markup in Python. When you change the
   graph UI, rebuild and **commit** the `assets/graph/` bundle (`task
   frontend:build`).
4. **Assets ship in the wheel.** Anything you add under `dbdocs/site/bundle/`
   (including the committed `assets/graph/` bundle and vendored JS) must be
   covered by the `artifacts` glob in `pyproject.toml`
   (`dbdocs/site/bundle/**/*`), or it won't be packaged.
5. **Escape multiline descriptions.** dbt column descriptions can contain
   newlines; `nodes.py` replaces `\n` with `<br>` before they reach the SPA —
   preserve that when touching the node records.

## Pulling current docs

Use the context7 MCP for up-to-date `dbterd` (ERD generation), `click` (CLI) and
`@xyflow/react` (React Flow graph) behavior, and for `sqlglot` lineage
internals, before non-trivial integration changes — prefer it over guessing from
training data.
