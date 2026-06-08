"""Extract the SPA's ``nodes`` and ``tree`` data from dbt artifacts.

``build_nodes`` flattens every model/source/seed/snapshot into a display record
(columns merged from manifest descriptions + catalog types, transformation code,
resolved macros). ``build_tree`` groups those into the ``database → schema``
navigation tree. Pure functions — no I/O, no dbterd calls beyond reading the
already-parsed objects — so they're trivially testable with lightweight fakes.
"""

from typing import Any

from dbdocs.core.artifacts import NODE_PREFIXES, db_schema, node_name


def _column_entry(name: str, manifest_column: Any, col_type: str) -> dict:
    """One column record. Newlines in the description become ``<br>`` for HTML."""
    description = getattr(manifest_column, "description", "") or "" if manifest_column else ""
    return {
        "name": name,
        "type": col_type or "",
        "tags": (getattr(manifest_column, "tags", []) or []) if manifest_column else [],
        "description": description.replace("\n", "<br>"),
    }


def _columns(model: Any, catalog_node: Any) -> list:
    """Build a node's columns: the manifest is the source of truth, the catalog
    enriches it.

    The **manifest** decides which columns are documented and carries their
    metadata (description, tags, ``data_type``); the **catalog** *enriches* — it
    supplies the warehouse-confirmed type and any columns the manifest didn't
    document. It never replaces the manifest, so a model absent from a
    stale/partial ``catalog.json`` still shows every documented column.

    Manifest columns come first, in manifest order, each with its type enriched
    from the catalog when present (falling back to the manifest ``data_type``).
    The catalog keys columns by the warehouse's casing (Snowflake upper-cases
    them) while the manifest keeps the modeled casing, so the catalog type lookup
    is case-insensitive. Catalog-only columns are appended afterwards.
    """
    manifest_columns = getattr(model, "columns", {}) or {}
    catalog_columns = getattr(catalog_node, "columns", {}) or {} if catalog_node else {}
    catalog_by_lower = {str(name).lower(): col for name, col in catalog_columns.items()}

    columns = []
    seen_lower = set()
    for name, manifest_column in manifest_columns.items():
        lower = str(name).lower()
        seen_lower.add(lower)
        catalog_column = catalog_by_lower.get(lower)
        col_type = getattr(catalog_column, "type", None) or getattr(
            manifest_column, "data_type", None
        )
        columns.append(_column_entry(name, manifest_column, col_type or ""))

    for name, catalog_column in catalog_columns.items():
        if str(name).lower() in seen_lower:
            continue
        columns.append(_column_entry(name, None, getattr(catalog_column, "type", "") or ""))
    return columns


def macros_used(manifest: Any, node: Any) -> list:
    """The macros a node depends on, resolved to ``{name, package, sql}`` dicts.

    ``depends_on.macros`` holds macro unique_ids; each is looked up in
    ``manifest.macros``. Project macros come first (what a reader most wants),
    then everything else, each group name-sorted.
    """
    macros = getattr(manifest, "macros", {}) or {}
    depends_on = getattr(node, "depends_on", None)
    macro_ids = list(getattr(depends_on, "macros", []) or [])
    resolved = []
    for macro_id in macro_ids:
        macro = macros.get(macro_id)
        if macro is None:
            continue
        resolved.append(
            {
                "name": getattr(macro, "name", node_name(macro_id)),
                "package": getattr(macro, "package_name", "") or "",
                "sql": getattr(macro, "macro_sql", "") or "",
            }
        )
    project_pkg = getattr(node, "package_name", "") or ""
    resolved.sort(key=lambda m: (m["package"] != project_pkg, m["package"], m["name"]))
    return resolved


def _node_record(unique_id: str, entity: Any, catalog_node: Any, resource_type: str, manifest: Any):
    database, schema = db_schema(entity)
    return {
        "id": unique_id,
        "name": getattr(entity, "name", node_name(unique_id)),
        "label": node_name(unique_id),
        "resource_type": resource_type,
        "database": database,
        "schema": schema,
        "package": getattr(entity, "package_name", "") or "",
        "description": getattr(entity, "description", "") or "",
        "tags": list(getattr(entity, "tags", []) or []),
        "relation_name": getattr(entity, "relation_name", "") or "",
        "columns": _columns(entity, catalog_node),
        "language": getattr(entity, "language", "") or "",
        "raw_code": getattr(entity, "raw_code", "") or "",
        "compiled_code": getattr(entity, "compiled_code", "") or "",
        "macros": macros_used(manifest, entity),
    }


def build_nodes(manifest: Any, catalog: Any) -> dict:
    """Return the ``nodes`` dict keyed by unique_id (models + sources)."""
    catalog_nodes = getattr(catalog, "nodes", {}) or {}
    catalog_sources = getattr(catalog, "sources", {}) or {}
    nodes: dict = {}
    for unique_id, entity in (getattr(manifest, "nodes", {}) or {}).items():
        if not str(unique_id).startswith(NODE_PREFIXES):
            continue
        resource_type = str(unique_id).split(".")[0]
        nodes[unique_id] = _node_record(
            unique_id, entity, catalog_nodes.get(unique_id), resource_type, manifest
        )
    for unique_id, entity in (getattr(manifest, "sources", {}) or {}).items():
        nodes[unique_id] = _node_record(
            unique_id, entity, catalog_sources.get(unique_id), "source", manifest
        )
    return nodes


def build_tree(nodes: dict) -> dict:
    """Group node ids into an ordered ``{database: {schema: [ids]}}`` nav tree."""
    by_database: dict = {}
    for unique_id, record in nodes.items():
        database = record["database"]
        schema = record["schema"]
        by_database.setdefault(database, {}).setdefault(schema, []).append(unique_id)
    return {
        database: {
            schema: sorted(by_database[database][schema], key=lambda i: nodes[i]["label"])
            for schema in sorted(by_database[database])
        }
        for database in sorted(by_database)
    }
