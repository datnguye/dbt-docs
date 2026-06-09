from types import SimpleNamespace

from sqlglot import exp

from dbdocs.extract import column_lineage
from dbdocs.extract.column_lineage import ColumnLineageExtractor, _to_dialect
from tests.conftest import column


def test_to_dialect_aliases_and_passthrough():
    assert _to_dialect("databricks") == "spark"
    assert _to_dialect("snowflake") == "snowflake"
    assert _to_dialect(None) is None
    assert _to_dialect("") is None


def test_extract_traces_columns_to_source(fake_manifest, fake_catalog):
    extractor = ColumnLineageExtractor(fake_manifest, fake_catalog, dialect="snowflake")
    result = extractor.extract()
    # customers.id traces back through stg_customers to the raw_customers source.
    assert extractor.skipped == 0
    customers_id = result.get("model.shop.customers.id")
    assert customers_id is not None
    nodes_hit = {u["node"] for u in customers_id}
    assert "model.shop.stg_customers" in nodes_hit


def test_extract_runs_in_parallel_above_threshold(monkeypatch, fake_manifest, fake_catalog):
    # Force the parallel path on the small fixture by lowering the threshold,
    # then run a real ProcessPoolExecutor end to end — same result as serial.
    monkeypatch.setattr(column_lineage, "_PARALLEL_THRESHOLD", 1)
    extractor = ColumnLineageExtractor(fake_manifest, fake_catalog, dialect="snowflake")
    result = extractor.extract()
    assert extractor.skipped == 0
    assert result.get("model.shop.customers.id") is not None


def test_extract_empty_when_no_models(fake_catalog):
    manifest = SimpleNamespace(nodes={}, sources={})
    assert ColumnLineageExtractor(manifest, fake_catalog).extract() == {}


def test_extract_skips_unparseable_model(fake_manifest, fake_catalog):
    fake_manifest.nodes["model.shop.customers"].compiled_code = "this is not valid SQL )("
    extractor = ColumnLineageExtractor(fake_manifest, fake_catalog, dialect="snowflake")
    result = extractor.extract()
    # The bad model is skipped (fail-soft); others still resolve.
    assert extractor.skipped >= 0
    assert "model.shop.stg_customers.id" in result


def test_extract_ignores_models_without_compiled_code(fake_manifest, fake_catalog):
    fake_manifest.nodes["model.shop.customers"].compiled_code = "   "
    extractor = ColumnLineageExtractor(fake_manifest, fake_catalog, dialect="snowflake")
    result = extractor.extract()
    assert not any(k.startswith("model.shop.customers.") for k in result)


def test_extract_falls_back_to_catalog_columns(fake_manifest, fake_catalog):
    # Strip the manifest columns so the extractor must use the catalog list.
    fake_manifest.nodes["model.shop.stg_customers"].columns = {}
    extractor = ColumnLineageExtractor(fake_manifest, fake_catalog, dialect="snowflake")
    result = extractor.extract()
    assert "model.shop.stg_customers.id" in result


def test_extract_returns_early_for_model_without_columns(fake_manifest, fake_catalog):
    # Drop both the manifest columns and the catalog node so there are no output
    # columns to trace — _extract_model bails before building a scope.
    fake_manifest.nodes["model.shop.customers"].columns = {}
    del fake_catalog.nodes["model.shop.customers"]
    extractor = ColumnLineageExtractor(fake_manifest, fake_catalog, dialect="snowflake")
    result = extractor.extract()
    assert not any(k.startswith("model.shop.customers.") for k in result)
    # The other model is unaffected.
    assert "model.shop.stg_customers.id" in result


def test_extract_skips_column_absent_from_select(fake_manifest, fake_catalog):
    # A declared column that the compiled SELECT doesn't actually project: the
    # shared scope builds fine, but tracing that one column raises and is skipped
    # while the real columns still resolve.
    fake_manifest.nodes["model.shop.customers"].columns["ghost"] = column("ghost")
    extractor = ColumnLineageExtractor(fake_manifest, fake_catalog, dialect="snowflake")
    result = extractor.extract()
    assert "model.shop.customers.ghost" not in result
    assert "model.shop.customers.id" in result


