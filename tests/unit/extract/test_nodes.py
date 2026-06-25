from types import SimpleNamespace

import pytest

from dbdocs.extract import nodes as nodes_mod
from tests.conftest import (
    exposure_entity,
    make_test_node,
    metric_entity,
    saved_query_entity,
    semantic_model_entity,
    unit_test_entity,
)


def test_build_nodes_includes_models_sources_seeds_skips_tests(fake_manifest, fake_catalog):
    result = nodes_mod.build_nodes(fake_manifest, fake_catalog)
    assert "model.shop.customers" in result
    assert "source.shop.ecom.raw_customers" in result
    assert "seed.shop.country_codes" in result
    assert "test.shop.not_null_customers_id" not in result


def test_build_nodes_merges_columns_and_escapes_newlines(fake_manifest, fake_catalog):
    record = nodes_mod.build_nodes(fake_manifest, fake_catalog)["model.shop.customers"]
    assert record["database"] == "db"
    assert record["schema"] == "analytics"
    assert record["resource_type"] == "model"
    assert record["relation_name"] == "db.analytics.customers"
    by_name = {c["name"]: c for c in record["columns"]}
    assert by_name["id"]["type"] == "integer"
    assert by_name["id"]["tags"] == ["pk"]
    assert by_name["id"]["description"] == "primary<br>key"
    assert record["raw_code"].startswith("select * from")
    assert record["compiled_code"].startswith("select id, name")


def test_build_nodes_new_detail_fields_defaults(fake_manifest, fake_catalog):
    record = nodes_mod.build_nodes(fake_manifest, fake_catalog)["model.shop.customers"]
    assert record["materialization"] == "view"
    assert record["meta"] == {}
    assert record["access"] == ""
    assert record["group"] == ""
    assert record["contract_enforced"] is False
    assert record["version"] == ""
    assert record["latest_version"] == ""
    assert record["owner"] == ""
    assert record["original_file_path"] == ""
    assert record["patch_path"] == ""
    assert record["stats"] == {}


def test_node_record_materialization_from_config(fake_manifest, fake_catalog):
    entity = fake_manifest.nodes["model.shop.customers"]
    entity.config = SimpleNamespace(materialized="incremental", meta={"team": "analytics"})
    result = nodes_mod.build_nodes(fake_manifest, fake_catalog)["model.shop.customers"]
    assert result["materialization"] == "incremental"
    assert result["meta"] == {"team": "analytics"}


def test_node_record_meta_prefers_node_over_config():
    entity = SimpleNamespace(
        name="m",
        database="db",
        schema_="s",
        description="",
        tags=[],
        relation_name="",
        package_name="p",
        language="sql",
        raw_code="",
        compiled_code="",
        columns={},
        depends_on=SimpleNamespace(nodes=[], macros=[]),
        config=SimpleNamespace(materialized="view", meta={"from": "config"}),
        meta={"from": "node"},
        access="",
        group="",
        contract=SimpleNamespace(enforced=False),
        version=None,
        latest_version=None,
        owner=None,
        original_file_path="",
        patch_path="",
    )
    manifest = SimpleNamespace(nodes={"model.p.m": entity}, sources={}, macros={})
    catalog = SimpleNamespace(nodes={}, sources={})
    result = nodes_mod.build_nodes(manifest, catalog)["model.p.m"]
    assert result["meta"] == {"from": "node"}


def test_node_record_owner_name_email():
    entity = SimpleNamespace(
        name="m",
        database="db",
        schema_="s",
        description="",
        tags=[],
        relation_name="",
        package_name="p",
        language="sql",
        raw_code="",
        compiled_code="",
        columns={},
        depends_on=SimpleNamespace(nodes=[], macros=[]),
        config=SimpleNamespace(materialized="view", meta={}),
        meta={},
        access="",
        group="",
        contract=SimpleNamespace(enforced=False),
        version=None,
        latest_version=None,
        owner=SimpleNamespace(name="Alice", email="alice@example.com"),
        original_file_path="",
        patch_path="",
    )
    manifest = SimpleNamespace(nodes={"model.p.m": entity}, sources={}, macros={})
    catalog = SimpleNamespace(nodes={}, sources={})
    result = nodes_mod.build_nodes(manifest, catalog)["model.p.m"]
    assert result["owner"] == "Alice"


def test_node_record_owner_email_fallback():
    entity = SimpleNamespace(
        name="m",
        database="db",
        schema_="s",
        description="",
        tags=[],
        relation_name="",
        package_name="p",
        language="sql",
        raw_code="",
        compiled_code="",
        columns={},
        depends_on=SimpleNamespace(nodes=[], macros=[]),
        config=SimpleNamespace(materialized="view", meta={}),
        meta={},
        access="",
        group="",
        contract=SimpleNamespace(enforced=False),
        version=None,
        latest_version=None,
        owner=SimpleNamespace(name="", email="bob@example.com"),
        original_file_path="",
        patch_path="",
    )
    manifest = SimpleNamespace(nodes={"model.p.m": entity}, sources={}, macros={})
    catalog = SimpleNamespace(nodes={}, sources={})
    result = nodes_mod.build_nodes(manifest, catalog)["model.p.m"]
    assert result["owner"] == "bob@example.com"


