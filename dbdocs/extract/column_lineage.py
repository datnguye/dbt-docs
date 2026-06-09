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

from concurrent.futures import ProcessPoolExecutor
from typing import Any

from sqlglot import exp
from sqlglot.errors import SqlglotError

from dbdocs.core.artifacts import db_schema, node_name
from dbdocs.core.exceptions import LineageError
from dbdocs.core.log import logger
from dbdocs.extract._sqlglot_lineage import Node, lineage, prepare_scope

#: dbt adapter_type → sqlglot dialect, when the names differ. Most match 1:1.
_DIALECT_ALIASES = {
    "databricks": "spark",
}

#: Parse + qualify is CPU-bound and embarrassingly parallel across models. Below
#: this model count the ProcessPoolExecutor's spawn + pickle overhead outweighs
#: the win, so we stay serial; at or above it we fan out across cores.
_PARALLEL_THRESHOLD = 500

#: Errors a single model's lineage may raise that must not sink the whole run.
_MODEL_ERRORS = (SqlglotError, LineageError, KeyError, ValueError, RecursionError)


def _to_dialect(adapter_type: "str | None") -> "str | None":
    if not adapter_type:
        return None
    return _DIALECT_ALIASES.get(adapter_type, adapter_type)


def _map_table(table: exp.Table, relation_to_node: dict) -> "str | None":
    """Map a sqlglot ``Table`` to a dbt unique_id via the relation index."""
    candidates = [
        f"{table.catalog}.{table.db}.{table.name}",
        f"{table.db}.{table.name}",
        table.name,
    ]
    for candidate in candidates:
        mapped = relation_to_node.get(candidate.lower().strip("."))
        if mapped:
            return mapped
    return None


def _leaf_columns(root: Node, relation_to_node: dict) -> list:
    """Collect distinct upstream ``{node, column}`` leaves of a lineage tree.

    A leaf is a node whose source is a real ``Table`` (not a CTE/subquery scope)
    that maps back to a dbt node. The root itself is skipped.
    """
    seen = set()
    upstream = []
    for node in root.walk():
        if node is root:
            continue
        source = node.source
        if not isinstance(source, exp.Table):
            continue
        mapped = _map_table(source, relation_to_node)
        if mapped is None:
            continue
        column = node_name(node.name)
        key = (mapped, column)
        if key in seen:
            continue
        seen.add(key)
        upstream.append({"node": mapped, "column": column})
    return upstream


def _extract_model_columns(
    unique_id: str,
    compiled: str,
    output_columns: list,
    schema: dict,
    dialect: "str | None",
    relation_to_node: dict,
) -> dict:
    """Trace every output column of one model to its upstream columns.

    Pure and picklable (plain str/list/dict args, no manifest/catalog objects) so
    it runs unchanged in the serial loop or a ``ProcessPoolExecutor`` worker.
    Builds the scope once per model — qualify is the expensive part and is
    identical for every column — then traces each column against it.
    """
    out: dict = {}
    scope = prepare_scope(compiled, schema=schema, dialect=dialect)
    for column in output_columns:
        try:
            root = lineage(column, compiled, dialect=dialect, scope=scope)
        except SqlglotError:
            # One unresolvable column shouldn't drop the rest of the model.
            continue
        upstream = _leaf_columns(root, relation_to_node)
        if upstream:
            out[f"{unique_id}.{column}"] = upstream
    return out


def _extract_model_task(work: tuple) -> tuple:
    """Worker wrapper: returns ``(unique_id, columns_map, error_str_or_None)``.

    Catching here (rather than letting the exception cross the process boundary)
    keeps the fail-soft contract: one unparseable model is reported and skipped,
    never sinking the pool.
    """
    unique_id, compiled, output_columns, schema, dialect, relation_to_node = work
    try:
        return (
            unique_id,
            _extract_model_columns(
                unique_id, compiled, output_columns, schema, dialect, relation_to_node
            ),
            None,
        )
    except _MODEL_ERRORS as exc:
        return unique_id, {}, str(exc)


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
        """Return the ``columnLineage`` map across all models (fail-soft).

        Runs serially for small projects; fans the per-model sqlglot work across
        processes once a project has ``_PARALLEL_THRESHOLD`` models or more, where
        the CPU-bound parse/qualify dominates the pool's spawn cost.
        """
        work = self._work_items()
        if not work:
            return {}
        if len(work) >= _PARALLEL_THRESHOLD:
            results = self._extract_parallel(work)
        else:
            results = (_extract_model_task(item) for item in work)

        result: dict = {}
        for unique_id, columns, error in results:
            if error is not None:
                self.skipped += 1
                logger.warning("Column lineage skipped for %s: %s", node_name(unique_id), error)
                continue
            result.update(columns)
        if self.skipped:
            logger.info("Column lineage: skipped %s model(s) that failed to parse.", self.skipped)
        return result

    def _extract_parallel(self, work: list) -> list:
        """Run the per-model tasks across a process pool, returning their results."""
        with ProcessPoolExecutor() as pool:
            return list(pool.map(_extract_model_task, work))

    def _work_items(self) -> list:
        """Build the picklable per-model work tuples for the (serial or pool) run.

        Each item is ``(unique_id, compiled, output_columns, schema, dialect,
        relation_to_node)`` — all plain str/list/dict, so it crosses a process
        boundary cleanly (the Pydantic manifest/catalog never do).
        """
        work = []
        for unique_id, model in (getattr(self.manifest, "nodes", {}) or {}).items():
            if not str(unique_id).startswith("model."):
                continue
            compiled = getattr(model, "compiled_code", "") or ""
            if not compiled.strip():
                continue
            output_columns = self._output_columns(unique_id, model)
            if not output_columns:
                continue
            work.append(
                (
                    unique_id,
                    compiled,
                    output_columns,
                    self.schema,
                    self.dialect,
                    self._relation_to_node,
                )
            )
        return work

    def _output_columns(self, unique_id: str, model: Any) -> list:
        """The model's documented columns, falling back to the catalog's list."""
        output_columns = [c for c in (getattr(model, "columns", {}) or {})]
        if not output_columns:
            catalog_node = (getattr(self.catalog, "nodes", {}) or {}).get(unique_id)
            output_columns = (
                list(getattr(catalog_node, "columns", {}) or {}) if catalog_node else []
            )
        return output_columns

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
