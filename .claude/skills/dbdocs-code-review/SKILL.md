---
name: dbdocs-code-review
description: Use when reviewing dbdocs changes (a diff, branch, or PR) for consistency, Python pluggability, design-pattern alignment, the 3-tier bundle-JS contract, complexity/scale, and the generated-SPA UX & accessibility. Produces a severity-graded findings report scoped to this codebase's documented patterns — not a generic lint.
---

# Reviewing dbdocs changes

This is **dbdocs**' opinionated review: it checks a change against *this*
codebase's load-bearing patterns, not generic style. The six review dimensions
below are the contract. Read the change, then report findings under each
dimension, severity-graded, with `file:line` evidence.

## Scope the change first

Determine what's under review and read only the relevant tiers:

```bash
git diff --stat                 # what changed
git status --short              # incl. untracked new files
```

**Consistency**, **Design patterns**, and **Complexity / scale** apply to *every*
change — Python, bundle JS, CSS, config, docs, tests (Complexity is scoped to the
generate path). The other three dimensions are domain-scoped:

- **Pluggable (Python modules)** → Python changes (`dbdocs/**/*.py`).
- **3-tier bundle JS** → bundle changes (`dbdocs/site/bundle/assets/{js,css}/**`).
- **UX & accessibility** → anything affecting the *rendered* SPA — bundle
  JS/CSS/HTML (`dbdocs/site/bundle/**`) and the React Flow graph (`frontend/**`).
- `frontend/**` (React Flow graph) is the *compiled* graph app, not the 3-tier
  shell — review it as its own app, not against the shell tiers, but it is still
  subject to **Consistency**, **Design patterns**, **Complexity / scale**, and
  **UX & accessibility** (e.g. the committed `assets/graph/` bundle must be
  rebuilt when the source changes, and DAG/ERD work must respect windowing).

Always run all six dimension checks; report "none" for a dimension with no
findings rather than skipping it.

**Authority:** `.claude/design_patterns.md` (patterns + `file:line` citations) and
`.claude/skills/spa-site/SKILL.md` (the SPA/data-dict contract). The cited
**symbol** is authoritative; line numbers drift — grep the symbol.

## Run the gates (report, don't fix)

```bash
uv run ruff format --check . && uv run ruff check .
uv run ruff check --select PLC0415 .        # no inline imports
uv run pytest --cov=dbdocs --cov-report=term-missing --cov-fail-under=100
```

A green baseline is table stakes; the review is about what the gates *don't*
catch. Never fix failures during a review unless the user asks.

## Dimension 1 — Consistency

Does the change look like the code around it, and reuse what already exists?

- **One class per file** (exception: multiple exception classes may share a file);
  **no nested** functions/classes; **all imports at module top** (`ruff PLC0415`);
  **no relative imports**.
- **Specific exception types** in `try/except` — never bare `except:` /
  `except Exception`. Fail-soft paths log via the singleton `logger`
  (`dbdocs.core.log`), never a new logger.
- **DRY**: repeated logic should be shared, not copy-pasted (helpers, fixtures via
  `tests/conftest.py`). Flag duplicated blocks and divergent values for the *same*
  concept (e.g. two CSS colors for one status, two constants for one threshold).
- **No backward-compat shims** unless explicitly asked.
- **Naming + docstrings match reality**: flag stale references (e.g. a docstring
  naming a renamed/moved module), unused parameters, dead exports.
- **No duplicated lookups**: a value computed twice in one function (especially a
  `service` accessor called repeatedly) should be cached in a local.

## Dimension 2 — Pluggable (Python modules)

New Python surface should extend an established seam, not invent a parallel one.

- **Pipeline-stage layout**: `core/` → `extract/` → `site/`, one-way. `extract/`
  and `site/` import from `core/`, never the reverse. A new extractor lives in
  `dbdocs/extract/`; a feature spanning >2 modules becomes a **sub-package**
  (`extract/<feature>/`) with a **thin `__init__.py` facade** (re-export only —
  no implementation) and the impl in named modules (e.g. `registry.py`,
  `dimensions/`). Cross-module imports use **public** names (no leading-underscore
  symbols imported across module boundaries).