def test_catalog_stats_include_filter():
    stat_included = SimpleNamespace(label="Row Count", value=42, include=True)
    stat_excluded = SimpleNamespace(label="Has Stats?", value=True, include=False)
    catalog_node = SimpleNamespace(stats={"row_count": stat_included, "has_stats": stat_excluded})
    result = nodes_mod._catalog_stats(catalog_node)
    assert "row_count" in result
    assert result["row_count"] == {"label": "Row Count", "value": 42}
    assert "has_stats" not in result


def test_catalog_stats_empty_when_no_catalog():
    assert nodes_mod._catalog_stats(None) == {}


def test_catalog_stats_empty_stats_dict():
    assert nodes_mod._catalog_stats(SimpleNamespace(stats={})) == {}


def test_node_record_contract_enforced():
    entity = SimpleNamespace(
        name="m",
        database="db",
        schema_="s",
        description="",
        tags=[],
        relation_name="",
        package_name="p",
        language="sql",
        raw_code="",
        compiled_code="",
        columns={},
        depends_on=SimpleNamespace(nodes=[], macros=[]),
        config=SimpleNamespace(materialized="view", meta={}),
        meta={},
        access="protected",
        group="analytics",
        contract=SimpleNamespace(enforced=True),
        version="2",
        latest_version="3",
        owner=None,
        original_file_path="models/m.sql",
        patch_path="models/m.yml",
    )
    manifest = SimpleNamespace(nodes={"model.p.m": entity}, sources={}, macros={})
    catalog = SimpleNamespace(nodes={}, sources={})
    result = nodes_mod.build_nodes(manifest, catalog)["model.p.m"]
    assert result["contract_enforced"] is True
    assert result["access"] == "protected"
    assert result["group"] == "analytics"
    assert result["version"] == "2"
    assert result["latest_version"] == "3"
    assert result["original_file_path"] == "models/m.sql"
    assert result["patch_path"] == "models/m.yml"


def test_build_nodes_keeps_manifest_columns_without_catalog(fake_manifest):
    empty_catalog = SimpleNamespace(nodes={}, sources={})
    record = nodes_mod.build_nodes(fake_manifest, empty_catalog)["model.shop.customers"]
    by_name = {c["name"]: c for c in record["columns"]}
    assert set(by_name) == {"id", "name"}
    assert by_name["id"]["description"] == "primary<br>key"
    assert by_name["id"]["tags"] == ["pk"]


def test_columns_manifest_is_base_catalog_enriches_type_case_insensitively():
    model = SimpleNamespace(
        columns={
            "location_id": SimpleNamespace(
                description="The unique key.", tags=["pk"], data_type="text"
            )
        }
    )
    catalog_node = SimpleNamespace(columns={"LOCATION_ID": SimpleNamespace(type="NUMBER")})
    cols = nodes_mod._columns(model, catalog_node, {})
    assert cols == [
        {
            "name": "location_id",
            "type": "NUMBER",
            "tags": ["pk"],
            "description": "The unique key.",
            "tests": [],
        }
    ]


def test_columns_type_falls_back_to_manifest_data_type():
    model = SimpleNamespace(
        columns={"amount": SimpleNamespace(description="", tags=[], data_type="numeric")}
    )
    assert nodes_mod._columns(model, None, {}) == [
        {"name": "amount", "type": "numeric", "tags": [], "description": "", "tests": []}
    ]


def test_columns_appends_catalog_only_columns_after_manifest():
    model = SimpleNamespace(
        columns={"id": SimpleNamespace(description="pk", tags=[], data_type="")}
    )
    catalog_node = SimpleNamespace(
        columns={"ID": SimpleNamespace(type="number"), "EXTRA": SimpleNamespace(type="text")}
    )
    cols = nodes_mod._columns(model, catalog_node, {})
    assert [(c["name"], c["type"]) for c in cols] == [("id", "number"), ("EXTRA", "text")]
    assert cols[1]["description"] == ""
    assert cols[0]["tests"] == []
    assert cols[1]["tests"] == []


def test_columns_empty_without_manifest_or_catalog():
    assert nodes_mod._columns(SimpleNamespace(columns={}), None, {}) == []


def test_macros_used_resolves_and_orders(fake_manifest):
    node = fake_manifest.nodes["model.shop.customers"]
    macros = nodes_mod.macros_used(fake_manifest, node)
    names = [(m["package"], m["name"]) for m in macros]
    assert ("shop", "cents") in names
    assert ("dbt", "builtin") in names
    assert len(macros) == 2
    assert names[0][0] == "shop"


