---
name: per-column-tests
description: Column records carry defined dbt tests via shared build_column_tests_index; health extractor shares manifest_test_node_metadata
metadata:
  type: project
---

Each column record in the `nodes` data dict now has a `tests: [test_type, ...]` field (sorted list, empty when none). Built once per `build_nodes` call via `build_column_tests_index(manifest)` in `dbdocs/extract/tests_index.py`.

The same module exports `manifest_test_node_metadata(node) -> (test_type, attached_node, column_name)` — the single place that reads `test_metadata.name`, `attached_node`, `column_name` from a manifest test node. `HealthCheckExtractor._resolve_metadata` now imports and calls this helper instead of duplicating the field access.

Table-level tests (no `column_name`) are excluded from the per-column index intentionally.

The SPA renders test badges with `class="badge test"` in the Columns table (new "Tests" column after "Tags"). CSS: `.badge.test` uses `--status-pass-bg/fg/bd` variables (green tone, light/dark mode aware).

**Why:** Native dbt docs shows tests per column; surfacing them brings dbdocs to parity without any new CLI flag or data-dict schema addition beyond the `tests` list on each column.

**How to apply:** To add a new per-column manifest annotation, follow the same `build_column_tests_index` pattern: build a `{node_id: {col_lower: value}}` index once in `build_nodes`, pass it down to `_columns`, and add the field to `_column_entry`. Don't rebuild per column or per node.

[[node-detail-fields]]
