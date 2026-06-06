---
description: Deploy a versioned dbdocs site with hand-rolled directory versioning.
---

Deploy a named version of the site. There is no mike — versioning is a plain
directory layout under `output_dir` that any static host serves as-is.

```
uv run dbdocs deploy --version <X.Y> [--alias latest] [--title T] [--push]
```

- `--version` (required) — the version label, e.g. `1.2`. Generates a fresh
  build into `site/<version>/`.
- `--alias` — a moving alias, e.g. `latest`; the build is also copied to
  `site/<alias>/` and the alias is moved off any older version.
- `--title` — display title for this version (defaults to the version label).
- It updates `site/versions.json` (the index the SPA's version dropdown reads).
- `--push` is **off by default**. Pushing publishes `output_dir` to the
  `gh-pages` branch via git (force-commit + force-push) — outward-facing, so
  only pass `--push` when the user has explicitly confirmed they want to
  publish. Without it, the deploy stays local.

Report the deployed version and alias, the directories written
(`site/<version>/`, `site/versions.json`, any alias dir), and whether it was
pushed.