def test_build_tree_groups_by_database_then_schema(fake_manifest, fake_catalog):
    result = nodes_mod.build_nodes(fake_manifest, fake_catalog)
    tree = nodes_mod.build_tree(result)
    assert list(tree) == ["db"]
    assert sorted(tree["db"]) == ["analytics", "raw"]
    assert "model.shop.customers" in tree["db"]["analytics"]
    assert "source.shop.ecom.raw_customers" in tree["db"]["raw"]
    assert "seed.shop.country_codes" in tree["db"]["raw"]


def test_columns_carry_defined_tests_from_manifest(fake_manifest, fake_catalog):
    record = nodes_mod.build_nodes(fake_manifest, fake_catalog)["model.shop.customers"]
    by_name = {c["name"]: c for c in record["columns"]}
    assert by_name["id"]["tests"] == ["not_null", "unique"]
    assert by_name["name"]["tests"] == []


def test_columns_tests_empty_when_no_test_nodes(fake_catalog):
    manifest = SimpleNamespace(
        nodes={
            "model.shop.orders": SimpleNamespace(
                name="orders",
                database="db",
                schema_="analytics",
                description="",
                tags=[],
                relation_name="",
                package_name="shop",
                language="sql",
                raw_code="",
                compiled_code="",
                columns={"amount": SimpleNamespace(description="", tags=[], data_type="")},
                depends_on=SimpleNamespace(nodes=[], macros=[]),
                config=SimpleNamespace(materialized="view", meta={}),
                meta={},
                access="",
                group="",
                contract=SimpleNamespace(enforced=False),
                version=None,
                latest_version=None,
                owner=None,
                original_file_path="",
                patch_path="",
            )
        },
        sources={},
        macros={},
    )
    result = nodes_mod.build_nodes(manifest, fake_catalog)
    by_name = {c["name"]: c for c in result["model.shop.orders"]["columns"]}
    assert by_name["amount"]["tests"] == []


def test_columns_tests_case_insensitive_match(fake_catalog):
    manifest = SimpleNamespace(
        nodes={
            "model.shop.orders": SimpleNamespace(
                name="orders",
                database="db",
                schema_="analytics",
                description="",
                tags=[],
                relation_name="",
                package_name="shop",
                language="sql",
                raw_code="",
                compiled_code="",
                columns={"supply_uuid": SimpleNamespace(description="", tags=[], data_type="")},
                depends_on=SimpleNamespace(nodes=[], macros=[]),
                config=SimpleNamespace(materialized="view", meta={}),
                meta={},
                access="",
                group="",
                contract=SimpleNamespace(enforced=False),
                version=None,
                latest_version=None,
                owner=None,
                original_file_path="",
                patch_path="",
            ),
            "test.shop.not_null_orders_SUPPLY_UUID.abc": make_test_node(
                test_type="not_null",
                attached_node="model.shop.orders",
                column_name="SUPPLY_UUID",
            ),
        },
        sources={},
        macros={},
    )
    result = nodes_mod.build_nodes(manifest, fake_catalog)
    cols = {c["name"]: c for c in result["model.shop.orders"]["columns"]}
    assert cols["supply_uuid"]["tests"] == ["not_null"]


def test_columns_tests_catalog_only_columns_also_get_tests(fake_catalog):
    manifest = SimpleNamespace(
        nodes={
            "model.shop.orders": SimpleNamespace(
                name="orders",
                database="db",
                schema_="analytics",
                description="",
                tags=[],
                relation_name="",
                package_name="shop",
                language="sql",
                raw_code="",
                compiled_code="",
                columns={},
                depends_on=SimpleNamespace(nodes=[], macros=[]),
                config=SimpleNamespace(materialized="view", meta={}),
                meta={},
                access="",
                group="",
                contract=SimpleNamespace(enforced=False),
                version=None,
                latest_version=None,
                owner=None,
                original_file_path="",
                patch_path="",
            ),
            "test.shop.not_null_orders_id.abc": make_test_node(
                test_type="not_null",
                attached_node="model.shop.orders",
                column_name="ID",
            ),
        },
        sources={},
        macros={},
    )
    catalog_with_id = SimpleNamespace(
        nodes={
            "model.shop.orders": SimpleNamespace(
                columns={"ID": SimpleNamespace(type="integer")},
                stats={},
            )
        },
        sources={},
    )
    result = nodes_mod.build_nodes(manifest, catalog_with_id)
    cols = {c["name"]: c for c in result["model.shop.orders"]["columns"]}
    assert cols["ID"]["tests"] == ["not_null"]


def _empty_catalog():
    return SimpleNamespace(nodes={}, sources={})


def _manifest_with(**collections):
    return SimpleNamespace(nodes={}, sources={}, macros={}, **collections)


