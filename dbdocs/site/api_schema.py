"""JSON Schema literals for the static ``api/v1/`` REST surface.

Each constant describes the shape of one doc type emitted by
``ReportBuilder._write_api``.  They are hand-authored (not generated from
runtime data), so they are the *normative* source of truth for what the API
promises.  ``_write_api`` writes them verbatim as ``api/v1/schema/*.json``
and injects a relative ``$schema`` self-pointer into every emitted doc.

Keep schema definitions loose on extension points (``additionalProperties:
true``) so per-resource-type sub-dicts (metric/exposure/…) and future fields
never break validation — the schema documents the *stable* contract, not every
optional key.
"""

INDEX_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "index.schema.json",
    "title": "dbdocs api/v1/index.json",
    "description": "Entry-point index for the dbdocs static REST API. Lists every node "
    "stub and surface-level metadata for a generated documentation site.",
    "type": "object",
    "required": ["$schema", "metadata", "counts", "generated_at", "nodes"],
    "additionalProperties": True,
    "properties": {
        "$schema": {
            "type": "string",
            "description": "Relative path to this document's JSON Schema.",
        },
        "metadata": {
            "type": "object",
            "description": "Site-level metadata copied from dbdocs.yml plus "
            "adapter/dialect/erd_algo resolved at generate time.",
            "additionalProperties": True,
        },
        "counts": {
            "type": "object",
            "description": "Count of every dbt resource type present in the project, "
            "keyed by resource type name (e.g. 'model', 'source', 'test').",
            "additionalProperties": {"type": "integer"},
        },
        "generated_at": {
            "type": "string",
            "description": "ISO-8601 timestamp of when the site was generated.",
        },
        "nodes": {
            "type": "array",
            "description": "One stub per node in the project. Each stub holds enough "
            "data to render a search result or nav entry; follow node_url for the "
            "full record.",
            "items": {
                "type": "object",
                "required": ["id", "resource_type", "node_url"],
                "additionalProperties": True,
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "The dbt unique_id (e.g. 'model.jaffle_shop.orders').",
                    },
                    "name": {"type": "string", "description": "Short model/source name."},
                    "label": {
                        "type": "string",
                        "description": "Display label (alias or name).",
                    },
                    "resource_type": {
                        "type": "string",
                        "description": "dbt resource type (model, source, seed, …).",
                    },
                    "database": {
                        "type": "string",
                        "description": "Warehouse database the node lives in.",
                    },
                    "schema": {
                        "type": "string",
                        "description": "Warehouse schema the node lives in.",
                    },
                    "description": {
                        "type": "string",
                        "description": "YAML docstring for this node.",
                    },
                    "node_url": {
                        "type": "string",
                        "description": "Relative URL to the full per-node JSON file.",
                    },
                },
            },
        },
    },
}

NODE_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "node.schema.json",
    "title": "dbdocs api/v1/nodes/<id>.json",
    "description": "Full record for a single dbt node, enriched with lineage and "
    "column-level lineage slices.  Per-resource-type payload sub-dicts "
    "(metric, exposure, semantic_model, …) are additionalProperties so "
    "future resource types never fail validation.",
    "type": "object",
    "required": ["$schema", "id", "resource_type"],
    "additionalProperties": True,
    "properties": {
        "$schema": {
            "type": "string",
            "description": "Relative path to this document's JSON Schema.",
        },
        "id": {
            "type": "string",
            "description": "The dbt unique_id (e.g. 'model.jaffle_shop.orders').",
        },
        "name": {"type": "string", "description": "Short model/source name."},
        "label": {"type": "string", "description": "Display label (alias or name)."},
        "resource_type": {
            "type": "string",
            "description": "dbt resource type (model, source, seed, snapshot, "
            "analysis, operation, metric, semantic_model, saved_query, "
            "unit_test, exposure).",
        },
        "database": {
            "type": "string",
            "description": "Warehouse database.  Empty string for typeless resources "
            "(metrics, exposures, …) that have no physical location.",
        },
        "schema": {
            "type": "string",
            "description": "Warehouse schema.  Empty string for typeless resources.",
        },
        "description": {"type": "string", "description": "YAML docstring for this node."},
        "materialization": {
            "type": "string",
            "description": "dbt materialization strategy (view, table, incremental, …). "
            "Empty string for non-physical resource types.",
        },
        "meta": {
            "type": "object",
            "description": "Arbitrary user-defined meta dict from YAML.",
            "additionalProperties": True,
        },
        "tags": {
            "type": "array",
            "description": "List of YAML tags applied to this node.",
            "items": {"type": "string"},
        },
        "columns": {
            "type": "array",
            "description": "Column records for physical nodes (model/source/seed/snapshot). "
            "Absent or empty for non-physical types.",
            "items": {
                "type": "object",
                "required": ["name"],
                "additionalProperties": True,
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string", "description": "Warehouse column type."},
                    "description": {"type": "string"},
                    "tests": {
                        "type": "array",
                        "description": "dbt data-test types defined for this column "
                        "(not_null, unique, accepted_values, …).",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "depends_on": {
            "type": "array",
            "description": "List of unique_ids this node depends on (upstream parents). "
            "Derived from the lineage graph — not re-stored in the SPA payload.",
            "items": {"type": "string"},
        },
        "referenced_by": {
            "type": "array",
            "description": "List of unique_ids that depend on this node (downstream children). "
            "Derived from the lineage graph — not re-stored in the SPA payload.",
            "items": {"type": "string"},
        },
        "columnLineage": {
            "type": "object",
            "description": "Slice of the upstream column-level lineage map for this node. "
            "Keys are 'unique_id.column_name'; values list upstream column references.",
            "additionalProperties": True,
        },
        "column_referenced_by": {
            "type": "object",
            "description": "Slice of the downstream column-level lineage map for this node. "
            "Keys are 'unique_id.column_name'; values list downstream column references "
            "(columns in other nodes that derive from this node's columns).",
            "additionalProperties": True,
        },
    },
}

LINEAGE_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "lineage.schema.json",
    "title": "dbdocs api/v1/lineage.json",
    "description": "Complete node-level lineage graph for the project: a flat edge list "
    "plus pre-indexed parent and child adjacency maps.",
    "type": "object",
    "required": ["$schema", "edges", "parents", "children"],
    "additionalProperties": True,
    "properties": {
        "$schema": {
            "type": "string",
            "description": "Relative path to this document's JSON Schema.",
        },
        "edges": {
            "type": "array",
            "description": "Directed edges in the node-level DAG.  Each edge is "
            "{'source': upstream_id, 'target': downstream_id}.",
            "items": {
                "type": "object",
                "required": ["source", "target"],
                "additionalProperties": True,
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "unique_id of the upstream (parent) node.",
                    },
                    "target": {
                        "type": "string",
                        "description": "unique_id of the downstream (child) node.",
                    },
                },
            },
        },
        "parents": {
            "type": "object",
            "description": "Adjacency map: node id → list of parent unique_ids.",
            "additionalProperties": {"type": "array", "items": {"type": "string"}},
        },
        "children": {
            "type": "object",
            "description": "Adjacency map: node id → list of child unique_ids.",
            "additionalProperties": {"type": "array", "items": {"type": "string"}},
        },
    },
}

