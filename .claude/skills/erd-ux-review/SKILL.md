---
name: erd-ux-review
description: Use when reviewing the generated dbdocs ERD's UI/UX against a real dbt project — the overview ERD and the model-page "Related ERD". Installs the local build into a target dbt project, generates + serves, drives a headless browser to screenshot both ERD surfaces (light/dark, default/focused), and emits a severity-graded UX findings report. ALWAYS asks for the dbt project path first.
---

# Reviewing the dbdocs ERD UI/UX

This skill reviews the **rendered** ERD in a real generated site — not the code.
It exercises the two ERD surfaces a user actually sees and reports what's wrong
with the experience, severity-graded, with screenshot evidence.

Two surfaces under review:

1. **Overview ERD** — `#/overview`, the whole-project snowflake (radial, centered
   on the most-connected table; locked by default; toolbar = focus + schema).
2. **Model-page "Related ERD"** — `#/node/<id>`, the focused 1-hop snowflake for
   that model.

## Step 0 — ask for the dbt project path (REQUIRED, do this first)

Always ask which project to review against — but **suggest the bundled
`tests/fixtures/big_project` as the default**. That fixture is a real, large
project (96 models, snowflake, a wide FK ERD) committed in this repo, so it
surfaces ERD scale + snowflake-layout issues without an external project and
needs no `dbt build` — its `manifest.json` + `catalog.json` already exist. Use
`AskUserQuestion` to offer it as the first (recommended) option alongside "a
different dbt project (give a path)", e.g.:

> Which dbt project should I review the ERD against?
> - **`tests/fixtures/big_project`** (recommended) — the bundled 96-model
>   snowflake fixture; best for ERD scale, no setup needed.
> - A different dbt project — a path to one with `target/manifest.json` +
>   `target/catalog.json` (and ideally a `dbdocs.yml`).

Always let the user supply an arbitrary path. Validate the chosen path has the
artifacts before proceeding — the bundled fixture keeps them directly in
`tests/fixtures/big_project/` (no `target/` subdir); an external project keeps
them under `target/`:

```bash
ls "$PROJECT/manifest.json" "$PROJECT/catalog.json" 2>/dev/null \
  || ls "$PROJECT/target/manifest.json" "$PROJECT/target/catalog.json"
ls "$PROJECT/.venv/bin/activate" 2>/dev/null   # or whatever venv they use
```

For the bundled fixture, point `dbdocs generate` at it with a `target_dir` of
that path (the artifacts sit at the top of the dir, not under `target/`). For an
external project, the artifacts are under `target/`; if they're missing, stop and
tell the user to run `dbt docs generate` (or `dbt build`) there first.

## Step 1 — install the local build, generate

The local dbdocs must be installed into the target project's venv so its
prebuilt bundle (incl. any working-tree graph changes) is what gets served.
**Rebuild the bundle first if you touched `frontend/`** — `pip install -e` ships
whatever is in `dbdocs/site/bundle/`, so a stale bundle = a stale review:

```bash
# from the dbt-docs repo, if frontend changed:
task frontend:build

# then, in the target project:
cd "$PROJECT" && source .venv/bin/activate
pip install -e /Users/ilambda/sources/datnguye/dbt-docs
dbdocs generate          # writes <target_dir>/site (or output_dir from dbdocs.yml)
```

Note the "Generated site at …" path from the log — that's the serve root.

## Step 2 — serve (threaded, for the browser)

`dbdocs serve` is **single-threaded stdlib `http.server`** — a headless browser's
parallel asset loads + `networkidle` waits will **deadlock it** (curl then hangs
returning 000). Run `dbdocs serve` if the user asked to see it, but for the
automated review serve the same dir with a **threaded** server on a separate port:

```bash
cd "<generated-site-dir>" && nohup python3 -c "
import http.server, socketserver
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
class T(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads=True; allow_reuse_address=True
T(('127.0.0.1', 8010), H).serve_forever()
" >/tmp/erd_review_serve.log 2>&1 &
sleep 2; curl -s -m5 -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8010/
```