def test_build_nodes_analysis_and_operation_included(fake_catalog):
    manifest = SimpleNamespace(
        nodes={
            "analysis.shop.my_analysis": SimpleNamespace(
                name="my_analysis",
                database="db",
                schema_="analytics",
                description="an analysis",
                tags=[],
                relation_name="",
                package_name="shop",
                language="sql",
                raw_code="select 1",
                compiled_code="select 1",
                columns={},
                depends_on=SimpleNamespace(nodes=[], macros=[]),
                config=SimpleNamespace(materialized="", meta={}),
                meta={},
                access="",
                group="",
                contract=SimpleNamespace(enforced=False),
                version=None,
                latest_version=None,
                owner=None,
                original_file_path="",
                patch_path="",
            ),
            "operation.shop.my_op": SimpleNamespace(
                name="my_op",
                database="db",
                schema_="analytics",
                description="",
                tags=[],
                relation_name="",
                package_name="shop",
                language="sql",
                raw_code="create table t as select 1",
                compiled_code="create table t as select 1",
                columns={},
                depends_on=SimpleNamespace(nodes=[], macros=[]),
                config=SimpleNamespace(materialized="", meta={}),
                meta={},
                access="",
                group="",
                contract=SimpleNamespace(enforced=False),
                version=None,
                latest_version=None,
                owner=None,
                original_file_path="",
                patch_path="",
            ),
        },
        sources={},
        macros={},
    )
    result = nodes_mod.build_nodes(manifest, _empty_catalog())
    assert "analysis.shop.my_analysis" in result
    assert result["analysis.shop.my_analysis"]["resource_type"] == "analysis"
    assert result["analysis.shop.my_analysis"]["raw_code"] == "select 1"
    assert "operation.shop.my_op" in result
    assert result["operation.shop.my_op"]["resource_type"] == "operation"


def test_build_nodes_metric_record_basic():
    entity = metric_entity(
        "metric.shop.revenue",
        metric_type="simple",
        label="Revenue",
        depends_on_nodes=["semantic_model.shop.orders_sm"],
    )
    manifest = _manifest_with(metrics={"metric.shop.revenue": entity})
    result = nodes_mod.build_nodes(manifest, _empty_catalog())
    assert "metric.shop.revenue" in result
    rec = result["metric.shop.revenue"]
    assert rec["resource_type"] == "metric"
    assert rec["database"] == ""
    assert rec["schema"] == ""
    assert rec["metric"]["type"] == "simple"
    assert rec["metric"]["label"] == "Revenue"


def test_build_nodes_metric_type_params_none():
    entity = metric_entity("metric.shop.m", type_params=None)
    manifest = _manifest_with(metrics={"metric.shop.m": entity})
    result = nodes_mod.build_nodes(manifest, _empty_catalog())
    assert result["metric.shop.m"]["metric"]["type_params"] == {}


def test_build_nodes_metric_type_params_with_attrs():
    type_params = SimpleNamespace(
        measure="revenue_measure",
        numerator=None,
        denominator=None,
        expr=None,
        window=None,
        metrics=None,
    )
    entity = metric_entity("metric.shop.m", type_params=type_params)
    manifest = _manifest_with(metrics={"metric.shop.m": entity})
    result = nodes_mod.build_nodes(manifest, _empty_catalog())
    assert result["metric.shop.m"]["metric"]["type_params"] == {"measure": "revenue_measure"}


def test_build_nodes_metric_type_params_with_derived_metrics():
    type_params = SimpleNamespace(
        measure=None,
        numerator=None,
        denominator=None,
        expr=None,
        window=None,
        metrics=["metric.shop.a", "metric.shop.b"],
    )
    entity = metric_entity("metric.shop.derived", type_params=type_params)
    manifest = _manifest_with(metrics={"metric.shop.derived": entity})
    result = nodes_mod.build_nodes(manifest, _empty_catalog())
    assert result["metric.shop.derived"]["metric"]["type_params"]["metrics"] == [
        "metric.shop.a",
        "metric.shop.b",
    ]


def test_build_nodes_semantic_model_record():
    entities = [SimpleNamespace(name="order_id", type="primary")]
    dimensions = [SimpleNamespace(name="order_date", type="time")]
    measures = [SimpleNamespace(name="revenue", agg="sum", expr="amount")]
    entity = semantic_model_entity(
        "semantic_model.shop.orders_sm",
        model="ref('orders')",
        entities=entities,
        dimensions=dimensions,
        measures=measures,
    )
    manifest = _manifest_with(semantic_models={"semantic_model.shop.orders_sm": entity})
    result = nodes_mod.build_nodes(manifest, _empty_catalog())
    assert "semantic_model.shop.orders_sm" in result
    rec = result["semantic_model.shop.orders_sm"]
    assert rec["resource_type"] == "semantic_model"
    assert rec["database"] == ""
    assert rec["schema"] == ""
    assert rec["semantic_model"]["model"] == "ref('orders')"
    assert rec["semantic_model"]["entities"] == [{"name": "order_id", "type": "primary"}]
    assert rec["semantic_model"]["dimensions"] == [{"name": "order_date", "type": "time"}]
    assert rec["semantic_model"]["measures"] == [
        {"name": "revenue", "agg": "sum", "expr": "amount"}
    ]