- **Registry / plugin seams** (e.g. the health rule engine): a feature with a set
  of interchangeable units should expose a registration API
  (`register_rule`-style decorator/call), discover plugins via the
  **`dbdocs.health_rules` entry-point group** and/or a config `rules_module`
  dotted path, and keep the built-in baseline restorable (`reset_rules`). Check:
  registration is **idempotent**; the registry is reset between tests (an autouse
  conftest fixture); thresholds/behaviour are **config-driven** (read from the
  `dbdocs.yml` block via the object, not hardcoded at the call site); a bad plugin
  is **fail-soft** (caught, logged, skipped — never sinks `generate`).
- **Config**: new knobs are fields on `DbDocsConfig` loaded from `dbdocs.yml`;
  build-control fields (not display metadata) go in `_NON_METADATA_FIELDS`; a CLI
  override writes back to the config object before `ReportBuilder` runs (the
  `--dialect` pattern). Document the knob in `dbdocs.yml.example`.

## Dimension 3 — Align with design patterns

**Applies to every change** (Python, SPA, CSS, config, docs, tests).
Cross-check the change against the full catalogue in `.claude/design_patterns.md`
— not just the patterns below. For each pattern the change touches, confirm it
**extends** the pattern rather than forking it. The patterns span all tiers:
the pipeline-stage layout, the config object, the data dict, artifact loading,
column lineage, graph rendering, the SPA modules, versioned deploy, the click
group, the singleton logger, and the always-built health section. Representative
checks:

- **One data dict + external gzip payload** — new SPA surface extends
  `ReportBuilder.build_data()`'s single dict and is read in the SPA; no second
  hand-off channel, no re-inlining the payload into `index.html`.
- **Centralized artifact loading + the `schema_` gotcha** — artifact access goes
  through `dbdocs/core/artifacts.py`; read `schema_` (the alias), never `.schema`
  (a bound method) off a parsed node.
- **Manifest-base columns, catalog-enriched** (`extract/nodes.py`) — columns come
  from the manifest (manifest order), catalog only *enriches* type
  case-insensitively; a stale/empty catalog must not drop documented columns.
- **Fail-soft, parallel column-level lineage** (`extract/column_lineage.py`) —
  per-model failures caught/logged/skipped; scope built once per model (not per
  column); parallel above `_PARALLEL_THRESHOLD` via picklable work tuples (never
  the Pydantic manifest across the process boundary).
- **Windowed graph rendering** (`frontend/`, committed `assets/graph/` bundle) —
  the DAG windows to a focal neighborhood before layout; over
  `MAX_UNFOCUSED_DAG_NODES` it shows a placeholder. A graph-UI change must rebuild
  + commit the bundle (`task frontend:build`).
- **Bundled SPA directory resolution** (`site/builder.py`) — `BUNDLE_DIR` resolves
  from `__file__`; `generate()` does `rmtree` + `copytree` for a clean build.
  Anything new under `bundle/` must be covered by the `pyproject.toml` artifacts
  glob (`dbdocs/site/bundle/**/*`) or it won't ship in the wheel.
- **Versioned deploy without mike** (`site/deploy.py`) — plain `<version>/` dirs +
  `versions.json`; segment validation against `^[A-Za-z0-9._-]+$`. Don't
  reintroduce mike/external tooling.
- **Optional/always-built artifact-derived section** (Health Check) — fail-soft to
  an empty-but-enabled section when the artifact is absent; parse with the right
  library (`artifact-parser` for run_results, not the manifest parser); status
  enums read via `.value`.
- **If the change adds or removes a load-bearing pattern**, `.claude/design_patterns.md`
  must be updated in the same change (new entry + TOC + a concrete `file:line`
  citation). Flag a missing/stale doc update as a finding.

## Dimension 4 — 3-tier bundle JS

The bundled shell SPA (`dbdocs/site/bundle/assets/js/`) is native ES modules in a
strict one-way `ui → service → data`. Verify:

- **`data.js`** loads + `normalize()`s the payload, **defaulting every top-level
  key** so the upper tiers never null-check the dict shape.
- **`service.js` is DOM-free** — pure domain logic over the normalized dict. No
  `document`, no `el()`, no DOM reads/writes. Domain derivations (filtering,
  grouping, scoring, lookups) belong here, exposed as accessors.
- **`ui.js` is the only DOM toucher** — it renders via `el()` and reads from
  `service`. Flag domain logic that leaked into `ui` (it belongs in `service`) and
  any DOM access that leaked into `service`.
