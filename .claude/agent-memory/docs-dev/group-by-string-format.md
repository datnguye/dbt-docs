---
name: group-by-string-format
description: dbt manifest stores saved_query group_by items as string literals like "Entity('customer')" — not Python objects in current artifact_parser/jaffle_shop
metadata:
  type: project
---

In the jaffle_shop v12 manifest, `saved_queries[*].query_params.group_by` items are already plain strings like `"Entity('customer')"` or `"TimeDimension('metric_time', 'day')"` — the dbt manifest already serialized them this way.

**Why:** The artifact_parser parses these as-is from the manifest JSON. The task description suggested they'd be Python objects with `.name`, but in practice they arrive pre-stringified.

**How to apply:** `_object_name(g)` is still the right call (handles both cases). For plain strings it returns `str(val)` unchanged. If a future artifact_parser version returns structured objects, `.name` extraction will kick in automatically. The displayed value `"Entity('customer')"` is the actual dbt manifest format — not a bug in our code.
