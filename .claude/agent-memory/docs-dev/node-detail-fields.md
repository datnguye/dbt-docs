---
name: node-detail-fields
description: Node details panel — extended manifest fields on node records + client-side depends-on/referenced-by chips
metadata:
  type: project
---

`_node_record` in `dbdocs/extract/nodes.py` emits 11 detail fields:
`materialization`, `meta`, `access`, `group`, `contract_enforced`, `version`,
`latest_version`, `owner`, `original_file_path`, `patch_path`, `stats`.

Two helpers were added: `_catalog_stats` (filters catalog stats to `include=True`)
and `_owner_string` (resolves owner.name → owner.email → "").

**Why:** These fields exist in dbt manifest v12 but were dropped at extraction time; surfacing them brings the node page closer to native dbt docs parity.

**How to apply:** When adding more manifest fields, follow the same defensive-`getattr` pattern in `_node_record`. The `conftest.node()` helper now accepts all these params so existing tests don't need raw SimpleNamespace.

**Depends-on / Referenced-by** derive from `DATA.lineage.parents/children` in `service.js` — zero payload growth. The two new service exports are `dependsOn(id)` and `referencedBy(id)`. `ui.js` renders them via `nodeDetailsBlock` and `nodeDepsBlock`.

**Contract** is only shown in the UI for models (`n.resource_type === "model"`) or when `n.contract_enforced === true`, to avoid showing "not enforced" noise on sources/seeds.

[[catalog-uppercases-column-keys]]
