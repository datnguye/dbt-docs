---
description: Cut a PyPI release of dbdocs via the release-manager agent and the release skill.
---

Delegate the release to the `release-manager` agent. It reads its local memory
of prior releases and follows `.claude/skills/release/SKILL.md` exactly:
pre-flight (clean main, lint, 100% test coverage, wheel contains the bundled
templates), version selection, GitHub Release creation (which tags and triggers
the PyPI publish in CI), and post-publish verification.

Do **not** create the GitHub Release without explicit user confirmation of the
version. Never publish to PyPI locally — that's CI-only.