def test_build_nodes_saved_query_record():
    export = SimpleNamespace(
        name="exp", config=SimpleNamespace(schema_="mart", alias="rev_export", export_as="table")
    )
    entity = saved_query_entity(
        "saved_query.shop.revenue_query",
        label="Revenue Query",
        metrics=["metric.shop.revenue"],
        group_by=["dim_date"],
        where=["is_active = true"],
        exports=[export],
    )
    manifest = _manifest_with(saved_queries={"saved_query.shop.revenue_query": entity})
    result = nodes_mod.build_nodes(manifest, _empty_catalog())
    assert "saved_query.shop.revenue_query" in result
    rec = result["saved_query.shop.revenue_query"]
    assert rec["resource_type"] == "saved_query"
    assert rec["database"] == ""
    assert rec["schema"] == ""
    assert rec["saved_query"]["metrics"] == ["metric.shop.revenue"]
    assert rec["saved_query"]["group_by"] == ["dim_date"]
    assert rec["saved_query"]["where"] == ["is_active = true"]
    assert rec["saved_query"]["exports"][0]["name"] == "exp"
    assert rec["saved_query"]["exports"][0]["schema"] == "mart"
    assert rec["saved_query"]["exports"][0]["export_as"] == "table"


def test_build_nodes_saved_query_no_query_params():
    entity = SimpleNamespace(
        name="q",
        label="",
        description="",
        query_params=None,
        exports=[],
        tags=[],
        meta={},
        package_name="shop",
        depends_on=SimpleNamespace(nodes=[]),
    )
    manifest = _manifest_with(saved_queries={"saved_query.shop.q": entity})
    result = nodes_mod.build_nodes(manifest, _empty_catalog())
    rec = result["saved_query.shop.q"]
    assert rec["saved_query"]["metrics"] == []
    assert rec["saved_query"]["group_by"] == []
    assert rec["saved_query"]["where"] == []


def test_build_nodes_unit_test_record():
    given = [
        SimpleNamespace(input="ref('orders')", rows=[{"id": 1, "amount": 10}], format="csv"),
        SimpleNamespace(input="ref('customers')", rows=[{"id": 1}, {"id": 2}], format="dict"),
    ]
    expect = SimpleNamespace(rows=[{"id": 1, "total": None}, {"id": 2, "total": 5}], format="dict")
    entity = unit_test_entity(
        "unit_test.shop.test_revenue",
        model="model.shop.revenue",
        given=given,
        expect=expect,
        depends_on_nodes=["model.shop.revenue"],
    )
    manifest = _manifest_with(unit_tests={"unit_test.shop.test_revenue": entity})
    result = nodes_mod.build_nodes(manifest, _empty_catalog())
    assert "unit_test.shop.test_revenue" in result
    rec = result["unit_test.shop.test_revenue"]
    assert rec["resource_type"] == "unit_test"
    assert rec["database"] == ""
    assert rec["schema"] == ""
    ut = rec["unit_test"]
    assert ut["model"] == "model.shop.revenue"
    assert ut["given_count"] == 2
    assert ut["given"] == [
        {
            "ref": "ref('orders')",
            "rows_count": 1,
            "format": "csv",
            "columns": ["id", "amount"],
            "rows": [{"id": "1", "amount": "10"}],
            "sql": "",
        },
        {
            "ref": "ref('customers')",
            "rows_count": 2,
            "format": "dict",
            "columns": ["id"],
            "rows": [{"id": "1"}, {"id": "2"}],
            "sql": "",
        },
    ]
    assert ut["expect_rows"] == 2
    assert ut["expect_format"] == "dict"
    assert ut["expect_columns"] == ["id", "total"]
    assert ut["expect_data"] == [{"id": "1", "total": ""}, {"id": "2", "total": "5"}]
    assert ut["expect_sql"] == ""
    assert ut["given_summary"] == ["ref('orders')", "ref('customers')"]


def test_build_nodes_unit_test_sql_fixture():
    given = [SimpleNamespace(input="ref('orders')", rows="select 1 as id", format="sql")]
    expect = SimpleNamespace(rows="select 1 as id", format="sql")
    entity = unit_test_entity("unit_test.shop.t", model="model.shop.m", given=given, expect=expect)
    manifest = _manifest_with(unit_tests={"unit_test.shop.t": entity})
    result = nodes_mod.build_nodes(manifest, _empty_catalog())
    ut = result["unit_test.shop.t"]["unit_test"]
    assert ut["given"][0]["sql"] == "select 1 as id"
    assert ut["given"][0]["rows"] == []
    assert ut["given"][0]["columns"] == []
    assert ut["given"][0]["rows_count"] == 0
    assert ut["expect_sql"] == "select 1 as id"
    assert ut["expect_data"] == []
    assert ut["expect_columns"] == []


