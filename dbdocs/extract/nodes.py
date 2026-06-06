"""Extract the SPA's ``nodes`` and ``tree`` data from dbt artifacts.

``build_nodes`` flattens every model/source/seed/snapshot into a display record
(columns merged from manifest descriptions + catalog types, transformation code,
resolved macros). ``build_tree`` groups those into the ``database → schema``
navigation tree. Pure functions — no I/O, no dbterd calls beyond reading the
already-parsed objects — so they're trivially testable with lightweight fakes.
"""

from typing import Any

from dbdocs.core.artifacts import NODE_PREFIXES, db_schema, node_name


def _columns(model: Any, catalog_node: Any) -> list:
    """Merge manifest column metadata (description/tags) with catalog types.

    Iterates the catalog's columns (the warehouse truth for which columns exist
    and their types) and layers on the manifest description/tags when present.
    Newlines in descriptions become ``<br>`` so they survive HTML rendering.
    """
    manifest_columns = getattr(model, "columns", {}) or {}
    catalog_columns = getattr(catalog_node, "columns", {}) or {} if catalog_node else {}
    columns = []
    for name in catalog_columns:
        manifest_column = manifest_columns.get(name)
        description = getattr(manifest_column, "description", "") or "" if manifest_column else ""
        columns.append(
            {
                "name": name,
                "type": catalog_columns[name].type,
                "tags": (getattr(manifest_column, "tags", []) or []) if manifest_column else [],
                "description": description.replace("\n", "<br>"),
            }
        )
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