## Step 3 — drive the browser, capture evidence

Use Playwright (it's a dev dep under `frontend/` — write the script into
`frontend/` so it resolves the module, run it, then delete it). Use
`waitUntil: "domcontentloaded"` (NOT `networkidle`), and wait ~6s after load for
the gzip payload + React Flow mount. Capture, at minimum:

- Overview ERD: default (locked), then after focusing a table via the toolbar,
  then unlocked + zoomed-in. Record the viewport `scale` from
  `.react-flow__viewport`'s transform and the visible `.dbd-erd` count.
- Model-page ERD: pick a model with many relationships (highest FK degree from
  `dbdocs-data.json` `erd.edges`) so the snowflake is exercised.
- **Dark mode**: toggle `#theme-toggle` and re-shoot the overview ERD — theme
  bugs in the node bodies only show here.

Read the PNGs back (the Read tool renders them) and judge them.

## Step 4 — review checklist

Grade each against the rendered result. Cite the screenshot + the scale/counts.

**Readability & first paint**
- Does the ERD land at a legible zoom, or a grey haze? (fit-view `minZoom` floor
  lives in `ERD_FIT_OPTIONS`, GraphApp.tsx.) At the landing zoom, can you read a
  table's name + columns?
- Locked-by-default overview: is the affordance ("click to pan & zoom") clear, or
  does it read as broken/static?

**Node legibility**
- Node header: short name or full unique_id? (Full `model.<pkg>.x` on every box is
  noise — `ErdTableNode.tsx` `record.label`.)
- Compact mode: are wide tables collapsed to key columns + "+N more"? Is the
  center compact but neighbors bloated?

**Layout (snowflake)**
- Is the radial layout actually used (hub centered + rings), or a dagre strip?
- Does a many-FK hub blow up the ring radius? Overlaps?

**Interaction**
- Does the toolbar **focus search resolve what the user types** (short name, not
  just full id/label)? Type the displayed name and confirm it focuses.
- Schema filter narrows the set? Edge-click highlight works? Lock toggle?
- Full-screen present on **both** the overview AND the model-page ERD?

**Theming & consistency**
- Dark mode: do node bodies/borders adopt the theme, or stay hardcoded light?
- Do the two ERD surfaces behave consistently (controls, layout, sizing)?

**Scale**
- On a 100s-of-tables project: does it stay responsive (lazy
  `onlyRenderVisibleElements`)? Any freeze on load/pan?

## Step 5 — report

Emit a severity-graded findings list (🔴 bug / 🟡 UX / 🟢 nit), each with: what
you saw, the screenshot it's in, the likely code location (`file:symbol`), and a
concrete fix. End by offering to implement the fixes (all / high-severity / none).
Do **not** change product code during the review.

## Cleanup

Kill the review server (`lsof -ti:8010 | xargs kill`) and delete any temp
Playwright script. Leave the user's `dbdocs serve` running if they started one.

## Known ERD UX issues to check for (as of 2026-06-20)

These were live findings — verify whether they're still present:

- Node headers render the **full unique_id**, not the short name (clutter).
- Focus search matches only `id`/`label` exact/startsWith — typing the **short
  name doesn't focus** (`erdFocusId` in GraphApp.tsx).
- **Dark mode**: `.dbd-erd` table nodes stay white (hardcoded light bg in
  `graph.css`).
- Fit-view sizing (`ERD_FIT_FULL` vs `ERD_FIT_FOCUSED`, GraphApp.tsx): the **full
  (unfocused) ERD must fit ALL tables** so the whole diagram + relationships are
  visible — a `minZoom` floor there is a bug (it zooms into the hub and hides
  everything else). The 0.5 floor only applies to a **focused** small neighborhood.
  Verify the unfocused overview shows the full snowflake, not one giant table.
