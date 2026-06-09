# Plan: scale, mobile, E2E tests, branding

Six workstreams for `dbdocs`. Each is self-contained and can ship on its own
branch/PR. Workstream 0 is a no-behavior-change refactor sequenced first so the
feature workstreams land on tidy seams; 1–5 are independent. Ordered by leverage.
Every Python change stays inside the `core/` → `extract/` → `site/` pipeline
pattern and keeps the 100% coverage gate.

## Table of contents

- [Plan: scale, mobile, E2E tests, branding](#plan-scale-mobile-e2e-tests-branding)
  - [Table of contents](#table-of-contents)
  - [0. SPA 3-tier refactor (data → service → ui)](#0-spa-3-tier-refactor-data--service--ui)
  - [1. Standalone versioned demo via `dbdocs deploy`](#1-standalone-versioned-demo-via-dbdocs-deploy)
  - [2. Customizable logo + favicon](#2-customizable-logo--favicon)
  - [3. Performance at 3000+ models](#3-performance-at-3000-models)
  - [4. Mobile / responsive UI](#4-mobile--responsive-ui)
  - [5. Playwright E2E tests (TypeScript)](#5-playwright-e2e-tests-typescript)
  - [Agentic-docs updates](#agentic-docs-updates)

---

## 0. SPA 3-tier refactor (data → service → ui)

A **pure restructure, no behavior change** — done first so the feature
workstreams below each edit one tier instead of hunting through a 500-line IIFE,
and so the Playwright E2E suite (workstream 5) asserts against stable, named
seams. Ship as its own PR before the performance payload work (workstream 3a).

**Why now.** `app.js` is today a single ~504-line IIFE
(`(function () { … })()`) where all three concerns are present but interleaved:
- **data** — `var DATA = window.dbdocsData || { … }` (`app.js:8`).
- **service** — pure derivations over `DATA` with no DOM: `shortName`,
  `footerMeta`, `parseHash`, `resourceCards`, `repoUrl`, `pluralize`, counts.
- **ui** — DOM only: `el`, `clear`, `route`, `buildNav`, `render*`,
  `graphMount`.

The seams already exist; this names them. Three queued workstreams poke exactly
these seams — the gzipped payload (3a) is a **data**-tier change, logo/favicon (2)
is a **service→ui** metadata change, the mobile drawer (4) is **pure ui** — so
splitting first de-risks all of them.

**Hard constraint — no build step.** The shell bundle is committed vanilla JS;
`dbdocs generate` is "pure-Python and build-step-free — it just copies the
prebuilt bundle." So the tiering uses **native ES modules** (`<script
type="module">`), NOT a bundler. (This is the shell SPA — distinct from the React
Flow app under `frontend/`, which keeps its own Vite build.) Native modules work
in every browser the SPA already targets — the same ones that have
`DecompressionStream` for the gzipped payload (3a).

**Target layout** (`dbdocs/site/bundle/assets/`):
```
data.js     // tier 1: load + normalize the payload, export a ready DATA
            //   - window.dbdocsData → else fetch .json.gz → else .json (the 3a path)
service.js  // tier 2: pure domain logic over DATA, ZERO DOM
            //   - nodesByDatabase(), lineageFor(id), columnLineageFor(id),
            //     counts(), resolveRepoUrl()  (move shortName/footerMeta/etc. here)
ui.js       // tier 3: DOM only — el(), render*(), route(), buildNav()
            //   - imports from service.js; never reads the raw DATA shape directly
app.js      // thin entry: await data → wire ui
```
- `index.html` — load the entry as `<script type="module" src="assets/app.js">`.
- Dependency direction is one-way `ui → service → data`, mirroring the Python
  side's own `core → extract → site` flow. Keep it **light**: DOM-free service,
  DOM-only ui, one data loader — not a repository/interface abstraction (overkill
  for a read-only ~500-line app).

**Keep it behavior-preserving.** No visual or routing change; the E2E suite
(workstream 5, or a quick manual `task generate && task serve` pass if 5 lands
after) is the regression guard. **Touches the data-dict + SPA contract — read the
`spa-site` skill first.**

---

## 1. Standalone versioned demo via `dbdocs deploy`

**Decision: publish the demo standalone with `dbdocs deploy` (Option A), not
inside the mkdocs site.** This dogfoods dbdocs' own versioned-deploy feature and
gives the demo a real version switcher (the SPA's `initVersions` reads
`versions.json` — `app.js:431-437`), instead of mike nesting it at
`/latest/demo/`. The demo gets its own versioned URL/subpath, decoupled from the
docs site.

**`dbdocs deploy` builds; the CI action publishes — no `--push`.** `deploy()`
generates into `<output>/<version>/`, maintains `versions.json`, and copies the
build to each `--alias` dir (`deploy.py:64-95`). Its `--push` path does `git
checkout -B gh-pages` + force-push of the whole output dir (`deploy.py:127-140`)
— which would **clobber mike's `gh-pages`** (the docs site). So we **omit
`--push`** and let a GitHub Pages action publish the built dir to a non-colliding
location. Clean split: `dbdocs deploy` does the versioned *build*, the action does
the *publish*.

Implementation:
- `docs/dbdocs-demo.yml` — point `output_dir` at a standalone dir **outside** the
  mkdocs tree (e.g. `demo-site/` — already in `.gitignore:129`), not `docs/demo`.
  Update the config's header comment (it currently describes the in-mkdocs
  `/latest/demo/` flow — rewrite to the standalone-deploy flow; latest state only,
  no history).
- `.github/workflows/publish-docs.yml` — replace the demo `generate` step with a
  no-push deploy:
  ```yaml
  - name: Build the versioned demo
    run: uv run dbdocs -c docs/dbdocs-demo.yml deploy ${{ inputs.version }} --alias latest
  ```
  then publish `demo-site/` via a Pages action to a location that does **not**
  share mike's `gh-pages` branch/path (separate branch, or a `demo/` subpath mike
  never writes). The mike step for the docs site stays as-is and untouched.
- `site_url` in `docs/dbdocs-demo.yml` — update from `…/latest/demo/` to the new
  standalone demo URL so README link rewriting resolves correctly.

The version switcher now works for real: `dbdocs deploy ${{ inputs.version }}
--alias latest` writes `versions.json`, the SPA renders the dropdown, and each
release adds a version + moves `latest`. No display-only metadata field needed —
the version is genuinely part of the deploy layout.

**Two publishers, two locations — never the same `gh-pages` path.** mike owns the
docs site; the demo Pages action owns the standalone demo location. Keep them on
separate branches/paths so neither force-push clobbers the other. **Touches the
deploy layout — read the `spa-site` skill first.**

---

## 2. Customizable logo + favicon

Today `bundle/assets/favicon.svg` is fixed and there's no logo override. Config
already carries `site_name`, `repo_name`, `repo_url` — extend that pattern.

- `dbdocs/core/config.py` — add `logo: str | None = None` and `favicon: str |
  None = None` fields (paths relative to the project, resolved like `readme` via
  `_resolve_within_cwd` with the same fail-soft `..`-escape handling). Add both to
  `_NON_METADATA_FIELDS`? No — these *are* display metadata, so they flow through
  `render_context()` to the SPA.
- `dbdocs/site/builder.py` `generate()` — after staging the bundle, if `logo`/
  `favicon` are set, copy the user file into `site/assets/` (e.g.
  `assets/favicon.<ext>`, `assets/logo.<ext>`), overwriting the bundled default.
  Resolve relative to the package the same way the bundle dir is resolved.
- `bundle/index.html` / `app.js` — the favicon `<link>` and a header logo `<img>`
  read their paths from the injected metadata, falling back to the bundled
  defaults when unset.
- **Touches the data-dict + SPA contract — read the `spa-site` skill first.**

Validation: reject paths that escape the project dir (reuse the `readme` /
`_resolve_within_cwd` fail-soft rule); accept absolute paths as-is.

---

## 3. Performance at 3000+ models

The per-model scope reuse in `column_lineage.py` (`prepare_scope` once per model)
is already in place — that's the most important optimization. Three remaining
bottlenecks at 3000 models, sequenced cheapest-first.

**3a. Gzipped external-JSON payload for large projects.** `inject.py` inlines the
entire dataset base64'd into `index.html`. At 3000 models that's a multi-second
main-thread `JSON.parse` and an OOM risk. The fix is compressed JSON — most of the
size win with **zero new dependencies and native browser support** (no Parquet, no
WASM reader; the nested data shape stays exactly as-is).
- `dbdocs/site/builder.py` — write `dbdocs-data.json.gz` (stdlib `gzip`, already
  available) when the payload exceeds a threshold (or `--external-data` is set).
  Keep inlining as the default single-file share mode.
- SPA change: `app.js` resolves the payload in priority order — inlined
  `window.dbdocsData` if present, else `fetch` `dbdocs-data.json.gz` and
  decompress via `DecompressionStream('gzip')` (native in Chrome/Edge 80+, Firefox
  113+, Safari 16.4+), else fall back to plain `dbdocs-data.json`.
- Note: hosts that already gzip on the wire (GitHub Pages, S3+CloudFront, Netlify)
  make a plain `.json` compressed in transit anyway — the pre-gzipped `.json.gz`
  matters most for `dbdocs serve` (stdlib server, no compression) and dumb static
  hosts. Handling all three forms covers both.
- **Touches the data-dict + SPA contract — read the `spa-site` skill first.**

**3b. Parallelize column lineage.** `ColumnLineageExtractor.extract()` is a
single-process loop; sqlglot parse is CPU-bound and embarrassingly parallel
across models.
- Wrap the per-model loop in a `ProcessPoolExecutor`. The catalog schema is
  read-only and picklable; results merge into the dict. Near-linear speedup on
  multi-core CI.
- Keep the fail-soft per-model skip (`self.skipped`) semantics intact.

**3c. Verify the React Flow graph windows to a neighborhood** (focal node ± N
hops) rather than rendering all 3000 nodes eagerly — full-graph render will
freeze the browser. `frontend/` change → needs `task frontend:build` to rebuild
the committed bundle.

Sequencing: **3a → 3b → 3c.** 3a–3b are pure-Python; 3c touches `frontend/`.

---

## 4. Mobile / responsive UI

Current state: viewport meta tag is correct (`bundle/index.html:5`), but the only
media query (`style.css:91`) just hides the repo name, and the sidebar is a rigid
non-shrinking 300px column (`style.css:107-108`). Desktop-only today.

- **Collapsible sidebar** — below ~768px the 300px sidebar becomes an off-canvas
  drawer toggled by a hamburger; content goes full-width. CSS + small JS toggle in
  the vanilla SPA (`app.js`). This is the core fix.
- **Responsive tables** — the column table needs horizontal scroll or a stacked
  card layout below ~480px or it blows out the viewport.
- **Graph on touch** — add `touch-action` handling; verify pinch-zoom/pan work.
  React Flow handles most of this unless the CSS overrides break it; possibly a
  "best on desktop" hint for the DAG.
- **Breakpoints** — add ≤768 and ≤480 rules for header, search, and node-detail
  panels.

Mostly vanilla-CSS + minimal JS in `dbdocs/site/bundle/` (no Node rebuild needed
except any graph touch tweaks). Lowest-risk workstream.

---

## 5. Playwright E2E tests (TypeScript)

**Decision: `@playwright/test` (TypeScript)**, run by Playwright's own runner —
same Node toolchain as the existing Vite/Vitest frontend. Kept fully separate from
the Python 100% coverage gate (it runs a browser, not Python lines).

**Layout**
- `frontend/e2e/` — `*.spec.ts` test files (next to the existing `frontend/tests/`
  vitest unit tests).
- `frontend/playwright.config.ts` — `webServer` block that builds + serves the
  generated site before the suite runs.

**webServer wiring.** The suite needs a *generated* site to test against. Two
options for the `webServer.command`:
- Preferred: a small npm script that runs `uv run dbdocs -c
  tests/fixtures/jaffle_shop generate` (or the demo config) into a temp `site/`,
  then `uv run dbdocs serve -p 8000`. Playwright waits on
  `http://127.0.0.1:8000`.
- Reuses the committed `tests/fixtures/jaffle_shop/{manifest,catalog}.json` —
  real artifacts, already in git, deterministic.

**Tooling**
- `frontend/package.json` — add `@playwright/test` devDep and scripts:
  `"e2e": "playwright test"`, `"e2e:install": "playwright install --with-deps
  chromium"`.
- `Taskfile.yml` — add `frontend:e2e` target wrapping `npm --prefix frontend run
  e2e`, plus `frontend:e2e:install`.

**Test surface (first pass)** — drive the real SPA against jaffle_shop:
- Page loads, `window.dbdocsData` present, no console errors.
- Sidebar tree renders nodes grouped byDatabase; clicking a node opens its detail.
- Full-text search (minisearch): typing `orders` filters results to matching
  models/columns.
- Column table renders types/descriptions/tests for a known model.
- Column-lineage badge opens the lineage view.
- React Flow DAG + ERD mount and render nodes.
- Dark/light toggle flips the theme.
- **Mobile viewport** (375px): the mobile drawer (workstream 4) collapses and
  toggles — this is how we regression-guard the mobile work.

**CI**
- `.github/workflows/ci_pr.yml` — add an E2E job (Node + `playwright install
  chromium` + `dbdocs generate` + `playwright test`). Independent of the
  Python matrix; does **not** feed the coverage gate.

**Coverage gate is untouched** — no `tests/e2e/` Python dir, `testpaths` and
`source=dbdocs` stay as-is. **Read the `spa-site` skill before writing selectors**
so the tests assert against the documented SPA contract, not incidental markup.

---

## Agentic-docs updates

Reflect the **latest state only** — no historical changelog, no "previously…"
notes. For each shipped workstream, update in the same change:

- **`CLAUDE.md`** — CLI lifecycle / config table: document the new `generate`
  `--external-data` flag and new `dbdocs.yml` keys (`logo`, `favicon`). Add the
  `frontend:e2e` rows to the workflows table. Update the demo description to the
  standalone `dbdocs deploy` flow (no longer `/latest/demo/` inside the mkdocs
  site).
- **`.claude/design_patterns.md`** — add/extend entries with file:line citations:
  SPA 3-tier ES-module layout (new entry: data → service → ui, no build step),
  gzipped external-JSON payload (extend "One data dict + base64 injection"),
  parallel column lineage (extend "Fail-soft column-level lineage"), responsive
  SPA layout, logo/favicon override (extend "Config object from dbdocs.yml"),
  standalone demo deploy (extend "Versioned deploy without mike"). Update the TOC.
  Cite the authoritative **symbol**, not just the line.
- **`spa-site` skill** — reflect the data/service/ui tier split, the external-data
  fetch path, the logo/favicon metadata keys, the mobile drawer, and the
  standalone demo deploy in the SPA contract.
- **Taskfile.yml** — `frontend:e2e` / `frontend:e2e:install` targets.

Edit docs in place to describe how things work **now**; do not append change
history.