- **Producer ↔ consumer in sync**: a Python data-dict change must have the SPA
  side updated to read it (and vice-versa). Vendored UMD libs and the React Flow
  graph bundle stay classic scripts setting globals (`window.dbdocsGraph`,
  `MiniSearch`, `marked`); `data.js` re-exposes the payload on `window.dbdocsData`
  for the graph bundle.
- **CSS** lives under `assets/css/`; the same status/concept uses **one** color
  across pills/badges (don't introduce a divergent value).

## Dimension 5 — Complexity / scale (the 1000s-of-models invariant)

**Applies to every change that touches the generate path** (Python *and* the
graph bundle). dbdocs must stay performant on **3000+ model** projects — this is a
load-bearing product promise (parallel column lineage + windowed graph rendering
exist for exactly this). For each new or changed loop, recursion, or data
structure, state its **complexity in terms of N = #nodes (models+sources+tests)**
and flag anything worse than the budget below.

What to compute and check:

- **Annotate the hot path.** For each new function on the generate path, give its
  Big-O in N. The bar: **whole-pass work should be ~`O(N)` or `O(N·k)`** for a
  small constant/config `k` (e.g. #rules, #columns-per-model). Flag:
  - **`O(N²)`** — a nested loop over all nodes (e.g. "for each model, scan all
    models/edges"). Almost always avoidable by **indexing once** (build a
    `dict`/`set` adjacency up front, then O(1) lookups — see
    `ManifestGraph._build_adjacency`). The health rules are `O(N·rules)` with O(1)
    `parents()`/`children()` for this reason.
  - **Repeated recompute** — the same derived value computed per-iteration instead
    of **memoized once** (e.g. `non_physical_chain_depth` caches on
    `_chain_cache`; column-lineage builds `scope` once per model, not per column).
  - **Re-parsing / re-scanning** — re-reading an artifact, re-parsing SQL, or
    re-scanning entry points inside a loop.
- **Recursion depth.** dbt DAGs can be **thousands deep**. Any recursion over the
  graph must be **iterative or memoized** — naive recursion hits Python's
  ~1000-frame limit and `RecursionError`s `generate` on a deep chain. Prefer an
  explicit stack + a visited set (cycle guard) over `def f(): ... f(parent)`.
- **Parallelism threshold.** CPU-bound per-model work (sqlglot parsing) fans out
  across a `ProcessPoolExecutor` above `_PARALLEL_THRESHOLD`; only **picklable**
  work tuples cross the boundary (never the Pydantic manifest/catalog). A new
  heavy per-model step should follow this, not run a serial loop.
- **Payload size.** New data-dict keys are `O(N)` per node at worst — don't emit
  `O(N²)` data (e.g. a full adjacency matrix). The payload is gzipped + external;
  keep per-node records lean.
- **Graph bundle.** New DAG/ERD work must respect windowing — layout only the kept
  set (`buildDagFlow(data, keepIds)`), never lay out all N nodes unfocused.
- **Fail-soft on blow-up.** A pathological input (deep cycle, huge fanout) must be
  caught per-unit and skipped, not crash `generate` (the per-rule `try/except` in
  `DimensionAnalyzer.analyze` catches `RecursionError` too).

When reviewing, **prove it**: if a change adds a graph walk or per-model loop and
you're unsure, sketch a worst-case input (a 3000-deep view chain, a 3000-wide
fanout) and reason about whether it stays linear / terminates. Cite the offending
`file:line` and the input that breaks it.

## Dimension 6 — UX & accessibility (the rendered SPA)

**Scoped to changes that affect the *rendered* product** — the bundled shell SPA
(`dbdocs/site/bundle/**`: `js/`, `css/`, `index.html`) and the React Flow graph
(`frontend/**`). dbdocs ships a documentation site people *use*; a change can be
correct, pattern-aligned, and `O(N)` yet still ship a page that's unusable by
keyboard, unreadable on a phone, or silently broken on an empty/error state.
Report "none" for a change that doesn't touch the rendered SPA. Cite `file:line`
and, where it matters, the device/AT (assistive tech) or state that exposes it.

### Accessibility

- **Keyboard reachable + operable.** Every interactive affordance is a real
  control (`<a href>`, `<button>`, native `<details>`/`<input>`) — not a `<div>`
  with an `onclick`. Tab order is sane; nothing is keyboard-trapped. The DAG/ERD
  full-screen, the nav drawer/collapse rail, the copy-link button, the search box
  and the tree filter all work without a mouse.
- **Focus management.** Route changes and deep-link scrolls (`focusColumn`,
  `renderHealth`'s scroll-into-view) move/restore focus sensibly; a focused
  element stays visible (don't suppress the focus ring without a replacement).
  Opening the mobile drawer should not strand focus behind an overlay.
- **Names for the nameless.** Icon-only buttons (`copyLinkButton`, full-screen,
  `nav-toggle`/`nav-collapse`, the search 🔍) carry an accessible name
  (`aria-label`/`title`/visually-hidden text) — an `<span class="ic">` mask glyph
  has no text. State toggles expose `aria-expanded`/`aria-pressed`; the nav
  follows the existing `aria-expanded` pattern (`setNavOpen`/`setNavCollapsed`).
- **Contrast + non-color cues.** Text/background pairs meet ~WCAG AA in **both**
  themes (check the health status palette, `.muted` text, pills/badges in dark).
  Status is never color-*only* — pass/warn/fail/error carry a text label too
  (the health pills/badges do; flag any new color-only signal).
- **Semantics.** Tables that are data tables use `<thead>/<th>` (the health +
  columns tables do); headings nest without skipping levels; `target="_blank"`
  links carry `rel="noopener"` (already the convention).

### Responsive / mobile

- **Small-screen layout.** New UI works at ~360px wide: the mobile drawer nav and
  the desktop collapse rail are distinct (`nav-open` vs `nav-collapsed`) and both
  behave; nothing overflows the viewport horizontally.
- **Wide tables.** New tables (health findings, the Columns table's added
  Downstream-impact column, per-model Tests) must scroll/wrap on narrow screens
  rather than blowing out the layout — verify the overflow treatment matches the
  existing tables.
- **Touch targets + the graph.** Tap targets are comfortably sized; the windowed
  graph stays usable on touch (pan/zoom, the "focus a node" placeholder over the
  cap) — don't ship a DAG that's only operable with a hover.

### Interaction & feedback

- **Every state is handled.** Loading, empty, and error states exist and read
  clearly — the "too many models" placeholder, the filter-matched-nothing empty
  state, "Graph bundle not loaded.", "No description provided.", the health
  `note` when `run_results.json` is absent. A new view that can be empty must say
  so, not render blank.
- **Transient feedback resolves.** Async affordances confirm + recover — the
  copy-link button flashes "Copied!" / "Copy unavailable" and resets; flag any
  action that gives no feedback or leaves a stuck state.
- **Deep links + shareability.** Hash routes round-trip (`#/health?d=…`,
  `#/dag?focus=&rtype=&schema=`, `?col=`); filter state is written back via
  `history.replaceState` **without** remounting the graph (the documented
  no-`hashchange` trick). A new shareable view should be reflected in the hash.

### Visual consistency

- **One token per concept.** Spacing, radius, color read from the CSS custom
  properties (`--bg`, `--border`, `--accent`, the `--status-*` palette) — not new
  hard-coded hex/px that duplicate an existing token (this overlaps Consistency;
  call it under whichever fits, not both).
- **Light/dark parity.** Anything new is defined for **both** themes (or inherits
  theme tokens so it follows automatically); flag a light-only color literal.
- **Icon + idiom reuse.** New icons go through the `icon()` mask + `KNOWN_ICONS` +
  `icons.css` path (no inline SVG); new surfaces reuse the established
  card/pill/badge/scorecard idioms rather than inventing a parallel look.

## Output format

Lead with a one-line verdict + the gate results, then findings grouped by the six
dimensions, **severity-graded** and each with `file:line` + a one-line description.
Do not rewrite code in the report — identify, then offer to apply.

```
**Verdict:** <aligned / needs work> · ruff <ok> · <N> tests <pass> at <X>% coverage

### Consistency
- 🔴/🟡/⚪ `file:line` — <finding>
### Pluggable (Python)
- ...
### Design patterns
- ...
### 3-tier bundle JS
- ...
### Complexity / scale
- 🔴/🟡/⚪ `file:line` — <finding> (state the Big-O in N + the worst-case input)
### UX & accessibility
- 🔴/🟡/⚪ `file:line` — <finding> (name the device/AT or state that exposes it)
- ...

(✓ Verified clean: <dimensions with no findings>)
```

Severity: 🔴 correctness/contract violation · 🟡 worth fixing (real
inconsistency) · ⚪ nit/optional. Behavior-neutral findings are test-safe to
apply; say so and offer to apply **all**, the **high-severity subset**, or none.
