---
name: non-physical-resource-nodes
description: Metrics/semantic_models/saved_queries/unit_tests/exposures/analyses/operations are first-class nav pages; key decisions: macro exclusion, Semantic Layer tree bucket, _COLLECTION_ATTRS mapping, LineageGraph extended to all types
metadata:
  type: project
---

Every dbt resource type is surfaced as a navigable node page. Changes span nodes.py, graph.py, service.js, ui.js, tests, and design_patterns.md.

**Why:** Classic dbt docs coverage parity — resource types were counted on overview cards but had no nav entry or detail page.

**How to apply:**

- `_COLLECTION_ATTRS` in `nodes.py` is the single source of truth for prefix→manifest-attribute mapping. Never derive by string (`saved_query.rstrip(".")+s` = `saved_querys`). `graph.py` imports it.
- Typeless resources (metrics, semantic_models, saved_queries, unit_tests, exposures) use `database="Semantic Layer"`, `schema=resource_type` so `build_tree` groups them under one nav bucket sorted after real databases.
- Macros explicitly excluded: hundreds of package macros flood the nav; they render inline under models via `macros_used`.
- `LineageGraph._default_node_ids` includes all new types so `dependsOn`/`referencedBy` on new pages resolve. Visual DAG is unchanged (graph bundle filters by `data-rtype`).
- `ui.js renderNode` dispatches by `resource_type`; physical types route to the renamed `renderPhysicalNode` — behavior byte-identical to before.

[[semantic-layer-rendering]]
