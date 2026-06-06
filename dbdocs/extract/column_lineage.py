"""Column-level lineage: trace each model column back to its source columns.

For every model we parse its **compiled** SQL with sqlglot, qualify it against a
schema built from the dbt catalog (so ``SELECT *`` and unqualified columns
resolve), then walk each output column's lineage tree to its leaf table columns
and map those tables back to dbt unique_ids. The heavy lifting lives in the
vendored :mod:`dbdocs.extract._sqlglot_lineage` (a self-contained lineage
builder over sqlglot's optimizer).

Design: **fail-soft per model.** A single model with SQL sqlglot can't parse
must never sink the whole ``generate`` — it's caught, logged, and skipped, and
the run reports how many were skipped.
"""

from typing import Any

from sqlglot import exp
from sqlglot.errors import SqlglotError

from dbdocs.core.artifacts import db_schema, node_name
from dbdocs.core.exceptions import LineageError
from dbdocs.core.log import logger
from dbdocs.extract._sqlglot_lineage import Node, lineage

#: dbt adapter_type → sqlglot dialect, when the names differ. Most match 1:1.
_DIALECT_ALIASES = {
    "databricks": "spark",
}


def _to_dialect(adapter_type: "str | None") -> "str | None":
    if not adapter_type:
        return None
    return _DIALECT_ALIASES.get(adapter_type, adapter_type)


class ColumnLineageExtractor:
    """Build the ``columnLineage`` map for a dbt project's models.

    The output maps a fully-qualified output column to the upstream columns it is
    derived from::

        {"model.shop.customers.customer_id": [{"node": "model.shop.stg_customers",
                                               "column": "customer_id"}, ...]}
    """

    def __init__(self, manifest: Any, catalog: Any, dialect: "str | None" = None) -> None:
        self.manifest = manifest
        self.catalog = catalog
        self.dialect = _to_dialect(dialect)
        self.schema = self._schema_from_catalog()
        # Map a lower-cased ``db.schema.table`` relation back to its unique_id.
        self._relation_to_node = self._relation_index()
        self.skipped = 0

    def extract(self) -> dict:
        """Return the ``columnLineage`` map across all models (fail-soft)."""
        result: dict = {}
        for unique_id, model in (getattr(self.manifest, "nodes", {}) or {}).items():
            if not str(unique_id).startswith("model."):
                continue
            compiled = getattr(model, "compiled_code", "") or ""
            if not compiled.strip():
                continue
            try:
                self._extract_model(unique_id, compiled, result)
            except (SqlglotError, LineageError, KeyError, ValueError, RecursionError) as exc:
                self.skipped += 1
                logger.warning("Column lineage skipped for %s: %s", node_name(unique_id), exc)
        if self.skipped:
            logger.info("Column lineage: skipped %s model(s) that failed to parse.", self.skipped)
        return result

    def _extract_model(self, unique_id: str, compiled: str, result: dict) -> None:
        node = self.manifest.nodes[unique_id]
        output_columns = [c for c in (getattr(node, "columns", {}) or {})]
        # Fall back to the catalog's column list when the manifest has none.
        if not output_columns:
            catalog_node = (getattr(self.catalog, "nodes", {}) or {}).get(unique_id)
            output_columns = (
                list(getattr(catalog_node, "columns", {}) or {}) if catalog_node else []
            )
        for column in output_columns:
            try:
                root = lineage(column, compiled, schema=self.schema, dialect=self.dialect)
            except SqlglotError:
                # One unresolvable column shouldn't drop the rest of the model.
                continue
            upstream = self._leaf_columns(root)
            if upstream:
                result[f"{unique_id}.{column}"] = upstream

    def _leaf_columns(self, root: Node) -> list:
        """Collect distinct upstream ``{node, column}`` leaves of a lineage tree.

        A leaf is a node whose source is a real ``Table`` (not a CTE/subquery
        scope) that we can map back to a dbt node. The root itself is skipped.
        """
        seen = set()
        upstream = []
        for node in root.walk():
            if node is root:
                continue
            source = node.source
            if not isinstance(source, exp.Table):
                continue
            mapped = self._map_table(source)
            if mapped is None:
                continue
            column = node_name(node.name)
            key = (mapped, column)
            if key in seen:
                continue
            seen.add(key)
            upstream.append({"node": mapped, "column": column})
        return upstream

    def _map_table(self, table: exp.Table) -> "str | None":
        catalog = table.catalog
        db = table.db
        name = table.name
        candidates = [
            f"{catalog}.{db}.{name}",
            f"{db}.{name}",
            name,
        ]
        for candidate in candidates:
            mapped = self._relation_to_node.get(candidate.lower().strip("."))
            if mapped:
                return mapped
        return None

    def _relation_index(self) -> dict:
        """Map ``db.schema.table`` (and shorter forms) → dbt unique_id."""
        index: dict = {}
        for unique_id, entity in self._all_entities():
            database, schema = db_schema(entity)
            table = getattr(entity, "alias", None) or getattr(entity, "name", None)
            if not table:
                continue
            full = f"{database}.{schema}.{table}".lower()
            index[full] = unique_id
            index.setdefault(f"{schema}.{table}".lower(), unique_id)
            index.setdefault(str(table).lower(), unique_id)
            relation = getattr(entity, "relation_name", None)
            if relation:
                index.setdefault(str(relation).replace('"', "").lower(), unique_id)
        return index

    def _schema_from_catalog(self) -> dict:
        """Build sqlglot's nested ``{db: {schema: {table: {col: type}}}}`` schema."""
        schema: dict = {}
        for _, entity, columns in self._catalog_entities():
            database, db_schema_name = db_schema(entity)
            table = getattr(entity, "alias", None) or getattr(entity, "name", None)
            if not table:
                continue
            col_types = {name: (col.type or "UNKNOWN") for name, col in columns.items()}
            schema.setdefault(database, {}).setdefault(db_schema_name, {})[table] = col_types
        return schema

    def _all_entities(self):
        yield from (getattr(self.manifest, "nodes", {}) or {}).items()
        yield from (getattr(self.manifest, "sources", {}) or {}).items()

    def _catalog_entities(self):
        """Yield ``(unique_id, manifest_entity, catalog_columns)`` for schema build.

        Pairs the catalog's column list (types) with the manifest entity (the
        authoritative database/schema, read via ``schema_``).
        """
        manifest_nodes = getattr(self.manifest, "nodes", {}) or {}
        manifest_sources = getattr(self.manifest, "sources", {}) or {}
        for unique_id, catalog_node in (getattr(self.catalog, "nodes", {}) or {}).items():
            entity = manifest_nodes.get(unique_id)
            if entity is not None:
                yield unique_id, entity, getattr(catalog_node, "columns", {}) or {}
        for unique_id, catalog_source in (getattr(self.catalog, "sources", {}) or {}).items():
            entity = manifest_sources.get(unique_id)
            if entity is not None:
                yield unique_id, entity, getattr(catalog_source, "columns", {}) or {}
