"""Tests for dbdocs.extract.tests_index."""

from types import SimpleNamespace

from dbdocs.extract.tests_index import (
    build_column_tests_index,
    manifest_test_node_details,
    manifest_test_node_metadata,
)


def _test_node(test_type=None, attached=None, column=None):
    """A manifest test node stub."""
    metadata = SimpleNamespace(name=test_type) if test_type is not None else None
    return SimpleNamespace(
        test_metadata=metadata,
        attached_node=attached,
        column_name=column,
    )


def _manifest(nodes):
    return SimpleNamespace(nodes=nodes)


def test_manifest_test_node_metadata_full():
    node = _test_node("not_null", "model.shop.orders", "id")
    assert manifest_test_node_metadata(node) == ("not_null", "model.shop.orders", "id")


def test_manifest_test_node_metadata_no_test_metadata():
    node = SimpleNamespace(test_metadata=None, attached_node="model.shop.orders", column_name="id")
    test_type, attached, column = manifest_test_node_metadata(node)
    assert test_type == ""
    assert attached == "model.shop.orders"
    assert column == "id"


def test_manifest_test_node_metadata_missing_attrs():
    node = SimpleNamespace()
    assert manifest_test_node_metadata(node) == ("", "", "")


def test_manifest_test_node_metadata_blank_values():
    node = _test_node("", "model.shop.orders", "")
    test_type, attached, column = manifest_test_node_metadata(node)
    assert test_type == ""
    assert attached == "model.shop.orders"
    assert column == ""


def _detail_node(description=None, kwargs=None):
    metadata = (
        SimpleNamespace(kwargs=kwargs) if kwargs is not None else SimpleNamespace(kwargs=None)
    )
    return SimpleNamespace(description=description, test_metadata=metadata)


def test_manifest_test_node_details_filters_hidden_kwargs_and_keeps_user_kwargs():
    node = _detail_node(
        description="Customer must be a known segment.",
        kwargs={
            "model": "{{ ref('customers') }}",  # hidden — already in its own column
            "column_name": "segment",  # hidden — duplicated
            "severity": "warn",  # hidden — noise
            "accepted_values": ["bronze", "silver", "gold"],
            "quote": True,
        },
    )
    description, kwargs = manifest_test_node_details(node)
    assert description == "Customer must be a known segment."
    assert kwargs == {"accepted_values": ["bronze", "silver", "gold"], "quote": True}


def test_manifest_test_node_details_stringifies_unknown_value_types():
    node = _detail_node(kwargs={"expression": object()})
    _, kwargs = manifest_test_node_details(node)
    assert "expression" in kwargs and isinstance(kwargs["expression"], str)


def test_manifest_test_node_details_missing_fields():
    description, kwargs = manifest_test_node_details(SimpleNamespace())
    assert description == ""
    assert kwargs == {}


def test_manifest_test_node_details_non_dict_kwargs_ignored():
    node = SimpleNamespace(description="d", test_metadata=SimpleNamespace(kwargs="not a dict"))
    description, kwargs = manifest_test_node_details(node)
    assert description == "d"
    assert kwargs == {}


def test_build_column_tests_index_basic():
    manifest = _manifest(
        {
            "test.shop.not_null_orders_id.abc": _test_node("not_null", "model.shop.orders", "id"),
            "test.shop.unique_orders_id.def": _test_node("unique", "model.shop.orders", "id"),
            "test.shop.not_null_orders_name.ghi": _test_node(
                "not_null", "model.shop.orders", "name"
            ),
        }
    )
    index = build_column_tests_index(manifest)
    assert index == {
        "model.shop.orders": {
            "id": ["not_null", "unique"],
            "name": ["not_null"],
        }
    }


def test_build_column_tests_index_case_insensitive_column_key():
    manifest = _manifest(
        {
            "test.shop.not_null_orders_SUPPLY_UUID.abc": _test_node(
                "not_null", "model.shop.orders", "SUPPLY_UUID"
            ),
        }
    )
    index = build_column_tests_index(manifest)
    assert "supply_uuid" in index.get("model.shop.orders", {})
    assert "SUPPLY_UUID" not in index.get("model.shop.orders", {})


def test_build_column_tests_index_skips_table_level_tests():
    manifest = _manifest(
        {
            "test.shop.expression_is_true_orders.abc": _test_node(
                "expression_is_true", "model.shop.orders", None
            ),
        }
    )
    assert build_column_tests_index(manifest) == {}


def test_build_column_tests_index_skips_non_test_nodes():
    manifest = _manifest(
        {
            "model.shop.orders": SimpleNamespace(test_metadata=None),
            "source.shop.raw.orders": SimpleNamespace(test_metadata=None),
        }
    )
    assert build_column_tests_index(manifest) == {}


def test_build_column_tests_index_skips_missing_attached_node():
    manifest = _manifest(
        {
            "test.shop.not_null_x.abc": _test_node("not_null", None, "id"),
        }
    )
    assert build_column_tests_index(manifest) == {}


def test_build_column_tests_index_skips_missing_test_metadata():
    manifest = _manifest(
        {
            "test.shop.custom_test.abc": SimpleNamespace(
                test_metadata=None,
                attached_node="model.shop.orders",
                column_name="id",
            ),
        }
    )
    assert build_column_tests_index(manifest) == {}


def test_build_column_tests_index_skips_blank_test_type():
    manifest = _manifest(
        {
            "test.shop.custom_test.abc": _test_node("", "model.shop.orders", "id"),
        }
    )
    assert build_column_tests_index(manifest) == {}


def test_build_column_tests_index_deduplicates_and_sorts():
    manifest = _manifest(
        {
            "test.shop.not_null_a.1": _test_node("not_null", "model.shop.orders", "id"),
            "test.shop.not_null_b.2": _test_node("not_null", "model.shop.orders", "id"),
            "test.shop.unique_a.3": _test_node("unique", "model.shop.orders", "id"),
        }
    )
    index = build_column_tests_index(manifest)
    assert index["model.shop.orders"]["id"] == ["not_null", "unique"]


def test_build_column_tests_index_empty_manifest():
    assert build_column_tests_index(SimpleNamespace(nodes={})) == {}


def test_build_column_tests_index_none_nodes():
    assert build_column_tests_index(SimpleNamespace(nodes=None)) == {}


def test_build_column_tests_index_multiple_nodes():
    manifest = _manifest(
        {
            "test.shop.not_null_orders_id.a": _test_node("not_null", "model.shop.orders", "id"),
            "test.shop.not_null_customers_id.b": _test_node(
                "not_null", "model.shop.customers", "id"
            ),
        }
    )
    index = build_column_tests_index(manifest)
    assert "model.shop.orders" in index
    assert "model.shop.customers" in index
    assert index["model.shop.orders"]["id"] == ["not_null"]
    assert index["model.shop.customers"]["id"] == ["not_null"]