HEALTH_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "health.schema.json",
    "title": "dbdocs api/v1/health.json",
    "description": "Health-check section derived from run_results.json and the manifest. "
    "Present even when run_results.json is absent (fail-soft, testResults=null). "
    "The shape of each dimension and testResults entry is rich and may evolve; "
    "additionalProperties is true throughout.",
    "type": "object",
    "required": ["$schema", "enabled"],
    "additionalProperties": True,
    "properties": {
        "$schema": {
            "type": "string",
            "description": "Relative path to this document's JSON Schema.",
        },
        "enabled": {
            "type": "boolean",
            "description": "True when health data is available (at least one result "
            "was processed).  False means generate ran without a run_results.json.",
        },
        "dimensions": {
            "type": "object",
            "description": "One entry per DPE dimension "
            "(testing, modeling, documentation, structure, performance, governance). "
            "Each value is {issues, checked, findings}.",
            "additionalProperties": True,
        },
        "testResults": {
            "description": "Per-test pass/fail detail from run_results.json, or null "
            "when the file was absent.",
            "oneOf": [
                {
                    "type": "object",
                    "description": "Test results present.",
                    "additionalProperties": True,
                    "properties": {
                        "summary": {
                            "type": "object",
                            "description": "Tally of test outcomes.",
                            "additionalProperties": True,
                            "properties": {
                                "pass": {"type": "integer"},
                                "fail": {"type": "integer"},
                                "skipped": {"type": "integer"},
                                "total": {"type": "integer"},
                            },
                        },
                        "results": {
                            "type": "array",
                            "description": "One entry per test result.",
                            "items": {"type": "object", "additionalProperties": True},
                        },
                    },
                },
                {"type": "null"},
            ],
        },
        "note": {
            "type": "string",
            "description": "Human-readable note set when run_results.json was absent.",
        },
    },
}

_COLUMN_REF_ITEM: dict = {
    "type": "object",
    "required": ["node", "column"],
    "additionalProperties": False,
    "properties": {
        "node": {
            "type": "string",
            "description": "dbt unique_id of the referenced node.",
        },
        "column": {
            "type": "string",
            "description": "Column name on the referenced node.",
        },
    },
}

COLUMN_LINEAGE_SCHEMA: dict = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "column-lineage.schema.json",
    "title": "dbdocs api/v1/column-lineage.json",
    "description": "Whole-graph column-level lineage for the project. "
    "'edges' maps each output column to its upstream sources (the direction "
    "data flows from). 'children' is the inverted downstream map: for each "
    "upstream column, which downstream columns depend on it. "
    "'skipped' reports how many models were not parsed (fail-soft gaps).",
    "type": "object",
    "required": ["$schema", "skipped", "edges", "children"],
    "additionalProperties": True,
    "properties": {
        "$schema": {
            "type": "string",
            "description": "Relative path to this document's JSON Schema.",
        },
        "skipped": {
            "type": "integer",
            "description": "Number of models whose column lineage could not be parsed "
            "(sqlglot fail-soft). Zero means all models were parsed successfully.",
        },
        "edges": {
            "type": "object",
            "description": "Upstream column lineage map. "
            "Keys are 'unique_id.column_name' for each output column; "
            "values list the upstream column references that column derives from.",
            "additionalProperties": {
                "type": "array",
                "items": _COLUMN_REF_ITEM,
            },
        },
        "children": {
            "type": "object",
            "description": "Downstream column lineage map (inverted from 'edges'). "
            "Keys are 'unique_id.column_name' for each upstream column; "
            "values list the downstream columns that depend on it.",
            "additionalProperties": {
                "type": "array",
                "items": _COLUMN_REF_ITEM,
            },
        },
    },
}

SCHEMA_FILES: dict = {
    "index.schema.json": INDEX_SCHEMA,
    "node.schema.json": NODE_SCHEMA,
    "lineage.schema.json": LINEAGE_SCHEMA,
    "health.schema.json": HEALTH_SCHEMA,
    "column-lineage.schema.json": COLUMN_LINEAGE_SCHEMA,
}
