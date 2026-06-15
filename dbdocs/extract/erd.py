"""Structured ERD data via dbterd's official ``json`` target.

dbterd 1.28.0 ships a built-in, schema-validated ``json`` target that emits
``{nodes, edges, metadata}``. Each node carries ``id`` (the dbt unique_id),
``name``, ``schema_name``, ``database``, ``resource_type``, and ``columns``
(with ``data_type``, ``is_primary_key``, ``is_foreign_key``). Each edge carries
``id``, ``from_id`` (FK/child side), ``to_id`` (referenced/parent side),
``from_columns``, ``to_columns``, ``label``, and ``cardinality``.

``build_erd_data`` maps that shape into the SPA's ``{nodes, edges}`` — the
React Flow bundle reads ``nodes`` (entities + column flags) and ``edges``
(FK relationships, ``source``/``target`` keyed by dbt unique_id).
"""

import json

from dbterd.api import DbtErd, default


def erd_algo(dbterd_options: "dict | None" = None) -> str:
    """The dbterd algorithm that detected the ERD relationships.

    Reads the configured ``algo`` from the ``dbterd:`` block, falling back to
    dbterd's own default. Surfaced into the SPA so it can explain an empty ERD.
    """
    return (dbterd_options or {}).get("algo") or default.default_algo()


def build_erd(dbterd_options: "dict | None" = None, artifacts_dir: "str | None" = None) -> DbtErd:
    """Build the ERD generator (json target) from dbdocs' ``dbterd`` options.

    ``dbterd_options`` is the ``dbterd:`` block of ``dbdocs.yml`` (``algo``,
    ``entity_name_format``, ``resource_type``, ``select``, …) passed straight to
    ``DbtErd``. We force ``target="json"`` — the SPA needs structured data — but
    let everything else come from the project's config so the ERD matches what
    the team configured. (Config lives in ``dbdocs.yml``, not a separate
    ``.dbterd.yml``.)

    ``artifacts_dir`` is the dbt target dir (``config.target_dir``). dbterd reads
    the manifest/catalog directly from this dir; without it dbterd would default
    to ``./target`` and ignore the configured ``target_dir``. An explicit
    ``artifacts_dir`` in ``dbterd_options`` still wins.
    """
    dbterd_kwargs = {k: v for k, v in (dbterd_options or {}).items() if k != "target"}
    if artifacts_dir is not None:
        dbterd_kwargs.setdefault("artifacts_dir", artifacts_dir)
    return DbtErd(target="json", **dbterd_kwargs)


def build_erd_data(erd: DbtErd) -> dict:
    """Parse dbterd's official ``{nodes, edges}`` payload into the SPA shape.

    dbterd's ``json`` target emits nodes keyed by dbt unique_id (``id`` field).
    When ``entity_name_format`` is configured, dbterd emits edge ``from_id`` /
    ``to_id`` as the formatted entity name (e.g. ``orders``) rather than the
    full unique_id (e.g. ``model.jaffle_shop.orders``). A ``name_to_id`` map
    resolves those short names back to the node id before building edges, so the
    SPA's ``source``/``target`` always reference a valid node ``id``.

    Some dbterd algos (e.g. ``model_contract``) do not set ``is_foreign_key``
    on node columns even when those columns appear in FK edges. After building
    edges, any column named in an edge's ``from_columns`` (the FK/child side)
    has its ``is_foreign_key`` flag back-filled to ``True`` on the target node.

    SPA edge direction: ``source`` is the referenced (parent) side, ``target``
    is the FK (child) side — matching dbterd's ``to_id`` and ``from_id``
    respectively.
    """
    payload = json.loads(erd.get_erd())
    raw_nodes = payload.get("nodes", [])
    raw_edges = payload.get("edges", [])
    nodes = [_build_node(n) for n in raw_nodes]
    node_ids = {n["id"] for n in nodes}
    # Count occurrences first; ambiguous names (more than one node) are excluded
    # so a collision can't silently resolve to the wrong node.
    name_counts: dict[str, int] = {}
    for n in raw_nodes:
        nm = n.get("name")
        if nm:
            name_counts[nm] = name_counts.get(nm, 0) + 1
    name_to_id = {
        n.get("name"): n["id"]
        for n in raw_nodes
        if n.get("name") and name_counts[n.get("name")] == 1
    }
    edges = [_build_edge(e, i, node_ids, name_to_id) for i, e in enumerate(raw_edges)]
    _backfill_fk_flags(nodes, edges)
    return {"nodes": nodes, "edges": edges}


def _backfill_fk_flags(nodes: "list[dict]", edges: "list[dict]") -> None:
    """Set is_foreign_key=True on columns named in each edge's from_columns.

    Keyed by node id so the lookup is O(1) per column per edge.
    """
    nodes_by_id = {n["id"]: n for n in nodes}
    for edge in edges:
        target_node = nodes_by_id.get(edge["target"])
        if target_node is None:
            continue
        fk_cols = {c.lower() for c in edge.get("from_columns", [])}
        if not fk_cols:
            continue
        for col in target_node["columns"]:
            if col["name"].lower() in fk_cols:
                col["is_foreign_key"] = True


def _build_node(node: dict) -> dict:
    return {
        "id": node["id"],
        "label": node.get("name") or "",
        "database": node.get("database") or "",
        "schema": node.get("schema_name") or "",
        "resource_type": node.get("resource_type") or "model",
        "columns": [
            {
                "name": c["name"],
                "type": c.get("data_type") or "",
                "description": c.get("description") or "",
                "is_primary_key": bool(c.get("is_primary_key")),
                "is_foreign_key": bool(c.get("is_foreign_key")),
            }
            for c in node.get("columns", [])
        ],
    }


def _resolve_edge_id(raw: str, node_ids: "set[str]", name_to_id: "dict[str, str]") -> str:
    # If raw is already a valid node id, keep it (the no-entity_name_format case).
    # Otherwise resolve through the name→id map built from node labels.
    if raw in node_ids:
        return raw
    return name_to_id.get(raw, raw)


def _build_edge(edge: dict, index: int, node_ids: "set[str]", name_to_id: "dict[str, str]") -> dict:
    # from_id is the FK/child side; to_id is the referenced/parent side.
    # SPA convention: source = parent (to_id), target = child (from_id).
    raw_from = edge.get("from_id") or ""
    raw_to = edge.get("to_id") or ""
    return {
        "id": edge.get("id") or f"e{index}",
        "source": _resolve_edge_id(raw_to, node_ids, name_to_id),
        "target": _resolve_edge_id(raw_from, node_ids, name_to_id),
        "from_columns": edge.get("from_columns") or [],
        "to_columns": edge.get("to_columns") or [],
        "label": edge.get("label") or "",
        "type": edge.get("cardinality") or "",
    }
