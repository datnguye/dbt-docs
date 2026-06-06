---
description: Build the self-contained dbdocs SPA into ./site from the dbt artifacts.
---

Build the site:

```
uv run dbdocs generate                       # uses dbdocs.yml / defaults
uv run dbdocs generate --output-dir <dir>    # override output_dir
uv run dbdocs generate --dialect <dialect>   # override the SQL dialect
```

This loads `dbdocs.yml` (if present), reads the dbt artifacts from the
configured `target_dir` (`manifest.json` / `catalog.json`), derives the project
data dict (nodes + columns, node-level lineage, column-level lineage via
sqlglot, Mermaid ERDs, nav tree), and writes a **single self-contained**
`site/index.html` with that data base64-injected as `window.dbdocsData`, plus a
debug `site/dbdocs-data.json` and the vendored JS assets. It does not serve —
use `/docs` for that.

`--dialect` overrides the SQL dialect used for column-lineage parsing
(otherwise it follows the artifact's `adapter_type`).

After it runs, summarize what landed under `site/` (or `output_dir`):
- `site/index.html` with the injected `window.dbdocsData`
- `site/dbdocs-data.json` (the same data dict, for debugging)
- the node count and the column-lineage edge count (the CLI logs both)

If it errors because artifacts are missing, tell the user to run `dbt docs
generate` in their dbt project first so `manifest.json` and `catalog.json`
exist in the configured `target_dir`.
