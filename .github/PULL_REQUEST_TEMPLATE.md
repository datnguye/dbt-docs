<!--
  Thanks for contributing to dbdocs! Keep the description tight and the checklist
  honest — a green checklist is what gets a PR reviewed fast. See CONTRIBUTING.md.
-->

## What & why

<!-- What does this change, and what problem does it solve? Link the issue. -->

Closes #

## Type of change

- [ ] 🐞 Bug fix (non-breaking change that fixes an issue)
- [ ] ✨ Feature (non-breaking change that adds capability)
- [ ] 💥 Breaking change (existing behavior changes)
- [ ] 🧹 Refactor / internal (no user-facing change)
- [ ] 📖 Docs only

## Area

- [ ] CLI (`generate` / `serve` / `deploy`)
- [ ] `extract/` (nodes / erd / graph / column_lineage / health)
- [ ] `site/` (data dict / builder / 3-tier SPA / deploy)
- [ ] `frontend/` (React Flow graph bundle)
- [ ] Config (`dbdocs.yml`) / packaging / CI / docs

## How to test

<!-- The exact commands a reviewer runs to see this working. -->

```bash
task generate && task serve   # then open ...
```

## Checklist

- [ ] `task lint` passes (`ruff format --check` + `ruff check`).
- [ ] `task test` passes at **100% coverage** (the gate is enforced in CI).
- [ ] I followed the **load-bearing patterns** in `.claude/design_patterns.md` (extended an existing seam, didn't fork one). If I added/removed a pattern, I updated that doc + its TOC in this PR.
- [ ] **Data-dict / SPA changes** keep producer ↔ consumer in sync (Python builder ⇄ the 3-tier `assets/js/` modules) and don't re-inline the payload.
- [ ] **Graph-UI changes** rebuilt the committed bundle (`task frontend:build`) and I committed `dbdocs/site/bundle/assets/graph/`.
- [ ] New files under `dbdocs/site/bundle/**` are covered by the `pyproject.toml` artifacts glob (so they ship in the wheel).
- [ ] Docs / `dbdocs.yml.example` updated for any new config knob or CLI flag.

## Screenshots / notes

<!-- For site changes, a before/after screenshot. Anything else reviewers should know. -->
