---
name: static-api-v1-surface
description: Static REST api/v1 tree — layout, serializer DRY, unsafe-id guard, pyproject glob is untouched
metadata:
  type: project
---

`generate()` writes `api/v1/{index.json, lineage.json, health.json, nodes/<id>.json}` from the same `data` dict the SPA uses. Key decisions:

- `_serialize(value)` is the canonical serializer on `ReportBuilder`, reused for both the gzip payload and all api/ files.
- `_write_api(out, data)` is called after `rmtree + copytree`, so api/ is created fresh on each run with `mkdir(parents=True, exist_ok=True)`.
- `_UNSAFE_ID_CHARS = frozenset("/\\")` guards against path-traversal writes — skips + warns on any node whose unique_id contains `/` or `\`.
- Per-node file is enriched with `depends_on` (lineage.parents[id]), `referenced_by` (lineage.children[id]), `columnLineage` (slice of columnLineage keys starting with `<id>.`).
- The `pyproject.toml` artifacts glob (`dbdocs/site/bundle/**/*`) is unchanged — api/ is runtime output, not wheel content.

**Why:** The static `api/v1/` JSON tree gives AI agents / MCP servers headless access to project metadata without parsing HTML.

**How to apply:** Do not add a second data render path or second serializer. Extend `_write_api` for new api endpoints. Run `task test` after any change to builder.py.
