"""A dbterd ``json`` target adapter: structured tables + relationships.

dbterd's built-in targets emit diagram *text* (Mermaid, DBML, …). The dbdocs SPA
renders its ERD with React Flow, which needs structured node/edge data, not a
diagram string. Registering this adapter makes ``DbtErd(target="json").get_erd()``
return a JSON document of ``{tables, relationships}`` that ``erd.build_erd_data``
turns into the SPA's ``{nodes, edges}``.

The ``Table``/``Column``/``Ref`` → dict serializers are pure and tested in
isolation; the adapter is the thin dbterd-contract shell over them.
"""

import json
from typing import Any

from dbterd.core.adapters.target import BaseTargetAdapter
from dbterd.core.models import Column, Ref, Table
from dbterd.core.registry.decorators import register_target


def column_to_dict(column: Column) -> dict:
    """A dbterd ``Column`` as a plain dict (name, type, description, PK flag)."""
    return {
        "name": column.name,
        "data_type": column.data_type,
        "description": column.description,
        "is_primary_key": bool(getattr(column, "is_primary_key", False)),
    }


def table_to_dict(table: Table) -> dict:
    """A dbterd ``Table`` as a plain dict, keyed for ERD rendering."""
    return {
        "name": table.name,
        "database": table.database,
        "schema": table.schema,
        "resource_type": table.resource_type,
        "node_name": table.node_name,
        "raw_sql": table.raw_sql,
        "description": table.description,
        "label": table.label,
        "columns": [column_to_dict(c) for c in (table.columns or [])],
    }


def relationship_to_dict(ref: Ref) -> dict:
    """A dbterd ``Ref`` as a plain dict: endpoints + the joined columns."""
    parent, child = ref.table_map
    parent_cols, child_cols = ref.column_map
    return {
        "name": ref.name,
        "type": ref.type,
        "table_map": [parent, child],
        "column_map": [list(parent_cols), list(child_cols)],
        "relationship_label": getattr(ref, "relationship_label", None),
    }


@register_target("json", description="Structured JSON of tables and relationships")
class JsonAdapter(BaseTargetAdapter):
    """Emit dbterd tables + relationships as one structured JSON document."""

    file_extension = ".json"
    default_filename = "output.json"

    def build_erd(self, tables: list, relationships: list, **kwargs: Any) -> str:
        payload = {
            "tables": [table_to_dict(t) for t in tables],
            "relationships": [relationship_to_dict(r) for r in relationships],
        }
        return json.dumps(payload)

    def format_table(self, table: Table, **kwargs: Any) -> str:
        return json.dumps(table_to_dict(table))

    def format_relationship(self, relationship: Ref, **kwargs: Any) -> str:
        return json.dumps(relationship_to_dict(relationship))

    def get_rel_symbol(self, relationship_type: str) -> str:
        return ""
