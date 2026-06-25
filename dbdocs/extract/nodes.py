"""Extract the SPA's ``nodes`` and ``tree`` data from dbt artifacts.

``build_nodes`` flattens every resource type — models, sources, seeds, snapshots,
analyses, operations, metrics, semantic_models, saved_queries, unit_tests,
exposures — into a display record. ``build_tree`` groups only physical resources
(those with real database/schema coordinates) into the ``database → schema`` nav
tree. Typeless resources (metrics, semantic_models, saved_queries, unit_tests,
exposures) are first-class nodes in the ``nodes`` dict but are navigated via
resource-type sidebar tabs in the SPA — not slotted into the db tree. Pure
functions — no I/O, no dbterd calls beyond reading the already-parsed objects —
so they're trivially testable with lightweight fakes.

Macros are intentionally excluded: a real project typically has hundreds of
package-vendor macros that would flood the nav. Macros already surface inline
under the models that depend on them via ``macros_used``; they need no page.
"""

import re
from typing import Any

from dbdocs.core.artifacts import (
    CODE_ONLY_PREFIXES,
    COLLECTION_ATTRS,
    NODE_PREFIXES,
    db_schema,
    node_name,
)
from dbdocs.extract.tests_index import build_column_tests_index

#: unique_id prefixes for resources with real database/schema coordinates that
#: belong in the catalog nav tree.  Sources live in manifest.sources (not nodes)
#: but share the same naming convention.
_PHYSICAL_PREFIXES = NODE_PREFIXES + CODE_ONLY_PREFIXES + ("source.",)

#: Tuple of id prefixes for the collection attrs (for startswith checks).
_COLLECTION_PREFIXES = tuple(COLLECTION_ATTRS.keys())


def _column_entry(name: str, manifest_column: Any, col_type: str, tests: list) -> dict:
    """One column record. Newlines in the description become ``<br>`` for HTML."""
    description = getattr(manifest_column, "description", "") or "" if manifest_column else ""
    return {
        "name": name,
        "type": col_type or "",
        "tags": (getattr(manifest_column, "tags", []) or []) if manifest_column else [],
        "description": description.replace("\n", "<br>"),
        "tests": tests,
    }


def _columns(model: Any, catalog_node: Any, column_tests: dict) -> list:
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

    ``column_tests`` maps ``column_name_lower`` to a sorted list of test types
    defined on that column in the manifest (from ``build_column_tests_index``).
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
        columns.append(
            _column_entry(name, manifest_column, col_type or "", column_tests.get(lower, []))
        )

    for name, catalog_column in catalog_columns.items():
        if str(name).lower() in seen_lower:
            continue
        lower = str(name).lower()
        columns.append(
            _column_entry(
                name, None, getattr(catalog_column, "type", "") or "", column_tests.get(lower, [])
            )
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


def _catalog_stats(catalog_node: Any) -> dict:
    """Warehouse stats from the catalog node, restricted to ``include=True`` entries."""
    raw = getattr(catalog_node, "stats", {}) or {} if catalog_node else {}
    return {
        k: {"label": getattr(v, "label", k), "value": getattr(v, "value", None)}
        for k, v in raw.items()
        if getattr(v, "include", False)
    }


def _owner_string(entity: Any) -> str:
    """Resolve the node's owner to a display string (name or email), or empty."""
    owner = getattr(entity, "owner", None)
    if owner is None:
        return ""
    name = getattr(owner, "name", None) or ""
    email = getattr(owner, "email", None) or ""
    return name or email


def _node_record(
    unique_id: str,
    entity: Any,
    catalog_node: Any,
    resource_type: str,
    manifest: Any,
    tests_index: dict,
) -> dict:
    database, schema = db_schema(entity)
    config = getattr(entity, "config", None)
    contract = getattr(entity, "contract", None)
    column_tests = tests_index.get(unique_id, {})
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
        "columns": _columns(entity, catalog_node, column_tests),
        "language": getattr(entity, "language", "") or "",
        "raw_code": getattr(entity, "raw_code", "") or "",
        "compiled_code": getattr(entity, "compiled_code", "") or "",
        "macros": macros_used(manifest, entity),
        "materialization": getattr(config, "materialized", None) or "",
        "meta": getattr(entity, "meta", None) or getattr(config, "meta", None) or {},
        "access": getattr(entity, "access", None) or "",
        "group": getattr(entity, "group", None) or "",
        "contract_enforced": bool(getattr(contract, "enforced", False)),
        "version": getattr(entity, "version", None) or "",
        "latest_version": getattr(entity, "latest_version", None) or "",
        "owner": _owner_string(entity),
        "original_file_path": getattr(entity, "original_file_path", None) or "",
        "patch_path": getattr(entity, "patch_path", None) or "",
        "stats": _catalog_stats(catalog_node),
    }