def test_build_nodes_unit_test_caps_rows_keeps_total():
    big = [{"id": i} for i in range(nodes_mod._FIXTURE_ROW_CAP + 7)]
    given = [SimpleNamespace(input="ref('orders')", rows=big, format="dict")]
    expect = SimpleNamespace(rows=big, format="dict")
    entity = unit_test_entity("unit_test.shop.t", model="model.shop.m", given=given, expect=expect)
    manifest = _manifest_with(unit_tests={"unit_test.shop.t": entity})
    result = nodes_mod.build_nodes(manifest, _empty_catalog())
    ut = result["unit_test.shop.t"]["unit_test"]
    assert len(ut["given"][0]["rows"]) == nodes_mod._FIXTURE_ROW_CAP
    assert ut["given"][0]["rows_count"] == nodes_mod._FIXTURE_ROW_CAP + 7
    assert len(ut["expect_data"]) == nodes_mod._FIXTURE_ROW_CAP
    assert ut["expect_rows"] == nodes_mod._FIXTURE_ROW_CAP + 7


def test_build_nodes_unit_test_no_expect():
    entity = unit_test_entity("unit_test.shop.t", model="model.shop.m", given=[], expect=None)
    manifest = _manifest_with(unit_tests={"unit_test.shop.t": entity})
    result = nodes_mod.build_nodes(manifest, _empty_catalog())
    ut = result["unit_test.shop.t"]["unit_test"]
    assert ut["expect_rows"] == 0
    assert ut["expect_format"] == ""
    assert ut["expect_columns"] == []
    assert ut["expect_data"] == []
    assert ut["expect_sql"] == ""
    assert ut["given"] == []


@pytest.mark.parametrize(
    "owner_name,owner_email,expected_name,expected_email",
    [
        ("Alice", "alice@x.com", "Alice", "alice@x.com"),
        ("", "bob@x.com", "", "bob@x.com"),
        ("", "", "", ""),
    ],
)
def test_build_nodes_exposure_record(owner_name, owner_email, expected_name, expected_email):
    entity = exposure_entity(
        "exposure.shop.my_dashboard",
        exposure_type="dashboard",
        label="My Dashboard",
        maturity="high",
        url="https://example.com/dash",
        owner_name=owner_name,
        owner_email=owner_email,
        depends_on_nodes=["model.shop.revenue"],
    )
    manifest = _manifest_with(exposures={"exposure.shop.my_dashboard": entity})
    result = nodes_mod.build_nodes(manifest, _empty_catalog())
    assert "exposure.shop.my_dashboard" in result
    rec = result["exposure.shop.my_dashboard"]
    assert rec["resource_type"] == "exposure"
    assert rec["database"] == ""
    assert rec["schema"] == ""
    assert rec["exposure"]["type"] == "dashboard"
    assert rec["exposure"]["url"] == "https://example.com/dash"
    assert rec["exposure"]["owner_name"] == expected_name
    assert rec["exposure"]["owner_email"] == expected_email


def test_build_nodes_empty_collections_produce_no_nodes(fake_catalog):
    manifest = SimpleNamespace(
        nodes={},
        sources={},
        macros={},
        metrics={},
        semantic_models={},
        saved_queries={},
        unit_tests={},
        exposures={},
    )
    result = nodes_mod.build_nodes(manifest, fake_catalog)
    assert result == {}


def test_build_tree_excludes_typeless_resources():
    entity = metric_entity("metric.shop.revenue")
    manifest = _manifest_with(metrics={"metric.shop.revenue": entity})
    nodes = nodes_mod.build_nodes(manifest, _empty_catalog())
    tree = nodes_mod.build_tree(nodes)
    assert tree == {}


def test_build_tree_physical_nodes_present_typeless_excluded(fake_manifest, fake_catalog):
    entity = metric_entity("metric.shop.revenue")
    fake_manifest.metrics = {"metric.shop.revenue": entity}
    nodes = nodes_mod.build_nodes(fake_manifest, fake_catalog)
    tree = nodes_mod.build_tree(nodes)
    assert "db" in tree
    assert "metric.shop.revenue" not in str(tree)


def _fake_enum(value):
    """A minimal enum-like object: has a ``.value`` attribute."""
    return SimpleNamespace(value=value)


def _fake_measure(name):
    """A minimal Measure/MetricInput-like object: has a ``.name`` attribute."""
    return SimpleNamespace(name=name)


def test_enum_value_unwraps_enum_like_object():
    assert nodes_mod._enum_value(_fake_enum("derived")) == "derived"


def test_enum_value_passes_plain_string_through():
    assert nodes_mod._enum_value("simple") == "simple"


def test_object_name_extracts_name_attribute():
    assert nodes_mod._object_name(_fake_measure("revenue")) == "revenue"


def test_object_name_stringifies_plain_value():
    assert nodes_mod._object_name("plain_metric") == "plain_metric"


def test_object_name_extracts_inner_name_from_entity_repr():
    assert nodes_mod._object_name("Entity('customer')") == "customer"
    assert nodes_mod._object_name('Dimension("ds")') == "ds"
    assert nodes_mod._object_name("not_a_repr") == "not_a_repr"


