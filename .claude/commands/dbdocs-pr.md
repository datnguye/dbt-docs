---
description: Open a GitHub PR for the current branch with a body that follows .github/PULL_REQUEST_TEMPLATE.md, filled from the actual diff and with the checklist verified against the repo gates.
---

Use the **dbdocs-pr** skill to open a pull request for the current branch.

Target (in order of precedence):
1. If `$ARGUMENTS` names a base branch, an issue to close, draft, or a title, use it.
2. Otherwise PR the current branch against the repo's default branch.

Follow the skill: run the **pre-flight** and, when HEAD is `main` (or the repo
default), **create a feature branch** carrying the working tree onto a
`<type>/<slug>` name derived from the change (confirm the name first; use
`$ARGUMENTS` verbatim if a name is given). Then run the **gates** (`ruff` +
`pytest` at 100% coverage) and fold the real results into the checklist,
**compose the body from `.github/PULL_REQUEST_TEMPLATE.md`** — tick the one
correct Type box, every touched Area, and only the checklist items you actually
verified — then `git push -u origin HEAD` and `gh pr create`.

Creating a PR is outward-facing: confirm anything ambiguous (base, draft vs
ready, which commits belong) before pushing. If the gates are red, stop and offer
to fix or to open a **draft** with the failures called out — never tick a red box.
End with the PR URL.
