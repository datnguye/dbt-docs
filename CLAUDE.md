# dbt-docs

`dbdocs` is a Python CLI that generates an **alternative dbt documentation
site**: a dbt docs site + ERD + **column-level lineage**. Rather than dbt's
single-page bundle (or an mkdocs build), it reads dbt artifacts
(`manifest.json` / `catalog.json`) via the `dbterd` Python API, derives the
documentation data (catalog nodes, ERDs, node-level + column-level lineage), and
emits a small `index.html` plus an **external** `dbdocs-data.json.gz` that a
hand-written vanilla-JS SPA fetches + decompresses client-side. The shell SPA is
build-step-free native ES modules; the interactive graphs are a committed React
Flow bundle. Served over HTTP (`dbdocs serve` or any static host). No mkdocs, no
mkdocs-material, no mike.

## Table of contents

- [dbt-docs](#dbt-docs)
  - [Table of contents](#table-of-contents)
  - [Repo layout](#repo-layout)
  - [Workflows](#workflows)
  - [Conventions](#conventions)
  - [Design patterns](#design-patterns)
  - [Agentic setup](#agentic-setup)
  - [Agent memory](#agent-memory)
  - [External docs via context7 MCP](#external-docs-via-context7-mcp)
  - [Delegating work](#delegating-work)

## Repo layout

```
dbt-docs/
├── dbdocs/
│   ├── main.py / __main__.py     # console-script entrypoint shim
│   ├── cli/main.py               # click group + generate/serve/deploy commands
│   ├── core/                     # foundation: config, artifacts, exceptions, log
│   ├── extract/                  # derive doc data from artifacts:
│   │                             #   nodes, erd, graph, column_lineage (sqlglot)
│   └── site/                     # assemble + publish:
│       ├── builder.py            #   ReportBuilder — the one data dict + generate
│       ├── inject.py             #   strip_marker (data is external, not inlined)
│       ├── deploy.py             #   versioned deploy (no mike)
│       └── bundle/               #   the SPA: index.html + assets/{js,css,vendor,graph}/
│                                 #     js/ = 3-tier ES modules (data→service→ui)
│                                 #     graph/ = committed React Flow bundle
├── frontend/                     # React Flow graph app (React+TS, Vite) →
│                                 #   built into dbdocs/site/bundle/assets/graph/ (committed)
│                                 #   src/{components,lib}, test/{unit,e2e}, @/*→src/*
├── tests/                        # pytest, mirrors the package under tests/unit/
├── pyproject.toml                # uv + hatchling, ruff, 100% coverage gate
├── Taskfile.yml                  # task runner (wraps the uv commands)
└── .claude/                      # agents, skills, commands, hooks
```

It's a flat single-package layout — `dbdocs/` lives at the repo root (no `src/`).
The package is grouped by pipeline stage: `core/` → `extract/` → `site/`.

## Workflows

Day-to-day work is driven by `task` (root `Taskfile.yml`). Slash commands wrap
the same targets so the agentic and manual paths stay aligned.

| Goal                                 | Task              | Slash command |
|--------------------------------------|-------------------|---------------|
| Sync the uv environment              | `task install`    | —             |
| Install the graph app's npm deps     | `task frontend:install` | —       |
| Format + autofix                     | `task format`     | —             |
| Lint (format-check + ruff)           | `task lint`       | —             |
| Run tests at 100% coverage           | `task test`       | `/test`       |
| Build the generated site             | —                 | `/generate`   |
| Serve the generated site locally     | —                 | `/docs`       |
| Deploy a versioned build             | —                 | `/deploy`     |
| Cut a PyPI release                   | —                 | `/release`    |
| Rebuild the React Flow graph bundle  | `task frontend:build` | —         |
| Run the graph app's vitest units     | `task frontend:test`  | —         |
| Run the Playwright E2E suite         | `task frontend:e2e`   | —         |
| Install the Playwright browser       | `task frontend:e2e:install` | —   |
| Build demo + serve mkdocs (embedded) | `task demo:docs`  | —             |
| Install the git hooks                | `task git-hooks`  | —             |
| Remove generated artefacts + caches  | `task clean`      | —             |

`task --list` shows everything. The site `generate`/`serve`/`deploy` goals are
run via the `dbdocs` CLI (or the matching slash command), not a `task` target.

### Project docs vs the generated product

Two distinct "docs" live here — don't conflate them:

- **The product** is the SPA `dbdocs generate` emits (no mkdocs, no mike — see
  the design patterns below). It builds into `site/`.
- **The project's own documentation** at `dbdocs.datnguye.me` is a
  **mkdocs-material + mike** site under `docs/` (`mkdocs.yml`), published to the
  `gh-pages` branch by `.github/workflows/publish-docs.yml`. It builds into
  `site-docs/`. The "no mkdocs" rule is about the *product*, not this repo's docs.
- **A live demo** is `dbdocs deploy`'d (not `generate`'d) from the committed
  `tests/fixtures/jaffle_shop` artifacts via `docs/dbdocs-demo.yml` into
  `docs/demo/` (gitignored) — a versioned tree (`<version>/`, `latest/`,
  `versions.json`) so the demo SPA renders its own version switcher. `mike` then
  nests the whole docs build under its version alias, so the demo lands at
  **`/latest/demo/latest/`** — links point there. Locally (`mkdocs serve`, no
  mike prefix) it's at `/demo/latest/`.

### CI/CD

GitHub Actions under `.github/workflows/`: `ci_pr.yml` (lint + 100%-coverage
tests across Python 3.10–3.13 on Linux/macOS/Windows, plus an independent `e2e`
job — Node + Playwright against a real demo build, kept out of the coverage
gate), `pypi-publish.yml` (trusted-publisher PyPI release on tag push),
`publish-docs.yml` (mike deploy + the versioned jaffle_shop demo), `stale.yml`.

### CLI lifecycle

`dbdocs` has three commands: `generate` (read artifacts → build the data dict →
emit `site/index.html` + the external `site/dbdocs-data.json.gz` the SPA fetches,
plus a `dbdocs-data.json` debug dump) → `serve` (stdlib `http.server` over the
output dir; required since the data loads over HTTP; no live-reload — re-run
generate) → `deploy` (versioned build into `site/<version>/` + `versions.json`,
no mike). Site config lives in an optional `dbdocs.yml` (see `dbdocs.yml.example`):
`target_dir` (artifacts in), `output_dir` (site out), optional `dialect` override
for column-lineage parsing, optional `logo`/`favicon` overrides, and a `dbterd`
block (e.g. `algo`) controlling ERD relationship detection.

## Conventions

- Python: `uv run ruff format && uv run ruff check` must pass. 100% test
  coverage (`task test`). Vendored third-party code (`extract/_sqlglot_lineage.py`)
  is omitted from coverage, not gamed with no-cover pragmas.
- No relative imports. All imports at module top (`ruff PLC0415` enforces this).
- One class per file (exception: multiple exception classes may share one file).
  No nested functions/classes.
- Specific exception types in `try/except` — never bare `except:` /
  `except Exception`.
- No backward-compat shims unless explicitly asked.
- **Do not add new inline comments.** Let names and structure carry intent;
  put any rationale in `.claude/design_patterns.md` (or a module/function
  docstring for an API contract), never in scattered `#` / `//` lines inside a
  function body. This applies to new and edited code alike — when you touch a
  block, do not leave behind explanatory inline comments. Applies to Python, the
  bundle JS, and tests (incl. test names).
- The few inline comments that already exist must still describe the current
  implementation only — never the history that led to it. Drop "we used to…",
  "no longer…", "now / as before / instead of the old…", and references to
  removed code. A comment should read correctly to someone who has never seen a
  previous version.
- DRY in tests — share fixtures via `tests/conftest.py`.
- The SPA (vanilla JS under `site/bundle/`) owns presentation; the Python only
  assembles the data dict. The shell is native ES modules in 3 tiers under
  `assets/js/` (`data` → `service` → `ui`, one-way) — keep `service` DOM-free and
  `ui` the only DOM toucher; no bundler for the shell. Vendored JS libs are
  committed (offline, no CDN) and shipped in the wheel via the
  `dbdocs/site/bundle/**/*` artifacts glob.
- The interactive graphs (DAG + ERD) are a React Flow app under `frontend/`
  (React+TS, Vite). Graph-UI changes need Node: `task frontend:install &&
  task frontend:build` rebuilds the **committed** bundle at
  `dbdocs/site/bundle/assets/graph/`. `dbdocs generate` stays pure-Python and
  build-step-free — it just copies that prebuilt bundle.

## Design patterns

The load-bearing patterns of this codebase are catalogued — with file:line
evidence — in the imported config below. Extend the established pattern instead
of inventing a parallel one.

@.claude/design_patterns.md

- When you add or remove a load-bearing pattern, update
  `.claude/design_patterns.md` in the same change (new entry + TOC), with a
  concrete file:line citation.
- Line numbers there can drift; the cited symbol is authoritative — grep it.

## Agentic setup

- `docs-dev` agent (`memory: project`) — owns `dbdocs/` and `tests/`.
- `release-manager` agent (`memory: local`) — cuts PyPI releases.
- Skills: `dbterd-api` (consuming dbt artifacts/ERDs), `spa-site` (the data-dict
  + generated-SPA contract), `release` (the release procedure), `dbdocs-code-review`
  (the four-dimension review: consistency, Python pluggability, design-pattern
  alignment, 3-tier bundle JS — via `/dbdocs-code-review`).
- Hooks: `block-secrets.sh` (PreToolUse, denies secret-file access),
  `post-edit-check.sh` (PostToolUse, ruff-checks edited `.py` files).

## Agent memory

`docs-dev` uses `memory: project` — its scratchpad is committed and shared with
teammates. `release-manager` uses `memory: local` — personal, gitignored.
Because project memory lands in git:

- Never write secrets, tokens, or customer data into agent memory.
- Never write things only true for your local setup (paths to personal dbt
  projects, ports you picked).
- Do write things that remain true across sessions: dbterd/sqlglot quirks,
  architectural decisions, recurring pitfalls.

Agents curate their own `MEMORY.md` index — do not hand-edit it.

## External docs via context7 MCP

`context7` is configured in `.mcp.json`. Use it to pull up-to-date docs for
`dbterd`, `sqlglot`, and `click` before writing non-trivial integration code.
Prefer context7 over guessing from training data when library behavior matters.

## Delegating work

- Code changes in `dbdocs/`: delegate to `docs-dev`.
- Anything touching the data-dict shape or the SPA: read the `spa-site` skill
  first.
- dbterd integration: read the `dbterd-api` skill first.
- Release cuts: `release-manager` agent / `/release`.