def test_metric_type_is_unwrapped_from_enum():
    entity = metric_entity("metric.shop.m", metric_type=_fake_enum("derived"))
    manifest = _manifest_with(metrics={"metric.shop.m": entity})
    result = nodes_mod.build_nodes(manifest, _empty_catalog())
    assert result["metric.shop.m"]["metric"]["type"] == "derived"


def test_metric_type_params_measure_object_extracts_name():
    type_params = SimpleNamespace(
        measure=_fake_measure("revenue_measure"),
        numerator=None,
        denominator=None,
        expr=None,
        window=None,
        metrics=None,
        input_measures=None,
    )
    entity = metric_entity("metric.shop.m", type_params=type_params)
    manifest = _manifest_with(metrics={"metric.shop.m": entity})
    result = nodes_mod.build_nodes(manifest, _empty_catalog())
    assert result["metric.shop.m"]["metric"]["type_params"]["measure"] == "revenue_measure"


def test_metric_type_params_numerator_denominator_objects():
    type_params = SimpleNamespace(
        measure=None,
        numerator=_fake_measure("num_measure"),
        denominator=_fake_measure("den_measure"),
        expr=None,
        window=None,
        metrics=None,
        input_measures=None,
    )
    entity = metric_entity("metric.shop.ratio", type_params=type_params)
    manifest = _manifest_with(metrics={"metric.shop.ratio": entity})
    result = nodes_mod.build_nodes(manifest, _empty_catalog())
    tp = result["metric.shop.ratio"]["metric"]["type_params"]
    assert tp["numerator"] == "num_measure"
    assert tp["denominator"] == "den_measure"


def test_metric_type_params_metrics_list_of_objects():
    type_params = SimpleNamespace(
        measure=None,
        numerator=None,
        denominator=None,
        expr="a / b",
        window=None,
        metrics=[_fake_measure("count_orders"), _fake_measure("lifetime_spend")],
        input_measures=None,
    )
    entity = metric_entity("metric.shop.derived", type_params=type_params)
    manifest = _manifest_with(metrics={"metric.shop.derived": entity})
    result = nodes_mod.build_nodes(manifest, _empty_catalog())
    tp = result["metric.shop.derived"]["metric"]["type_params"]
    assert tp["metrics"] == ["count_orders", "lifetime_spend"]
    assert tp["expr"] == "a / b"


def test_metric_type_params_input_measures():
    type_params = SimpleNamespace(
        measure=_fake_measure("revenue"),
        numerator=None,
        denominator=None,
        expr=None,
        window=None,
        metrics=None,
        input_measures=[_fake_measure("revenue"), _fake_measure("tax")],
    )
    entity = metric_entity("metric.shop.m", type_params=type_params)
    manifest = _manifest_with(metrics={"metric.shop.m": entity})
    result = nodes_mod.build_nodes(manifest, _empty_catalog())
    tp = result["metric.shop.m"]["metric"]["type_params"]
    assert tp["input_measures"] == ["revenue", "tax"]


def test_sm_items_enum_type_and_agg_unwrapped():
    entities = [SimpleNamespace(name="customer_id", type=_fake_enum("primary"))]
    dimensions = [SimpleNamespace(name="signup_date", type=_fake_enum("time"))]
    measures = [SimpleNamespace(name="revenue", agg=_fake_enum("sum"), expr="amount")]
    entity = semantic_model_entity(
        "semantic_model.shop.customers_sm",
        entities=entities,
        dimensions=dimensions,
        measures=measures,
    )
    manifest = _manifest_with(semantic_models={"semantic_model.shop.customers_sm": entity})
    result = nodes_mod.build_nodes(manifest, _empty_catalog())
    sm = result["semantic_model.shop.customers_sm"]["semantic_model"]
    assert sm["entities"][0] == {"name": "customer_id", "type": "primary"}
    assert sm["dimensions"][0] == {"name": "signup_date", "type": "time"}
    assert sm["measures"][0] == {"name": "revenue", "agg": "sum", "expr": "amount"}


def test_export_item_schema_name_and_enum_export_as():
    config = SimpleNamespace(
        schema_name="mart",
        alias="rev_export",
        export_as=_fake_enum("table"),
    )
    export = SimpleNamespace(name="rev", config=config)
    result = nodes_mod._export_item(export)
    assert result["schema"] == "mart"
    assert result["export_as"] == "table"


def test_export_item_export_as_plain_string():
    config = SimpleNamespace(schema_name=None, alias="", export_as="view")
    export = SimpleNamespace(name="x", config=config)
    result = nodes_mod._export_item(export)
    assert result["export_as"] == "view"
    assert result["schema"] == ""


def test_export_item_no_config():
    export = SimpleNamespace(name="y", config=None)
    result = nodes_mod._export_item(export)
    assert result["schema"] == ""
    assert result["export_as"] == ""


