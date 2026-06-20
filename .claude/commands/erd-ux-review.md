---
description: Review the rendered dbdocs ERD's UI/UX (overview + model-page "Related ERD") against a real dbt project — install the local build, generate, serve, screenshot, and report severity-graded findings.
---

Use the **erd-ux-review** skill to review the generated ERD's UI/UX against a
real dbt project.

**First, ask the user for the dbt project path**, suggesting the bundled
`tests/fixtures/big_project` (96-model snowflake) as the recommended default — it
needs no setup and surfaces ERD scale issues. Offer it as the first option, but
let the user point at any other project (one with `target/manifest.json` +
`target/catalog.json`). If `$ARGUMENTS` already contains a path, use it but
confirm the artifacts exist before proceeding.

Then follow the skill:

1. Rebuild the bundle if `frontend/` changed (`task frontend:build`), then
   `pip install -e` this repo into the project's venv and `dbdocs generate`.
2. Serve with a **threaded** static server for the browser (the stdlib
   `dbdocs serve` deadlocks under headless automation) — run `dbdocs serve` too
   only if the user wants to browse it themselves.
3. Drive Playwright to screenshot both ERD surfaces (overview + model page),
   light/dark, default/focused, and read the PNGs back.
4. Grade against the skill's checklist — readability & first paint, node
   legibility, snowflake layout, interaction, theming/consistency, scale.
5. Emit a severity-graded findings report (🔴 bug / 🟡 UX / 🟢 nit) with
   screenshot + `file:symbol` evidence and a concrete fix each.

Do **not** modify product code during the review. End by offering to implement
the fixes (all / high-severity / none). Clean up the review server and any temp
Playwright script; leave the user's `dbdocs serve` running.
