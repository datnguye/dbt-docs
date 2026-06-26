---
name: spa-site
description: Use when changing how dbdocs assembles or presents the generated single-page-app — the project data dict, the external gzip payload (dbdocs-data.json.gz), the bundled 3-tier vanilla-JS SPA (index.html + assets/js,css,vendor), the React Flow graph bundle (frontend/), the vendored minisearch, or the versioned deploy layout.
---

# The generated single-page-app (SPA)

`dbdocs` is an **alternative dbt docs site = dbt docs + ERD + column-level
lineage**. Instead of dbt's bundle (or any mkdocs site), `generate` emits a small
`index.html` plus an **external** `dbdocs-data.json.gz` that a hand-written
vanilla-JS SPA fetches + decompresses client-side. The shell SPA is build-step-free
**native ES modules** in three tiers (`data` → `service` → `ui`). The site is
served over HTTP (`dbdocs serve` or any static host) — the data loads via `fetch`,
so opening `index.html` from `file://` won't work. No mkdocs, no mike, no Jinja2.

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
| `dbdocs generate` | Load artifacts → build the data dict → stage the bundle → strip the data marker → write `index.html` + the external `dbdocs-data.json.gz` (+ `dbdocs-data.json` debug dump). |
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
SPA loads (via `data.js`, which fetches `dbdocs-data.json.gz` and exposes it on
`window.dbdocsData` for the graph bundle):

```
{
  "metadata":     { ...render_context(), generated_at, adapter_type, dialect,
                    erd_algo, counts, logo?, favicon? },
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
  "tree":         { byDatabase: { db: { schema: [ids...] } } },
  "readme":       "<markdown rendered on the overview, or ''>"
}
```

- `metadata.erd_algo` is the dbterd algorithm used for ERD detection (the demo's
  `model_contract`, else dbterd's default `test_relationship`); the graph app
  shows it when a per-node ERD has no relationships. `metadata.logo`/`favicon` are
  deployed asset URLs, present only when overridden in `dbdocs.yml`.

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
  built-in `json` target (dbterd ≥ 1.28.0; emits `{nodes, edges, metadata}`).
  The React Flow bundle derives all three graph surfaces (full DAG, global ERD,
  per-node ERD) from `lineage` + `erd`.

## Payload (external gzip — `dbdocs/site/inject.py` + `builder.generate`)

The data dict is **never inlined**. `generate` serializes it once (`sort_keys=True`,
compact) and writes two files: `dbdocs-data.json.gz` (the gzipped payload the SPA
fetches, written with `gzip.compress(payload, mtime=0)` so the bytes are
reproducible) and `dbdocs-data.json` (the plain debug dump — pipe through `jq`).
`inject.strip_marker` removes the `<!-- DBDOCS_DATA -->` placeholder from the
staged `index.html`. The SPA's `data.js` (`loadData`) resolves the payload in
order: `dbdocs-data.json.gz` (decompressed via the browser-native
`DecompressionStream`) → plain `dbdocs-data.json` fallback; it then sets
`window.dbdocsData` so the React Flow graph bundle (a separate app) can read it.
Because the data loads over HTTP, the site must be **served** — `file://` won't
fetch it.

## Bundle layout

The SPA ships in the wheel under `dbdocs/site/bundle/`:

```
dbdocs/site/bundle/
├── index.html                    # the shell (<script type="module">), DBDOCS_DATA marker
└── assets/
    ├── favicon.svg               # dbt-style default favicon (loose; the only one)
    ├── js/                       # the 3-tier ES-module shell SPA (one-way data→service→ui)
    │   ├── app.js                #   thin entry (loose at root): load data → svc.init → ui.boot
    │   ├── data/                 #   tier 1 (foldered)
    │   │   └── data.js           #     fetch + normalize the payload (loadData)
    │   ├── service/              #   tier 2 (foldered)
    │   │   └── service.js        #     pure domain logic over the dict, ZERO DOM
    │   └── ui/                   #   tier 3 (foldered): all DOM rendering
    │       ├── ui.js             #     renderer (nav, search, node pages, drawer); boot/route
    │       ├── dom.js            #     shared DOM primitives (el/clear/icon/KNOWN_ICONS)
    │       └── overlays.js       #     command palette + toasts + shared MiniSearch index
    ├── css/
    │   └── style.css             #   dark/light styling + responsive (drawer, tables)
    ├── graph/                    # committed React Flow bundle (built from frontend/)
    │   ├── index.js              #   the @xyflow/react graph app
    │   └── index.css
    └── vendor/                   # committed UMD libs (offline, no CDN)
        ├── minisearch.min.js     #   client-side search index
        └── marked.min.js         #   README markdown rendering
```

`generate` removes the output dir first (`rmtree`) to guarantee a clean build
— no stale assets from a prior run — then `copytree`s this whole dir into
`output_dir`, strips the data marker from `index.html`, copies any custom
`logo`/`favicon` into `assets/`, and writes the external payload files. The shell
loads as `<script type="module" src="assets/js/app.js">`; keep the `service` tier
DOM-free and `ui` the only DOM toucher.

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

The `ui` tier creates the host element (via `graphMount`); the graph bundle reads
the project data from `window.dbdocsData` (set by `data.js`):

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
outward-facing. Both `deploy()` and `delete()` validate that `version` and every
`alias` match `^[A-Za-z0-9._-]+$` and are not `.`/`..` (raises `DeployError`);
`delete()` also validates aliases read back from `versions.json`, so a tampered
index cannot cause path traversal.

## Rules

1. **The SPA owns presentation.** All HTML/CSS/JS lives in the bundle assets; the
   Python only assembles the data dict. Don't render markup in Python.
2. **One data dict.** Add new surface area by extending `build_data()`'s dict and
   reading it in the SPA — pure derivations go in the `service` tier, rendering in
   `ui`. Keep the producer (extract/builder) and the consumer (SPA) in sync, and
   prefer extending the dict over inventing a second hand-off channel.
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