def test_build_tree_multiple_physical_databases_sorted(fake_catalog):
    manifest = SimpleNamespace(
        nodes={
            "model.shop.orders": SimpleNamespace(
                name="orders",
                database="zeta_db",
                schema_="analytics",
                description="",
                tags=[],
                relation_name="",
                package_name="shop",
                language="sql",
                raw_code="",
                compiled_code="",
                columns={},
                depends_on=SimpleNamespace(nodes=[], macros=[]),
                config=SimpleNamespace(materialized="view", meta={}),
                meta={},
                access="",
                group="",
                contract=SimpleNamespace(enforced=False),
                version=None,
                latest_version=None,
                owner=None,
                original_file_path="",
                patch_path="",
            ),
            "model.shop.accounts": SimpleNamespace(
                name="accounts",
                database="alpha_db",
                schema_="analytics",
                description="",
                tags=[],
                relation_name="",
                package_name="shop",
                language="sql",
                raw_code="",
                compiled_code="",
                columns={},
                depends_on=SimpleNamespace(nodes=[], macros=[]),
                config=SimpleNamespace(materialized="view", meta={}),
                meta={},
                access="",
                group="",
                contract=SimpleNamespace(enforced=False),
                version=None,
                latest_version=None,
                owner=None,
                original_file_path="",
                patch_path="",
            ),
        },
        sources={},
        macros={},
    )
    nodes = nodes_mod.build_nodes(manifest, _empty_catalog())
    tree = nodes_mod.build_tree(nodes)
    db_keys = list(tree.keys())
    assert db_keys == ["alpha_db", "zeta_db"]


def test_build_nodes_unit_test_given_summary_none_input_uses_fallback():
    given = [
        SimpleNamespace(input=None, rows=[], format=None),
        SimpleNamespace(input=None, rows=[], format=None),
    ]
    entity = unit_test_entity("unit_test.shop.t", given=given)
    manifest = _manifest_with(unit_tests={"unit_test.shop.t": entity})
    result = nodes_mod.build_nodes(manifest, _empty_catalog())
    ut = result["unit_test.shop.t"]["unit_test"]
    assert ut["given_summary"] == ["input 0", "input 1"]
    assert ut["given"] == [
        {"ref": "input 0", "rows_count": 0, "format": "", "columns": [], "rows": [], "sql": ""},
        {"ref": "input 1", "rows_count": 0, "format": "", "columns": [], "rows": [], "sql": ""},
    ]


def test_build_nodes_unit_test_given_summary_empty_string_input_preserved():
    given = [
        SimpleNamespace(input="", rows=[], format="csv"),
        SimpleNamespace(input="ref('orders')", rows=[{"id": 1}], format="dict"),
    ]
    entity = unit_test_entity("unit_test.shop.t", given=given)
    manifest = _manifest_with(unit_tests={"unit_test.shop.t": entity})
    result = nodes_mod.build_nodes(manifest, _empty_catalog())
    ut = result["unit_test.shop.t"]["unit_test"]
    assert ut["given_summary"] == ["", "ref('orders')"]
    assert ut["given"][1] == {
        "ref": "ref('orders')",
        "rows_count": 1,
        "format": "dict",
        "columns": ["id"],
        "rows": [{"id": "1"}],
        "sql": "",
    }


def test_build_nodes_unit_test_given_item_no_rows_attr():
    given = [SimpleNamespace(input="ref('a')")]
    entity = unit_test_entity("unit_test.shop.t", given=given)
    manifest = _manifest_with(unit_tests={"unit_test.shop.t": entity})
    result = nodes_mod.build_nodes(manifest, _empty_catalog())
    ut = result["unit_test.shop.t"]["unit_test"]
    assert ut["given"] == [
        {"ref": "ref('a')", "rows_count": 0, "format": "", "columns": [], "rows": [], "sql": ""}
    ]


def test_build_nodes_saved_query_group_by_entity_objects_use_object_name():
    entity_obj = SimpleNamespace(name="customer")
    entity = saved_query_entity(
        "saved_query.shop.q",
        group_by=[entity_obj, "plain_dim"],
    )
    manifest = _manifest_with(saved_queries={"saved_query.shop.q": entity})
    result = nodes_mod.build_nodes(manifest, _empty_catalog())
    assert result["saved_query.shop.q"]["saved_query"]["group_by"] == ["customer", "plain_dim"]


def test_exposure_record_enum_type_and_maturity():
    entity = exposure_entity(
        "exposure.shop.dash",
        exposure_type=_fake_enum("dashboard"),
        maturity=_fake_enum("high"),
        url="https://example.com",
        owner_name="Alice",
        owner_email="alice@x.com",
    )
    manifest = _manifest_with(exposures={"exposure.shop.dash": entity})
    result = nodes_mod.build_nodes(manifest, _empty_catalog())
    ex = result["exposure.shop.dash"]["exposure"]
    assert ex["type"] == "dashboard"
    assert ex["maturity"] == "high"
