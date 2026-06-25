---
name: semantic-layer-rendering
description: Semantic-layer extraction bugs fixed (enum .value, object .name, schema_name) and client-side cross-linking added (metric↔metric, metric↔semantic_model, sm→metrics) via service.js accessors
metadata:
  type: project
---

Two concerns: extraction bug fixes and cross-link rendering.

**Why:** Semantic-layer node pages were functional but the data was corrupted by Pydantic enum reprs (`Type13.derived`), object reprs (`name='...' filter=None`), and a wrong schema attribute (`<bound method BaseModel.schema ...>`).

**Part A — extraction bugs fixed in `dbdocs/extract/nodes.py`:**

- `_enum_value(val)` — returns `val.value` when the value has `.value` (Pydantic enum), else pass-through. Applied to: `metric.type`, `dimension.type`, `entity.type`, `measure.agg`, `exposure.type`/`maturity`, `export_config.export_as`.
- `_object_name(val)` — returns `str(val.name)` when val has `.name` (Measure/MetricInput), else `str(val)`. Applied to `type_params.measure`/`numerator`/`denominator` and items in `metrics`/`input_measures` lists.
- **Export config schema gotcha:** `Config58` uses `schema_name` (not `schema_`). `_export_item` reads `schema_name` first, falls back to `schema_`. The `schema_` alias is only on manifest nodes, not export configs.
- `_metric_type_params` now also emits `input_measures` (was silently dropped before).
- `_sm_items` uses `str(_enum_value(val))` so all SM component type/agg enums are unwrapped.

**Part B — cross-linking added (client-side, zero payload growth):**

Three DOM-free accessors added to `service.js`:
- `metricByName(name)` — metric short name → `{id, label}` or null
- `semanticModelForMeasure(measureName)` — measure name → owning semantic_model `{id, label}` or null
- `metricsForSemanticModel(nodeId)` — reverse: all metrics whose `input_measures` overlap with a semantic model's declared measures

`input_measures` is the reliable cross-link key — always emitted by Python, covers all metric types.

`ui.js` changes:
- `metricNameLink(name)` / `measureNameLink(name)` — new helpers returning dep-chip anchors
- `renderMetricNode` — `type_params.metrics` → metric deep links; `type_params.measure`/`numerator`/`denominator`/`input_measures` → semantic_model deep links
- `renderSemanticModelNode` — new "Metrics built on this model" section
- `renderSavedQueryNode` — metrics list → metric deep links

**How to apply:**
- Any new semantic-layer field read from `artifact_parser` objects: check if it could be an enum (use `_enum_value`) or a named sub-object (use `_object_name`).
- Export config schema is `schema_name`, not `schema_` — the dbterd alias is on manifest nodes only.
- Cross-links always resolve client-side from the nodes dict; never pre-ship extra id maps in the payload.

[[non-physical-resource-nodes]]
