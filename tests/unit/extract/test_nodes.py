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


def test_build_nodes_without_catalog_entry_has_no_columns(fake_manifest):
    # An empty catalog: every node has zero columns but is still built.
    empty_catalog = SimpleNamespace(nodes={}, sources={})
    record = nodes_mod.build_nodes(fake_manifest, empty_catalog)["model.shop.customers"]
    assert record["columns"] == []


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
