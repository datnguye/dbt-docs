"""Synthesize standard dbt artifacts (manifest v12 / catalog v1 / run_results v6)
from the parquet information schema.

Merge rule, applied per record and field: the parquet set decides which records
exist, a non-empty parquet value wins, and the matching JSON artifact record (when
one was supplied) fills whatever parquet left empty. Column types are the one
exception: warehouse ``catalog.json`` type, then ``data_type_actual``, then the
declared type, then ``data_type_inferred``.
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from artifact_parser.dbt_info_schema.base import decode_json_column

from dbdocs.sources.info_schema.reader import InfoSchemaReader

MANIFEST_SCHEMA = "https://schemas.getdbt.com/dbt/manifest/v12.json"
CATALOG_SCHEMA = "https://schemas.getdbt.com/dbt/catalog/v1.json"
RUN_RESULTS_SCHEMA = "https://schemas.getdbt.com/dbt/run-results/v6.json"

_NODE_TABLES = (
    ("dbt.models", "model"),
    ("dbt.seeds", "seed"),
    ("dbt.snapshots", "snapshot"),
    ("dbt.analyses", "analysis"),
    ("dbt.data_tests", "test"),
)
_DEPENDENT_SECTIONS = (
    "nodes",
    "sources",
    "unit_tests",
    "metrics",
    "semantic_models",
    "saved_queries",
    "exposures",
)
_ALL_SECTIONS = _DEPENDENT_SECTIONS + ("macros", "docs", "groups")
_COLUMN_DEFAULTS = {"description": "", "meta": {}, "tags": [], "constraints": []}
_READ_ONLY_EVOLUTIONS = frozenset({"scan"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty(value: Any) -> bool:
    return value is None or (isinstance(value, (str, list, dict)) and not value)


def _compact(record: dict) -> dict:
    return {k: v for k, v in record.items() if not _empty(v)}


def _fill(base: Any, extra: Any) -> Any:
    """``base`` where it has a value, else ``extra``; dicts merge key by key."""
    if _empty(base):
        return extra
    if isinstance(base, dict) and isinstance(extra, dict):
        merged = dict(base)
        for key, value in extra.items():
            merged[key] = _fill(base.get(key), value)
        return merged
    return base


def _path(original_file_path: "str | None") -> "str | None":
    return original_file_path.split("/", 1)[-1] if original_file_path else None


def _common(row: dict, kind: str) -> dict:
    properties = row.get("properties_yml_file_path")
    package = row.get("package_name") or row["unique_id"].split(".")[1]
    return {
        "unique_id": row["unique_id"],
        "name": row.get("name"),
        "resource_type": row.get("resource_type") or kind,
        "package_name": package,
        "original_file_path": row.get("original_file_path"),
        "path": _path(row.get("original_file_path")),
        "fqn": row.get("fqn"),
        "description": row.get("description"),
        "tags": row.get("tags"),
        "meta": decode_json_column(row.get("meta")),
        "patch_path": f"{package}://{properties}" if properties else None,
    }


def _config(row: dict) -> dict:
    config = decode_json_column(row.get("config"))
    config = dict(config) if isinstance(config, dict) else {}
    config["materialized"] = row.get("materialized")
    return _compact(config)


def _physical(row: dict, kind: str) -> dict:
    compiled_code = row.get("compiled_code")
    record = _common(row, kind)
    record.update(
        database=row.get("database_name"),
        schema=row.get("schema_name"),
        alias=row.get("alias") or row.get("name"),
        relation_name=row.get("relation_name"),
        raw_code=row.get("raw_code"),
        compiled_code=compiled_code,
        compiled=True if compiled_code else None,
        compiled_path=row.get("compiled_path"),
        language=row.get("node_language"),
        config=_config(row),
        access=row.get("access"),
        group=row.get("group"),
        contract={"enforced": bool(row.get("contract_enforced"))},
        version=decode_json_column(row.get("version")),
        latest_version=decode_json_column(row.get("latest_version")),
        docs={"show": row["docs_show"]} if row.get("docs_show") is not None else None,
    )
    if kind == "test":
        record.update(
            test_metadata=_compact(
                {
                    "name": row.get("test_name"),
                    "namespace": row.get("test_definition_package"),
                    "kwargs": decode_json_column(row.get("arguments")),
                }
            ),
            column_name=row.get("column_name"),
            attached_node=row.get("node_unique_id"),
        )
    return record


def _source(row: dict, kind: str) -> dict:
    record = _physical(row, kind)
    record.update(
        source_name=row.get("source_name"),
        source_description=row.get("source_description"),
        loader=row.get("loader"),
        identifier=row.get("identifier"),
        loaded_at_field=row.get("loaded_at_field"),
        freshness=decode_json_column(row.get("freshness")),
    )
    return record


def _unit_test(row: dict, kind: str) -> dict:
    record = _common(row, kind)
    record.update(
        model=row.get("model"),
        given=decode_json_column(row.get("given")),
        expect=decode_json_column(row.get("expect")),
        overrides=decode_json_column(row.get("overrides")),
        config=decode_json_column(row.get("config")),
    )
    return record


def _metric(row: dict, kind: str) -> dict:
    record = _common(row, kind)
    record.update(
        label=row.get("label"),
        type=row.get("metric_type"),
        type_params=decode_json_column(row.get("type_params")),
        filter=decode_json_column(row.get("metric_filter")),
        time_granularity=row.get("time_granularity"),
        group=row.get("group"),
        config=decode_json_column(row.get("config")),
        created_at=row.get("created_at"),
    )
    return record


def _semantic_model(row: dict, kind: str) -> dict:
    record = _common(row, kind)
    record.update(
        label=row.get("label"),
        model=row.get("model"),
        node_relation=decode_json_column(row.get("node_relation")),
        primary_entity=row.get("primary_entity"),
        defaults=decode_json_column(row.get("defaults")),
        group=row.get("group"),
        config=decode_json_column(row.get("config")),
        created_at=row.get("created_at"),
    )
    return record


def _saved_query(row: dict, kind: str) -> dict:
    record = _common(row, kind)
    record.update(
        label=row.get("label"),
        query_params=decode_json_column(row.get("query_params")),
        exports=decode_json_column(row.get("exports")),
        group=row.get("group"),
        config=decode_json_column(row.get("config")),
        created_at=row.get("created_at"),
    )
    return record


def _exposure(row: dict, kind: str) -> dict:
    record = _common(row, kind)
    record.update(
        label=row.get("label"),
        type=row.get("exposure_type"),
        url=row.get("url"),
        maturity=row.get("maturity"),
        owner=_compact({"name": row.get("owner_name"), "email": row.get("owner_email")}),
        config=decode_json_column(row.get("config")),
        created_at=row.get("created_at"),
    )
    return record


def _group(row: dict, kind: str) -> dict:
    record = _common(row, kind)
    record["owner"] = _compact({"name": row.get("owner_name"), "email": row.get("owner_email")})
    return record


def _macro(row: dict, kind: str) -> dict:
    record = _common(row, kind)
    arguments = decode_json_column(row.get("arguments"))
    record.update(
        macro_sql=row.get("macro_sql"),
        depends_on={"macros": row.get("depends_on_macros")},
        arguments=arguments if isinstance(arguments, list) else None,
    )
    return record


def _doc(row: dict, kind: str) -> dict:
    record = _common(row, kind)
    record["block_contents"] = row.get("content")
    return record


_COLLECTIONS = (
    ("dbt.sources", "sources", "source", _source),
    ("dbt.unit_tests", "unit_tests", "unit_test", _unit_test),
    ("dbt.metrics", "metrics", "metric", _metric),
    ("dbt.semantic_models", "semantic_models", "semantic_model", _semantic_model),
    ("dbt.saved_queries", "saved_queries", "saved_query", _saved_query),
    ("dbt.exposures", "exposures", "exposure", _exposure),
    ("dbt.groups", "groups", "group", _group),
    ("dbt.macros", "macros", "macro", _macro),
    ("dbt.docs_blocks", "docs", "doc", _doc),
)

_DEFAULTS = {
    "nodes": {
        "description": "",
        "tags": [],
        "meta": {},
        "columns": {},
        "config": {},
        "checksum": {"name": "none", "checksum": ""},
    },
    "sources": {
        "description": "",
        "tags": [],
        "meta": {},
        "columns": {},
        "source_description": "",
        "loader": "",
    },
    "unit_tests": {"description": "", "tags": [], "meta": {}, "checksum": ""},
    "metrics": {"description": "", "label": "", "type_params": {}},
    "semantic_models": {"description": "", "node_relation": {}},
    "saved_queries": {"description": "", "exports": [], "query_params": {}},
    "exposures": {"description": "", "owner": {}},
    "groups": {"owner": {}},
    "macros": {"description": "", "macro_sql": ""},
    "docs": {"block_contents": ""},
}


def _group_by(rows: "list[dict]", key: str) -> "dict[str, list[dict]]":
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row[key]].append(row)
    return grouped


def _columns(reader: InfoSchemaReader) -> "dict[str, dict]":
    columns: dict[str, dict] = defaultdict(dict)
    for row in sorted(reader.table("dbt.node_columns"), key=lambda r: r.get("column_index") or 0):
        columns[row["node_unique_id"]][row["column_name"]] = _compact(
            {
                "name": row["column_name"],
                "description": row.get("description"),
                "data_type": row.get("data_type_declared"),
                "tags": row.get("tags"),
                "meta": decode_json_column(row.get("meta")),
                "granularity": row.get("granularity"),
            }
        )
    return columns


def _semantic_parts(reader: InfoSchemaReader) -> "dict[str, dict]":
    parts: dict[str, dict] = defaultdict(lambda: {"entities": [], "measures": [], "dimensions": []})
    for row in reader.table("dbt.semantic_entities"):
        parts[row["unique_id"]]["entities"].append(
            {
                "name": row["name"],
                "type": row.get("entity_type"),
                "description": row.get("description"),
                "label": row.get("label"),
                "role": row.get("entity_role"),
                "expr": row.get("expr"),
            }
        )
    for row in reader.table("dbt.semantic_measures"):
        parts[row["unique_id"]]["measures"].append(
            {
                "name": row["name"],
                "agg": row.get("agg"),
                "description": row.get("description"),
                "label": row.get("label"),
                "expr": row.get("expr"),
                "create_metric": row.get("create_metric"),
                "agg_time_dimension": row.get("agg_time_dimension"),
                "agg_params": decode_json_column(row.get("agg_params")),
                "non_additive_dimension": decode_json_column(row.get("non_additive_dimension")),
            }
        )
    for row in reader.table("dbt.semantic_dimensions"):
        granularity = row.get("time_granularity")
        parts[row["unique_id"]]["dimensions"].append(
            _compact(
                {
                    "name": row["name"],
                    "type": row.get("dimension_type"),
                    "description": row.get("description"),
                    "label": row.get("label"),
                    "expr": row.get("expr"),
                    "is_partition": row.get("is_partition"),
                    "type_params": {
                        "time_granularity": granularity,
                        "validity_params": decode_json_column(row.get("validity_params")),
                    }
                    if granularity
                    else None,
                }
            )
        )
    return parts


def _edges(reader: InfoSchemaReader) -> "tuple[dict, dict]":
    parents: dict[str, list[str]] = defaultdict(list)
    children: dict[str, list[str]] = defaultdict(list)
    for row in reader.table("dbt.edges"):
        parent, child = row["parent_unique_id"], row["child_unique_id"]
        if parent.startswith("macro.") or child.startswith("macro."):
            continue
        parents[child].append(parent)
        children[parent].append(child)
    return parents, children


def _known_json_records(json_manifest: "dict | None") -> "dict[str, dict]":
    known: dict[str, dict] = {}
    for section in _ALL_SECTIONS:
        known.update((json_manifest or {}).get(section) or {})
    return known


def _finish(record: dict, section: str, json_record: "dict | None") -> dict:
    merged = _fill(_compact(record), json_record or {})
    for key, value in _DEFAULTS[section].items():
        merged.setdefault(key, value)
    merged.setdefault("path", "")
    merged.setdefault("original_file_path", "")
    if section in _DEPENDENT_SECTIONS:
        merged.setdefault("fqn", [merged.get("package_name"), merged.get("name")])
    if section == "unit_tests" and isinstance(merged["checksum"], dict):
        merged["checksum"] = merged["checksum"].get("checksum") or ""
    for column in (merged.get("columns") or {}).values():
        for key, value in _COLUMN_DEFAULTS.items():
            column.setdefault(key, value)
    return merged


def build_manifest(reader: InfoSchemaReader, json_manifest: "dict | None" = None) -> dict:
    known = _known_json_records(json_manifest)
    parents, children = _edges(reader)
    columns = _columns(reader)
    semantic_parts = _semantic_parts(reader)
    manifest: dict = {section: {} for section in _ALL_SECTIONS}

    jobs = [
        (section, kind, builder, row)
        for table, section, kind, builder in _COLLECTIONS
        for row in reader.table(table)
    ]
    jobs += [
        ("nodes", kind, _physical, row)
        for table, kind in _NODE_TABLES
        for row in reader.table(table)
    ]
    for section, kind, builder, row in jobs:
        record = builder(row, kind)
        unique_id = record["unique_id"]
        if section in _DEPENDENT_SECTIONS:
            record["depends_on"] = {"nodes": parents.get(unique_id)}
        if unique_id in columns:
            record["columns"] = columns[unique_id]
        record.update(semantic_parts.get(unique_id, {}) if section == "semantic_models" else {})
        manifest[section][unique_id] = _finish(record, section, known.get(unique_id))

    project = (reader.table("dbt.project") or [{}])[0]
    metadata = _fill(
        _compact(
            {
                "dbt_version": project.get("dbt_version"),
                "project_name": project.get("project_name"),
                "adapter_type": project.get("adapter_type"),
                "quoting": decode_json_column(project.get("quoting")),
            }
        ),
        (json_manifest or {}).get("metadata") or {},
    )
    metadata["dbt_schema_version"] = MANIFEST_SCHEMA
    metadata.setdefault("generated_at", _now())
    manifest["metadata"] = metadata

    ids = [uid for section in _DEPENDENT_SECTIONS for uid in manifest[section]]
    manifest["parent_map"] = _fill(
        {uid: parents.get(uid, []) for uid in ids}, (json_manifest or {}).get("parent_map")
    )
    manifest["child_map"] = _fill(
        {uid: children.get(uid, []) for uid in ids}, (json_manifest or {}).get("child_map")
    )
    group_map: dict[str, list[str]] = defaultdict(list)
    for uid, node in manifest["nodes"].items():
        if node.get("group"):
            group_map[node["group"]].append(uid)
    manifest["group_map"] = dict(group_map)
    manifest["selectors"] = (json_manifest or {}).get("selectors") or {}
    manifest["disabled"] = (json_manifest or {}).get("disabled") or {}
    return manifest


def _catalog_type(json_column: "dict | None", row: dict) -> "str | None":
    return (
        (json_column or {}).get("type")
        or row.get("data_type_actual")
        or row.get("data_type_declared")
        or row.get("data_type_inferred")
    )


def build_catalog(reader: InfoSchemaReader, json_catalog: "dict | None" = None) -> dict:
    json_catalog = json_catalog or {}
    json_records = {**(json_catalog.get("sources") or {}), **(json_catalog.get("nodes") or {})}
    manifest_rows = {
        row["unique_id"]: row
        for table in ("dbt.models", "dbt.seeds", "dbt.snapshots", "dbt.sources")
        for row in reader.table(table)
    }
    by_node = _group_by(reader.table("dbt.node_columns"), "node_unique_id")
    catalog: dict = {"nodes": {}, "sources": {}}
    for unique_id, rows in by_node.items():
        owner = manifest_rows.get(unique_id)
        if owner is None:
            continue
        json_record = json_records.get(unique_id) or {}
        json_columns = {str(k).lower(): v for k, v in (json_record.get("columns") or {}).items()}
        columns = {}
        for index, row in enumerate(sorted(rows, key=lambda r: r.get("column_index") or 0)):
            name = row["column_name"]
            columns[name] = _compact(
                {
                    "name": name,
                    "index": index,
                    "type": _catalog_type(json_columns.get(name.lower()), row),
                    "comment": None,
                }
            )
            columns[name].setdefault("type", "")
        record = {
            "unique_id": unique_id,
            "metadata": {
                "type": owner.get("materialized") or "table",
                "schema": owner.get("schema_name"),
                "name": owner.get("identifier") or owner.get("name"),
                "database": owner.get("database_name"),
            },
            "columns": columns,
            "stats": {},
        }
        section = "sources" if unique_id.startswith("source.") else "nodes"
        catalog[section][unique_id] = _fill(record, json_record)
    for section in ("nodes", "sources"):
        for unique_id, json_record in (json_catalog.get(section) or {}).items():
            catalog[section].setdefault(unique_id, json_record)
    project = (reader.table("dbt.project") or [{}])[0]
    catalog.update(
        metadata={
            "dbt_schema_version": CATALOG_SCHEMA,
            "dbt_version": project.get("dbt_version") or "",
            "generated_at": _now(),
            "env": {},
        },
        errors=None,
    )
    return catalog


def _run_result(row: dict, json_result: "dict | None") -> dict:
    result = _fill(
        _compact(
            {
                "unique_id": row["unique_id"],
                "status": row.get("status"),
                "timing": decode_json_column(row.get("timing")),
                "thread_id": row.get("thread_id"),
                "execution_time": row.get("execution_time"),
                "adapter_response": decode_json_column(row.get("adapter_response")),
                "message": row.get("message"),
                "failures": row.get("failures"),
                "compiled": row.get("compiled"),
                "relation_name": row.get("relation_name"),
            }
        ),
        json_result or {},
    )
    defaults = {
        "timing": [],
        "thread_id": "",
        "execution_time": 0.0,
        "adapter_response": {},
        "message": "",
        "failures": None,
        "compiled": False,
        "compiled_code": None,
        "relation_name": None,
    }
    for key, value in defaults.items():
        result.setdefault(key, value)
    return result


def _latest_invocation(reader: InfoSchemaReader, rows: "list[dict]") -> "dict | None":
    with_tests = {
        r["invocation_id"] for r in rows if r["unique_id"].split(".")[0] in ("test", "unit_test")
    }
    candidates = [i for i in reader.table("dbt_rt.invocations") if i["invocation_id"] in with_tests]
    if not candidates:
        return None
    return max(
        candidates, key=lambda i: i.get("generated_at") or datetime.min.replace(tzinfo=timezone.utc)
    )


def build_run_results(
    reader: InfoSchemaReader, json_run_results: "dict | None" = None
) -> "dict | None":
    rows = reader.table("dbt_rt.run_results")
    invocation = _latest_invocation(reader, rows)
    if invocation is None:
        return json_run_results
    json_by_id = {r.get("unique_id"): r for r in (json_run_results or {}).get("results") or []}
    results = [
        _run_result(row, json_by_id.get(row["unique_id"]))
        for row in rows
        if row["invocation_id"] == invocation["invocation_id"]
    ]
    return {
        "metadata": {
            "dbt_schema_version": RUN_RESULTS_SCHEMA,
            "dbt_version": invocation.get("dbt_version") or "",
            "generated_at": invocation["generated_at"].isoformat()
            if invocation.get("generated_at")
            else _now(),
            "invocation_id": invocation["invocation_id"],
            "env": {},
        },
        "results": results,
        "elapsed_time": invocation.get("elapsed_time") or 0.0,
        "args": {},
    }


def column_lineage(reader: InfoSchemaReader) -> dict:
    """``dbt.column_lineage`` value lineage as ``{"<node>.<column>": [{node, column}, ...]}``.

    Rows whose ``evolution`` is in ``_READ_ONLY_EVOLUTIONS`` (``scan``: a join, filter
    or grouping key that is read but does not feed the column's value) are dropped,
    so the result means what the sqlglot lineage means. Refs are deduplicated and
    sorted by ``(node, column)``.
    """
    refs: dict[str, set] = defaultdict(set)
    for row in reader.table("dbt.column_lineage"):
        if row.get("evolution") in _READ_ONLY_EVOLUTIONS:
            continue
        key = f"{row['child_node_unique_id']}.{row['child_column_name']}"
        refs[key].add((row["parent_node_unique_id"], row["parent_column_name"]))
    return {
        key: [{"node": node, "column": column} for node, column in sorted(pairs)]
        for key, pairs in refs.items()
    }
