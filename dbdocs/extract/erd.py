"""Structured ERD data via dbterd's ``json`` target.

dbterd's built-in targets emit diagram text; the SPA renders its ERD with React
Flow, which needs structured node/edge data. We register a ``json`` target
(:mod:`dbdocs.extract.erd_json`) and parse its ``{tables, relationships}`` output
into the SPA's ``{nodes, edges}`` — entities with columns (PK/FK flags) and
foreign-key edges between them, all keyed by dbt unique_id.
"""

import json

from dbterd.api import DbtErd

# Importing the module registers the "json" target with dbterd's PluginRegistry.
from dbdocs.extract import erd_json  # noqa: F401


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
    """Parse the json target into ``{"nodes": [...], "edges": [...]}``.

    Nodes are entities (with columns, ``is_primary_key``/``is_foreign_key`` flags
    and the resolved dbt unique_id); edges are foreign-key relationships between
    them. dbterd's relationships reference tables by *name*, so we map those back
    to unique_ids via each table's ``node_name``.
    """
    payload = json.loads(erd.get_erd())
    tables = payload.get("tables", [])
    relationships = payload.get("relationships", [])

    # table name (as dbterd refers to it in relationships) → dbt unique_id.
    name_to_id = {t["name"]: (t.get("node_name") or t["name"]) for t in tables}

    edges, fk_columns = _build_edges(relationships, name_to_id)
    nodes = [_build_node(t, fk_columns.get(t.get("node_name") or t["name"], set())) for t in tables]
    return {"nodes": nodes, "edges": edges}


def _build_edges(relationships: list, name_to_id: dict) -> "tuple[list, dict]":
    """Map relationships → edges and collect each node's FK column names."""
    edges = []
    fk_columns: dict = {}
    for index, rel in enumerate(relationships):
        parent_name, child_name = rel["table_map"]
        parent_cols, child_cols = rel["column_map"]
        source = name_to_id.get(parent_name, parent_name)
        target = name_to_id.get(child_name, child_name)
        # The child side holds the foreign key columns.
        fk_columns.setdefault(target, set()).update(child_cols)
        edges.append(
            {
                "id": rel.get("name") or f"e{index}",
                "source": source,
                "target": target,
                "from_columns": list(parent_cols),
                "to_columns": list(child_cols),
                "label": rel.get("relationship_label"),
                "type": rel.get("type", ""),
            }
        )
    return edges, fk_columns


def _build_node(table: dict, fk_cols: set) -> dict:
    node_id = table.get("node_name") or table["name"]
    return {
        "id": node_id,
        "label": table["name"],
        "database": table.get("database") or "",
        "schema": table.get("schema") or "",
        "resource_type": table.get("resource_type") or "model",
        "columns": [
            {
                "name": c["name"],
                "type": c.get("data_type") or "",
                "description": c.get("description") or "",
                "is_primary_key": bool(c.get("is_primary_key")),
                "is_foreign_key": c["name"] in fk_cols,
            }
            for c in table.get("columns", [])
        ],
    }
