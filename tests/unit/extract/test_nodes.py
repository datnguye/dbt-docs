from types import SimpleNamespace

from dbdocs.extract import nodes as nodes_mod


def test_build_nodes_includes_models_sources_seeds_skips_tests(fake_manifest, fake_catalog):
    result = nodes_mod.build_nodes(fake_manifest, fake_catalog)
    assert "model.shop.customers" in result
    assert "source.shop.ecom.raw_customers" in result
    assert "seed.shop.country_codes" in result
    # The test node is not surfaced.
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
    # The manifest description's newline becomes <br>.
    assert by_name["id"]["description"] == "primary<br>key"
    assert record["raw_code"].startswith("select * from")
    assert record["compiled_code"].startswith("select id, name")


def test_build_nodes_keeps_manifest_columns_without_catalog(fake_manifest):
    # The manifest is the source of truth: with an empty catalog the documented
    # columns still render (they don't vanish), just without warehouse types.
    empty_catalog = SimpleNamespace(nodes={}, sources={})
    record = nodes_mod.build_nodes(fake_manifest, empty_catalog)["model.shop.customers"]
    by_name = {c["name"]: c for c in record["columns"]}
    assert set(by_name) == {"id", "name"}
    assert by_name["id"]["description"] == "primary<br>key"
    assert by_name["id"]["tags"] == ["pk"]


def test_columns_manifest_is_base_catalog_enriches_type_case_insensitively():
    # Manifest order + metadata is the base; the catalog enriches the type. The
    # catalog upper-cases names (Snowflake) so the type match is case-insensitive,
    # and the displayed name stays the manifest's modeled casing.
    model = SimpleNamespace(
        columns={
            "location_id": SimpleNamespace(
                description="The unique key.", tags=["pk"], data_type="text"
            )
        }
    )
    catalog_node = SimpleNamespace(columns={"LOCATION_ID": SimpleNamespace(type="NUMBER")})
    cols = nodes_mod._columns(model, catalog_node)
    assert cols == [
        {"name": "location_id", "type": "NUMBER", "tags": ["pk"], "description": "The unique key."}
    ]


def test_columns_type_falls_back_to_manifest_data_type():
    # No catalog → the manifest's own data_type is shown; column never dropped.
    model = SimpleNamespace(
        columns={"amount": SimpleNamespace(description="", tags=[], data_type="numeric")}
    )
    assert nodes_mod._columns(model, None) == [
        {"name": "amount", "type": "numeric", "tags": [], "description": ""}
    ]


def test_columns_appends_catalog_only_columns_after_manifest():
    # A warehouse column the manifest never documented is appended after the
    # documented ones — enrichment adds, it doesn't reorder the manifest.
    model = SimpleNamespace(
        columns={"id": SimpleNamespace(description="pk", tags=[], data_type="")}
    )
    catalog_node = SimpleNamespace(
        columns={"ID": SimpleNamespace(type="number"), "EXTRA": SimpleNamespace(type="text")}
    )
    cols = nodes_mod._columns(model, catalog_node)
    assert [(c["name"], c["type"]) for c in cols] == [("id", "number"), ("EXTRA", "text")]
    assert cols[1]["description"] == ""


def test_columns_empty_without_manifest_or_catalog():
    assert nodes_mod._columns(SimpleNamespace(columns={}), None) == []


def test_macros_used_resolves_and_orders(fake_manifest):
    node = fake_manifest.nodes["model.shop.customers"]
    macros = nodes_mod.macros_used(fake_manifest, node)
    # The missing macro id (not in manifest.macros) is dropped.
    names = [(m["package"], m["name"]) for m in macros]
    assert ("shop", "cents") in names
    assert ("dbt", "builtin") in names
    assert len(macros) == 2
    # Project-package macro (shop) sorts before the dbt builtin.
    assert names[0][0] == "shop"


def test_build_tree_groups_by_database_then_schema(fake_manifest, fake_catalog):
    result = nodes_mod.build_nodes(fake_manifest, fake_catalog)
    tree = nodes_mod.build_tree(result)
    assert list(tree) == ["db"]
    assert sorted(tree["db"]) == ["analytics", "raw"]
    assert "model.shop.customers" in tree["db"]["analytics"]
    # raw schema holds the staging model, the source and the seed.
    assert "source.shop.ecom.raw_customers" in tree["db"]["raw"]
    assert "seed.shop.country_codes" in tree["db"]["raw"]