def _base_envelope(unique_id: str, entity: Any, resource_type: str) -> dict:
    """Minimal fields common to every node record regardless of type."""
    return {
        "id": unique_id,
        "name": getattr(entity, "name", node_name(unique_id)),
        "label": node_name(unique_id),
        "resource_type": resource_type,
        "package": getattr(entity, "package_name", "") or "",
        "description": getattr(entity, "description", "") or "",
        "tags": list(getattr(entity, "tags", []) or []),
        "meta": getattr(entity, "meta", None) or {},
    }


def _enum_value(val: Any) -> Any:
    """Return the plain string value of a Pydantic enum, or the original value."""
    return val.value if hasattr(val, "value") else val


_ENTITY_REPR = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\(['\"](?P<name>[^'\"]+)['\"]\)$")


def _object_name(val: Any) -> str:
    """Return a plain display name for a metric/measure/entity reference.

    Handles three shapes seen across artifact_parser versions:
    - object with ``.name`` (``Measure``/``MetricInput``) → ``val.name``
    - literal string repr ``Entity('customer')`` / ``Dimension("foo")`` → ``customer``/``foo``
    - plain string already → as-is
    """
    name = getattr(val, "name", None)
    if name is not None:
        return str(name)
    text = str(val)
    match = _ENTITY_REPR.match(text)
    return match.group("name") if match else text


def _metric_record(unique_id: str, entity: Any) -> dict:
    """Node record for a metric (``manifest.metrics[id]``)."""
    type_params = getattr(entity, "type_params", None)
    record = _base_envelope(unique_id, entity, "metric")
    record["database"] = ""
    record["schema"] = ""
    record["group"] = getattr(entity, "group", None) or ""
    raw_type = getattr(entity, "type", None)
    record["metric"] = {
        "type": str(_enum_value(raw_type)) if raw_type is not None else "",
        "label": getattr(entity, "label", None) or "",
        "filter": str(getattr(entity, "filter", None) or ""),
        "type_params": _metric_type_params(type_params),
    }
    return record


def _metric_type_params(type_params: Any) -> dict:
    """Flatten ``type_params`` to a plain dict.

    Scalar-object fields (``measure``, ``numerator``, ``denominator``) carry a
    ``name`` attribute — extract it so the SPA can link to the owning semantic
    model.  List fields (``metrics``, ``input_measures``) may contain either
    ``MetricInput`` objects (also with ``.name``) or plain strings; both are
    normalised to plain names.
    """
    if type_params is None:
        return {}
    result: dict = {}
    for attr in ("measure", "numerator", "denominator"):
        val = getattr(type_params, attr, None)
        if val is not None:
            result[attr] = _object_name(val)
    for attr in ("expr", "window"):
        val = getattr(type_params, attr, None)
        if val is not None:
            result[attr] = str(val)
    for list_attr in ("metrics", "input_measures"):
        items = getattr(type_params, list_attr, None)
        if items:
            result[list_attr] = [_object_name(m) for m in items]
    return result


def _semantic_model_record(unique_id: str, entity: Any) -> dict:
    """Node record for a semantic model (``manifest.semantic_models[id]``)."""
    record = _base_envelope(unique_id, entity, "semantic_model")
    record["database"] = ""
    record["schema"] = ""
    record["semantic_model"] = {
        "model": getattr(entity, "model", None) or "",
        "entities": _sm_items(getattr(entity, "entities", []), ("name", "type")),
        "dimensions": _sm_items(getattr(entity, "dimensions", []), ("name", "type")),
        "measures": _sm_items(getattr(entity, "measures", []), ("name", "agg", "expr")),
    }
    return record


def _sm_items(collection: Any, attrs: tuple) -> list:
    """Convert a list of semantic-model component objects to plain dicts.

    Enum-valued fields (e.g. dimension ``type``, entity ``type``, measure
    ``agg``) are unwrapped via ``_enum_value`` so the SPA receives plain strings
    like ``"categorical"`` instead of ``"Type31.categorical"``.
    """
    if not collection:
        return []
    result = []
    for item in collection:
        row: dict = {}
        for attr in attrs:
            val = getattr(item, attr, None)
            if val is not None:
                row[attr] = str(_enum_value(val))
        result.append(row)
    return result


def _saved_query_record(unique_id: str, entity: Any) -> dict:
    """Node record for a saved query (``manifest.saved_queries[id]``)."""
    query_params = getattr(entity, "query_params", None)
    record = _base_envelope(unique_id, entity, "saved_query")
    record["database"] = ""
    record["schema"] = ""
    metrics = list(getattr(query_params, "metrics", []) or []) if query_params else []
    group_by = list(getattr(query_params, "group_by", []) or []) if query_params else []
    where = list(getattr(query_params, "where", []) or []) if query_params else []
    exports = getattr(entity, "exports", []) or []
    record["saved_query"] = {
        "metrics": [str(m) for m in metrics],
        "group_by": [_object_name(g) for g in group_by],
        "where": [_object_name(w) for w in where],
        "exports": [_export_item(e) for e in exports],
        "label": getattr(entity, "label", None) or "",
    }
    return record


def _export_item(export: Any) -> dict:
    """One export entry from a saved query.

    ``Config58`` uses ``schema_name`` for the target schema (not the dbterd
    ``schema_`` alias — that alias is on manifest nodes, not export configs).
    ``export_as`` is a Pydantic enum; ``.value`` gives the plain string.
    """
    config = getattr(export, "config", None)
    raw_export_as = getattr(config, "export_as", None)
    raw_schema = getattr(config, "schema_name", None) or getattr(config, "schema_", None) or ""
    return {
        "name": getattr(export, "name", None) or "",
        "schema": str(raw_schema) if raw_schema else "",
        "alias": getattr(config, "alias", None) or "",
        "export_as": str(_enum_value(raw_export_as)) if raw_export_as is not None else "",
    }


#: Max fixture rows emitted into the payload per unit-test given/expect block. A
#: csv-backed fixture can be large; the table is documentation, not a data dump,
#: so we keep the payload + DOM bounded and surface the full count via ``total``.
_FIXTURE_ROW_CAP = 50


def _fixture_rows(source: Any) -> dict:
    """Normalize a unit-test ``given``/``expect`` fixture to a renderable shape.

    ``dict``/``csv`` fixtures carry ``rows`` as a list of ``{column: value}``
    mappings — emit the ordered column union (first-seen order) plus the rows as
    stringified-value dicts so the SPA can render a data table, capped at
    :data:`_FIXTURE_ROW_CAP` with ``total`` recording the uncapped count. A
    ``sql`` fixture carries its query as the ``rows`` string instead — emit it as
    ``sql``.
    """
    raw_rows = getattr(source, "rows", None)
    if isinstance(raw_rows, str):
        return {"columns": [], "rows": [], "sql": raw_rows, "total": 0}
    all_rows = list(raw_rows or [])
    columns: list = []
    seen: set = set()
    rows: list = []
    for raw in all_rows[:_FIXTURE_ROW_CAP]:
        for key in raw:
            if key not in seen:
                seen.add(key)
                columns.append(str(key))
        rows.append({str(k): "" if v is None else str(v) for k, v in raw.items()})
    return {"columns": columns, "rows": rows, "sql": "", "total": len(all_rows)}


def _unit_test_given_item(g: Any, index: int) -> dict:
    """One given-input entry: ref name, format, and the (capped) fixture table."""
    inp = getattr(g, "input", None)
    fixture = _fixture_rows(g)
    return {
        "ref": inp if inp is not None else f"input {index}",
        "rows_count": fixture["total"],
        "format": getattr(g, "format", None) or "",
        "columns": fixture["columns"],
        "rows": fixture["rows"],
        "sql": fixture["sql"],
    }


_EMPTY_FIXTURE = {"columns": [], "rows": [], "sql": "", "total": 0}


def _unit_test_record(unique_id: str, entity: Any) -> dict:
    """Node record for a unit test definition (``manifest.unit_tests[id]``)."""
    record = _base_envelope(unique_id, entity, "unit_test")
    record["database"] = ""
    record["schema"] = ""
    given = getattr(entity, "given", []) or []
    expect = getattr(entity, "expect", None)
    expect_fixture = _fixture_rows(expect) if expect else _EMPTY_FIXTURE
    record["unit_test"] = {
        "model": getattr(entity, "model", None) or "",
        "given_count": len(given),
        "given": [_unit_test_given_item(g, i) for i, g in enumerate(given)],
        "expect_rows": expect_fixture["total"],
        "expect_format": getattr(expect, "format", None) or "" if expect else "",
        "expect_columns": expect_fixture["columns"],
        "expect_data": expect_fixture["rows"],
        "expect_sql": expect_fixture["sql"],
        "given_summary": [
            inp if (inp := getattr(g, "input", None)) is not None else f"input {i}"
            for i, g in enumerate(given)
        ],
    }
    return record


def _exposure_record(unique_id: str, entity: Any) -> dict:
    """Node record for an exposure (``manifest.exposures[id]``)."""
    owner = getattr(entity, "owner", None)
    record = _base_envelope(unique_id, entity, "exposure")
    record["database"] = ""
    record["schema"] = ""
    raw_type = getattr(entity, "type", None)
    raw_maturity = getattr(entity, "maturity", None)
    record["exposure"] = {
        "type": str(_enum_value(raw_type)) if raw_type is not None else "",
        "label": getattr(entity, "label", None) or "",
        "maturity": str(_enum_value(raw_maturity)) if raw_maturity is not None else "",
        "url": getattr(entity, "url", None) or "",
        "owner_name": getattr(owner, "name", None) or "" if owner else "",
        "owner_email": getattr(owner, "email", None) or "" if owner else "",
    }
    return record


def build_nodes(manifest: Any, catalog: Any) -> dict:
    """Return the ``nodes`` dict keyed by unique_id.

    Covers every navigable resource type:

    - Physical (database + schema from manifest): models, seeds, snapshots,
      sources, analyses, operations.  These appear in the Catalog sidebar tab
      and the ``database → schema`` nav tree.
    - Typeless (no real database/schema): metrics, semantic_models, saved_queries,
      unit_tests, exposures.  These carry ``database=""`` / ``schema=""`` and are
      navigated via per-resource-type sidebar tabs — they do not appear in
      ``build_tree``'s output.

    Macros are excluded — they surface inline under the models that depend on
    them; adding hundreds of package macros to the nav would obscure project nodes.
    """
    catalog_nodes = getattr(catalog, "nodes", {}) or {}
    catalog_sources = getattr(catalog, "sources", {}) or {}
    tests_index = build_column_tests_index(manifest)
    nodes: dict = {}

    for unique_id, entity in (getattr(manifest, "nodes", {}) or {}).items():
        if str(unique_id).startswith(NODE_PREFIXES):
            resource_type = str(unique_id).split(".")[0]
            nodes[unique_id] = _node_record(
                unique_id,
                entity,
                catalog_nodes.get(unique_id),
                resource_type,
                manifest,
                tests_index,
            )
        elif str(unique_id).startswith(CODE_ONLY_PREFIXES):
            resource_type = str(unique_id).split(".")[0]
            nodes[unique_id] = _node_record(
                unique_id, entity, None, resource_type, manifest, tests_index
            )

    for unique_id, entity in (getattr(manifest, "sources", {}) or {}).items():
        nodes[unique_id] = _node_record(
            unique_id, entity, catalog_sources.get(unique_id), "source", manifest, tests_index
        )

    for unique_id, entity in (getattr(manifest, "metrics", {}) or {}).items():
        nodes[unique_id] = _metric_record(unique_id, entity)

    for unique_id, entity in (getattr(manifest, "semantic_models", {}) or {}).items():
        nodes[unique_id] = _semantic_model_record(unique_id, entity)

    for unique_id, entity in (getattr(manifest, "saved_queries", {}) or {}).items():
        nodes[unique_id] = _saved_query_record(unique_id, entity)

    for unique_id, entity in (getattr(manifest, "unit_tests", {}) or {}).items():
        nodes[unique_id] = _unit_test_record(unique_id, entity)

    for unique_id, entity in (getattr(manifest, "exposures", {}) or {}).items():
        nodes[unique_id] = _exposure_record(unique_id, entity)

    return nodes


def build_tree(nodes: dict) -> dict:
    """Group physical node ids into an ordered ``{database: {schema: [ids]}}`` nav tree.

    Only nodes whose unique_id starts with a physical prefix
    (model/seed/snapshot/source/analysis/operation) are included.  Typeless
    resources (metrics, semantic_models, saved_queries, unit_tests, exposures)
    carry empty ``database``/``schema`` and are navigated via per-type sidebar
    tabs in the SPA — they are excluded here.
    """
    by_database: dict = {}
    for unique_id, record in nodes.items():
        if not str(unique_id).startswith(_PHYSICAL_PREFIXES):
            continue
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
