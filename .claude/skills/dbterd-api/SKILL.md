---
name: dbterd-api
description: Use when reading dbt artifacts or generating ERDs inside dbdocs — parsing manifest.json/catalog.json and producing Mermaid ERDs via the dbterd Python API for the generated Markdown pages.
---

# Consuming dbterd in dbdocs

`dbterd` is a library that turns dbt artifacts into ERDs. `dbdocs` uses it as a
**library**, never via its CLI. Two surfaces are in play in
`dbdocs/modules/standard.py`:

## 1. Loading artifacts

```python
from dbterd.helpers import file

manifest = file.read_manifest(path=target_path)   # parsed manifest.json
catalog = file.read_catalog(path=target_path)     # parsed catalog.json
```

Both expect a dbt `target/` directory containing `manifest.json` and
`catalog.json`. `manifest` exposes `.nodes` and `.sources` dicts keyed by dbt
`unique_id`; each node has `.unique_id`, `.description`, `.tags`, `.columns`.
`catalog` mirrors that with warehouse column types (`.columns[col].type`).

## 2. Rendering ERDs

```python
from dbterd.api import DbtErd

DbtErd(target="mermaid").get_erd()                  # whole-project Mermaid ERD
DbtErd(target="mermaid").get_model_erd(unique_id)   # one model's neighborhood
```

We render to **Mermaid** because mkdocs-material renders Mermaid fenced blocks
natively. The returned value is formatted text destined straight for a Markdown
template — do not try to post-process it into structured data.

## Honoring the project's `.dbterd.yml`

`dbdocs` does **not** hardcode the ERD shape. `standard.py::_build_erd()` calls
`dbterd.cli.config.load_config()` (dbterd's own loader — resolves `.dbterd.yml`
or `pyproject.toml`'s `[tool.dbterd]` from the cwd, returning `DbtErd` kwargs
with underscore keys) and forwards everything except `target` into
`DbtErd(target="mermaid", **kwargs)`. So a project's `.dbterd.yml` (`algo`,
`entity_name_format`, `resource_type`, `select`/`exclude`, …) controls the
catalog ERD; `target` is always forced to `mermaid` because the site renders
Mermaid. No config file → graceful dbterd defaults.

## Rules

1. **Do not hand-roll manifest/catalog parsing.** Use `file.read_manifest` /
   `file.read_catalog`.
2. **Do not shell out to the `dbterd` CLI.** We are a library consumer.
3. **Guard missing catalog columns.** A source/model present in the manifest may
   be absent from the catalog — see the `node in catalog.sources` guards in
   `standard.py`. Default to empty columns rather than raising.
4. **Iterate manifest keys with a prefix filter** (`str(x).startswith("model")`)
   to separate models from other resource types.

## Artifact stability across dbt versions (incl. dbt Core 2.0)

`dbterd` parses `manifest.json` / `catalog.json` via `dbt_artifacts_parser`,
which supports **manifest schema v1–v12** and auto-detects the version.
`file.read_manifest(path, version=...)` lets you pin a version but normally you
let it auto-detect.

This means **dbt Core 2.0 does not break dbdocs** — the manifest/catalog formats
remain versioned-and-parsed, not a breaking change. Keep relying on the parser;
do not hand-special-case a dbt version.

## Pinning

The `dbterd` dependency floor is in `pyproject.toml` (`dbterd>=1.26`, which
requires Python `>=3.10`). Before relying on a new `dbterd` symbol, confirm it
exists at that floor — prefer the context7 MCP docs over guessing from training
data.