def test_relation_index_and_map_table(fake_manifest, fake_catalog):
    extractor = ColumnLineageExtractor(fake_manifest, fake_catalog)
    rel = extractor._relation_to_node
    # db.raw.raw_customers maps back to the source node.
    table = SimpleNamespace(catalog="db", db="raw", name="raw_customers")
    assert column_lineage._map_table(table, rel) == "source.shop.ecom.raw_customers"
    # An unknown table maps to None.
    unknown = SimpleNamespace(catalog="x", db="y", name="z")
    assert column_lineage._map_table(unknown, rel) is None


def test_extract_warns_and_counts_when_internal_error(monkeypatch, fake_manifest, fake_catalog):
    extractor = ColumnLineageExtractor(fake_manifest, fake_catalog, dialect="snowflake")

    def _boom(work):
        return work[0], {}, "boom"

    monkeypatch.setattr(column_lineage, "_extract_model_task", _boom)
    result = extractor.extract()
    assert result == {}
    assert extractor.skipped == 2  # both models reported an error


def test_schema_from_catalog_handles_missing_column_type(fake_manifest):
    catalog = SimpleNamespace(
        nodes={"model.shop.customers": SimpleNamespace(columns={"id": SimpleNamespace(type=None)})},
        sources={},
    )
    extractor = ColumnLineageExtractor(fake_manifest, catalog)
    schema = extractor.schema
    assert schema["db"]["analytics"]["customers"]["id"] == "UNKNOWN"


def test_relation_index_skips_entities_without_table(fake_catalog):
    manifest = SimpleNamespace(
        nodes={
            "model.shop.noname": SimpleNamespace(
                database="db", schema_="raw", alias=None, name=None, relation_name=None
            )
        },
        sources={},
    )
    extractor = ColumnLineageExtractor(manifest, fake_catalog)
    # The table-less entity contributes no relation keys.
    assert not any(v == "model.shop.noname" for v in extractor._relation_to_node.values())


def test_schema_from_catalog_skips_entities_without_table():
    # The matched manifest entity has neither alias nor name → no table key →
    # the schema build skips it (the `if not table` guard).
    manifest = SimpleNamespace(
        nodes={
            "model.shop.noname": SimpleNamespace(
                database="db", schema_="raw", alias=None, name=None, relation_name=None
            )
        },
        sources={},
    )
    catalog = SimpleNamespace(
        nodes={"model.shop.noname": SimpleNamespace(columns={"id": SimpleNamespace(type="int")})},
        sources={},
    )
    extractor = ColumnLineageExtractor(manifest, catalog)
    assert extractor.schema == {}


def test_schema_from_catalog_skips_catalog_node_without_manifest_entity(fake_manifest):
    catalog = SimpleNamespace(
        nodes={
            "model.shop.customers": SimpleNamespace(columns={"id": SimpleNamespace(type="int")})
        },
        sources={"source.unknown": SimpleNamespace(columns={"x": SimpleNamespace(type="int")})},
    )
    # source.unknown has no manifest entity, so it's skipped in the schema build.
    extractor = ColumnLineageExtractor(fake_manifest, catalog)
    assert "customers" in extractor.schema["db"]["analytics"]


def test_leaf_columns_dedupes_and_skips_unmapped(fake_manifest, fake_catalog):
    extractor = ColumnLineageExtractor(fake_manifest, fake_catalog, dialect="snowflake")
    root = SimpleNamespace(name="root", source=SimpleNamespace())

    def make(name, table):
        return SimpleNamespace(name=name, source=table)

    known = exp.Table(
        this=exp.to_identifier("raw_customers"),
        db=exp.to_identifier("raw"),
        catalog=exp.to_identifier("db"),
    )
    unknown = exp.Table(
        this=exp.to_identifier("nope"), db=exp.to_identifier("x"), catalog=exp.to_identifier("y")
    )
    not_a_table = SimpleNamespace()
    leaves = [
        make("t.id", known),
        make("t.id", known),
        make("u.x", unknown),
        make("v.y", not_a_table),
    ]

    def walk():
        yield root
        yield from leaves

    root.walk = walk
    result = column_lineage._leaf_columns(root, extractor._relation_to_node)
    # The known table appears once (deduped); unknown + non-table dropped.
    assert result == [{"node": "source.shop.ecom.raw_customers", "column": "id"}]


def test_module_logger_is_dbdocs():
    assert column_lineage.logger.name == "dbdocs"
