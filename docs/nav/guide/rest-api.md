# Static REST API

Every `dbdocs generate` writes an addressable JSON API tree under
`<output_dir>/api/v1/`, built from the **same** data dict that powers the SPA —
not a second render path. Any static host serves the files as-is, so AI agents,
MCP servers, and CI scripts can consume your documentation headless, without
parsing a line of HTML.

It ships automatically. There's no flag to enable, nothing to stand up — if you
generated a site, you already have an API sitting next to it.

## The tree

```
api/v1/
├── index.json                     # entry point: metadata, counts, node list
├── lineage.json                   # node-level edges / parents / children
├── health.json                    # the project Health Check
├── column-lineage.json            # whole-graph column lineage (both directions)
├── nodes/
│   └── <unique_id>.json           # one self-contained file per node
└── schema/
    ├── index.schema.json          # JSON Schema (draft 2020-12), one per doc type
    ├── node.schema.json
    ├── lineage.schema.json
    ├── health.schema.json
    └── column-lineage.schema.json
```

## Entry point — `index.json`

The front door. It carries the site `metadata`, per-resource-type `counts`, the
build's `generated_at` timestamp, and a `nodes` array of lightweight summaries —
each with a **relative** `node_url` (`nodes/<id>.json`) so the tree works on any
base path, including versioned/aliased deploys.

```jsonc
{
  "$schema": "schema/index.schema.json",
  "metadata": { "site_name": "…", "adapter_type": "snowflake", "erd_algo": "model_contract", … },
  "counts": { "model": 15, "metric": 19, "test": 29, … },
  "generated_at": "2026-06-25 18:15:00",
  "nodes": [
    {
      "$schema": "schema/node.schema.json",
      "id": "model.jaffle_shop.orders",
      "name": "orders",
      "label": "orders",
      "resource_type": "model",
      "database": "shaman",
      "schema": "marts",
      "description": "…",
      "node_url": "nodes/model.jaffle_shop.orders.json"
    }
  ]
}
```

## Per-node — `nodes/<unique_id>.json`

One file per node, and **self-contained on purpose**: a single fetch gives an
agent both lineage directions and both column-lineage directions — no graph
traversal required. Beyond the full node record (columns, code, stats, tags,
materialization, owner, …) each file adds:

| Field                  | Meaning                                                          |
|------------------------|------------------------------------------------------------------|
| `depends_on`           | This node's upstream parents (from `lineage.parents`).           |
| `referenced_by`        | This node's downstream children (from `lineage.children`).       |
| `columnLineage`        | Upstream column lineage for *this* node's columns.               |
| `column_referenced_by` | Downstream columns that depend on this node's columns (impact).  |

## Whole-graph documents

- **`lineage.json`** — `{$schema, edges, parents, children}`: the node-level
  lineage graph in full.
- **`column-lineage.json`** — `{$schema, skipped, edges, children}`. `edges` is
  the upstream map (each `node.column` lists what it derives from); `children` is
  its inversion (each upstream column lists the downstream columns that depend on
  it — the impact-analysis direction). `skipped` is the count of models that
  could not be parsed for column lineage.
- **`health.json`** — the project Health Check: the six
  [dbt-project-evaluator](https://dbt-labs.github.io/dbt-project-evaluator/)
  dimensions plus, when a `run_results.json` was present, the per-test detail.

## Schemas & validation

Every emitted document carries a **relative `$schema` self-pointer**, so any
JSON-Schema-aware tool can validate a document against its contract without a
network round-trip — and the pointer survives a versioned or aliased deploy base
path. The schemas under `schema/` are hand-authored JSON Schema (draft 2020-12)
and are the normative contract; a drift test in the test suite keeps them honest
against what `generate` actually writes.

```bash
# Validate a node document with check-jsonschema (pipx install check-jsonschema)
check-jsonschema --schemafile site/api/v1/schema/node.schema.json \
  site/api/v1/nodes/model.jaffle_shop.orders.json
```

## Determinism

Every file is serialized with sorted keys and compact separators, identical to
the gzip payload, so re-running `generate` on unchanged artifacts produces
byte-for-byte identical output — diffable in CI, friendly to caching. (The
`generated_at` timestamp is the one field that moves between runs.)

## Try it on the demo

The live demo publishes its API tree too — for example,
[`api/v1/index.json`](https://dbdocs.datnguye.me/latest/demo/latest/api/v1/index.json)
and a
[node document](https://dbdocs.datnguye.me/latest/demo/latest/api/v1/nodes/model.jaffle_shop.orders.json).
