import json

from dbterd.core.models import Column, Ref, Table
from dbterd.core.registry.plugin_registry import PluginRegistry

from dbdocs.extract import erd_json


def _table():
    return Table(
        name="customers",
        database="db",
        schema="analytics",
        columns=[
            Column(name="id", data_type="int", is_primary_key=True),
            Column(name="name", data_type="text"),
        ],
        resource_type="model",
        node_name="model.shop.customers",
        description="The customers.",
        label="customers",
    )


def test_column_to_dict():
    d = erd_json.column_to_dict(Column(name="id", data_type="int", is_primary_key=True))
    assert d == {"name": "id", "data_type": "int", "description": "", "is_primary_key": True}


def test_table_to_dict():
    d = erd_json.table_to_dict(_table())
    assert d["name"] == "customers"
    assert d["node_name"] == "model.shop.customers"
    assert d["schema"] == "analytics"
    assert [c["name"] for c in d["columns"]] == ["id", "name"]


def test_relationship_to_dict():
    ref = Ref(
        name="fk1",
        table_map=("stg_customers", "customers"),
        column_map=(["cust_id"], ["id"]),
        type="n1",
        relationship_label="c_to_s",
    )
    d = erd_json.relationship_to_dict(ref)
    assert d["table_map"] == ["stg_customers", "customers"]
    assert d["column_map"] == [["cust_id"], ["id"]]
    assert d["type"] == "n1"


def test_adapter_build_erd_emits_structured_json():
    ref = Ref(name="fk1", table_map=("a", "b"), column_map=(["x"], ["y"]), type="n1")
    adapter = erd_json.JsonAdapter()
    payload = json.loads(adapter.build_erd([_table()], [ref]))
    assert payload["tables"][0]["name"] == "customers"
    assert payload["relationships"][0]["name"] == "fk1"


def test_adapter_format_helpers_and_symbol():
    adapter = erd_json.JsonAdapter()
    assert json.loads(adapter.format_table(_table()))["name"] == "customers"
    ref = Ref(name="r", table_map=("a", "b"), column_map=(["x"], ["y"]))
    assert json.loads(adapter.format_relationship(ref))["name"] == "r"
    assert adapter.get_rel_symbol("n1") == ""


def test_adapter_is_registered():
    # Importing the module registered the "json" target.
    assert PluginRegistry.has_target("json")
