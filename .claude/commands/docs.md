---
description: Serve the generated dbdocs site locally with a static http server.
---

Serve the generated site (run after `/generate` has produced
`site/index.html`):

```
uv run dbdocs serve            # http://127.0.0.1:8000
uv run dbdocs serve --port N   # pick a port
```

This serves the configured `output_dir` (default `site/`) with a plain stdlib
http server. Print the local URL (default http://127.0.0.1:8000).

There is **no live reload** — the site is a static, pre-built SPA. Re-run
`/generate` to pick up new artifacts, then refresh the browser. If serve finds
nothing to serve, remind the user to run `/generate` first.
