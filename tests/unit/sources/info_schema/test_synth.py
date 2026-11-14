import json
from datetime import datetime, timezone

from dbdocs.sources.info_schema import synth
from dbdocs.sources.info_schema.reader import InfoSchemaReader


def _reader(v2_parquet_only):
    return InfoSchemaReader(v2_parquet_only / "info_schema" / "v1")


def test_manifest_covers_every_collection(v2_parquet_only):
    manifest = synth.build_manifest(_reader(v2_parquet_only))
    assert len(manifest["nodes"]) == 13 + 6 + 27
    assert len(manifest["sources"]) == 6
    assert len(manifest["metrics"]) == 23
    assert manifest["metadata"]["dbt_schema_version"] == synth.MANIFEST_SCHEMA
    assert manifest["metadata"]["adapter_type"] == "duckdb"
    orders = manifest["nodes"]["model.jaffle_shop.orders"]
    assert orders["path"] == "marts/orders.sql"
    assert orders["patch_path"] == "jaffle_shop://models/marts/orders.yml"
    assert orders["config"]["materialized"] == "table"
    assert orders["depends_on"]["nodes"]
    assert "version" not in orders
    assert orders["columns"]["order_id"]["name"] == "order_id"
    assert manifest["parent_map"]["model.jaffle_shop.orders"] == orders["depends_on"]["nodes"]


def test_unit_test_checksum_is_a_string(v2_parquet_only):
    manifest = synth.build_manifest(_reader(v2_parquet_only))
    assert all(u["checksum"] == "" for u in manifest["unit_tests"].values())


def test_test_node_carries_metadata(v2_parquet_only):
    manifest = synth.build_manifest(_reader(v2_parquet_only))
    tests = [n for n in manifest["nodes"].values() if n["resource_type"] == "test"]
    relationship = next(t for t in tests if t["test_metadata"]["name"] == "relationships")
    assert relationship["test_metadata"]["kwargs"]["to"].startswith("ref(")
    assert relationship["attached_node"].startswith("model.")


def test_semantic_model_parts_are_nested(v2_parquet_only):
    manifest = synth.build_manifest(_reader(v2_parquet_only))
    model = manifest["semantic_models"]["semantic_model.jaffle_shop.orders"]
    assert {e["name"] for e in model["entities"]}
    assert model["measures"][0]["agg"]
    assert any("type_params" in d for d in model["dimensions"])
    assert any("type_params" not in d for d in model["dimensions"])


def test_json_fills_parquet_nulls_and_parquet_wins(fake_reader):
    reader = fake_reader(
        {
            "dbt.models": [
                {"unique_id": "model.p.a", "name": "a", "description": "", "alias": "from_pq"}
            ]
        }
    )
    json_manifest = {
        "nodes": {
            "model.p.a": {
                "description": "from json",
                "alias": "from_json",
                "depends_on": {"macros": ["macro.p.m"]},
            }
        },
        "metadata": {"project_name": "from json"},
    }
    node = synth.build_manifest(reader, json_manifest)["nodes"]["model.p.a"]
    assert node["description"] == "from json"
    assert node["alias"] == "from_pq"
    assert node["depends_on"]["macros"] == ["macro.p.m"]
    assert node["fqn"] == ["p", "a"]


def test_unit_test_checksum_object_from_json_is_flattened(fake_reader):
    reader = fake_reader({"dbt.unit_tests": [{"unique_id": "unit_test.p.m.t", "name": "t"}]})
    json_manifest = {
        "unit_tests": {"unit_test.p.m.t": {"checksum": {"name": "sha", "checksum": "abc"}}}
    }
    unit = synth.build_manifest(reader, json_manifest)["unit_tests"]["unit_test.p.m.t"]
    assert unit["checksum"] == "abc"


def test_remaining_resource_kinds(fake_reader):
    reader = fake_reader(
        {
            "dbt.snapshots": [{"unique_id": "snapshot.p.s", "name": "s", "group": "g"}],
            "dbt.exposures": [
                {
                    "unique_id": "exposure.p.e",
                    "name": "e",
                    "exposure_type": "dashboard",
                    "owner_name": "Ann",
                }
            ],
            "dbt.groups": [{"unique_id": "group.p.g", "name": "g", "owner_email": "a@b.c"}],
            "dbt.macros": [
                {"unique_id": "macro.p.m", "name": "m", "arguments": '[{"name": "x"}]'},
                {"unique_id": "macro.p.n", "name": "n", "arguments": "not json"},
            ],
            "dbt.docs_blocks": [{"unique_id": "doc.p.d", "name": "d", "content": "hi"}],
            "dbt.edges": [
                {"parent_unique_id": "macro.p.m", "child_unique_id": "macro.p.n"},
                {"parent_unique_id": "snapshot.p.s", "child_unique_id": "exposure.p.e"},
            ],
            "dbt.project": [{"dbt_version": "2.0.0", "quoting": '{"schema": true}'}],
        }
    )
    manifest = synth.build_manifest(reader)
    assert manifest["exposures"]["exposure.p.e"]["owner"] == {"name": "Ann"}
    assert manifest["groups"]["group.p.g"]["owner"] == {"email": "a@b.c"}
    assert manifest["group_map"] == {"g": ["snapshot.p.s"]}
    assert manifest["macros"]["macro.p.m"]["arguments"] == [{"name": "x"}]
    assert "arguments" not in manifest["macros"]["macro.p.n"]
    assert manifest["docs"]["doc.p.d"]["block_contents"] == "hi"
    assert manifest["child_map"]["snapshot.p.s"] == ["exposure.p.e"]
    assert manifest["metadata"]["quoting"] == {"schema": True}


def test_json_helpers_pass_through_non_json():
    assert synth._json('"{\\"a\\": 1}"') == {"a": 1}
    assert synth._json("plain") == "plain"
    assert synth._json(None) is None


def _catalog_rows():
    return {
        "dbt.models": [
            {"unique_id": "model.p.a", "name": "a", "schema_name": "s", "materialized": "view"}
        ],
        "dbt.sources": [{"unique_id": "source.p.src.t", "name": "t", "identifier": "t_id"}],
        "dbt.node_columns": [
            {
                "node_unique_id": "model.p.a",
                "column_name": "Both",
                "column_index": 0,
                "data_type_actual": "actual",
                "data_type_inferred": "inferred",
            },
            {
                "node_unique_id": "model.p.a",
                "column_name": "declared",
                "column_index": 1,
                "data_type_declared": "decl",
                "data_type_inferred": "inferred",
            },
            {"node_unique_id": "model.p.a", "column_name": "bare", "column_index": 2},
            {"node_unique_id": "source.p.src.t", "column_name": "c", "data_type_inferred": "Utf8"},
            {"node_unique_id": "model.p.orphan", "column_name": "x"},
        ],
    }


def test_catalog_type_precedence(fake_reader):
    json_catalog = {
        "nodes": {
            "model.p.a": {"columns": {"BOTH": {"type": "NUMBER"}}, "stats": {"rows": {"value": 1}}},
            "model.p.json_only": {"columns": {}},
        },
        "sources": {"source.p.other": {}},
    }
    catalog = synth.build_catalog(fake_reader(_catalog_rows()), json_catalog)
    columns = catalog["nodes"]["model.p.a"]["columns"]
    assert columns["Both"]["type"] == "NUMBER"
    assert columns["declared"]["type"] == "decl"
    assert columns["bare"]["type"] == ""
    assert catalog["nodes"]["model.p.a"]["stats"] == {"rows": {"value": 1}}
    assert catalog["nodes"]["model.p.a"]["metadata"]["type"] == "view"
    assert "model.p.json_only" in catalog["nodes"]
    assert "source.p.other" in catalog["sources"]
    assert catalog["sources"]["source.p.src.t"]["columns"]["c"]["type"] == "Utf8"
    assert catalog["sources"]["source.p.src.t"]["metadata"]["name"] == "t_id"
    assert "model.p.orphan" not in catalog["nodes"]


def test_catalog_prefers_actual_over_inferred(fake_reader):
    catalog = synth.build_catalog(fake_reader(_catalog_rows()))
    assert catalog["nodes"]["model.p.a"]["columns"]["Both"]["type"] == "actual"
    assert catalog["metadata"]["dbt_schema_version"] == synth.CATALOG_SCHEMA


def _run_tables():
    return {
        "dbt_rt.invocations": [
            {
                "invocation_id": "old",
                "generated_at": datetime(2020, 1, 1, tzinfo=timezone.utc),
                "dbt_version": "2.0.0",
            },
            {
                "invocation_id": "build",
                "generated_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
                "elapsed_time": 2.5,
            },
            {"invocation_id": "compile", "generated_at": None},
        ],
        "dbt_rt.run_results": [
            {"unique_id": "model.p.a", "invocation_id": "build", "status": "success"},
            {
                "unique_id": "test.p.t",
                "invocation_id": "build",
                "status": "pass",
                "timing": '[{"name": "execute"}]',
                "execution_time": 1.0,
            },
            {"unique_id": "model.p.a", "invocation_id": "compile", "status": "success"},
            {"unique_id": "test.p.t", "invocation_id": "old", "status": "fail"},
        ],
    }


def test_run_results_use_latest_invocation_with_tests(fake_reader):
    json_run_results = {"results": [{"unique_id": "test.p.t", "message": "from json"}]}
    run_results = synth.build_run_results(fake_reader(_run_tables()), json_run_results)
    assert {r["unique_id"] for r in run_results["results"]} == {"model.p.a", "test.p.t"}
    test = next(r for r in run_results["results"] if r["unique_id"] == "test.p.t")
    assert test["message"] == "from json"
    assert test["timing"] == [{"name": "execute"}]
    assert run_results["metadata"]["invocation_id"] == "build"
    assert run_results["metadata"]["dbt_schema_version"] == synth.RUN_RESULTS_SCHEMA


def test_run_results_generated_at_is_isoformat(fake_reader):
    run_results = synth.build_run_results(fake_reader(_run_tables()))
    assert run_results["metadata"]["invocation_id"] == "build"
    assert run_results["metadata"]["generated_at"].startswith("2026-01-02")
    assert run_results["elapsed_time"] == 2.5


def test_run_results_fall_back_to_json_without_tests(fake_reader):
    fallback = {"results": []}
    assert synth.build_run_results(fake_reader({}), fallback) is fallback
    assert synth.build_run_results(fake_reader({})) is None


def _lineage_row(parent, column, evolution):
    return {
        "child_node_unique_id": "model.p.b",
        "child_column_name": "x",
        "parent_node_unique_id": parent,
        "parent_column_name": column,
        "evolution": evolution,
    }


def test_column_lineage_keeps_value_sources_sorted_and_unique(fake_reader):
    reader = fake_reader(
        {
            "dbt.column_lineage": [
                _lineage_row("model.p.c", "z", "mod"),
                _lineage_row("model.p.a", "y", "copy"),
                _lineage_row("model.p.a", "y", "copy"),
                _lineage_row("model.p.a", "join_key", "scan"),
                _lineage_row("model.p.d", "w", None),
            ]
        }
    )
    assert synth.column_lineage(reader) == {
        "model.p.b.x": [
            {"node": "model.p.a", "column": "y"},
            {"node": "model.p.c", "column": "z"},
            {"node": "model.p.d", "column": "w"},
        ]
    }


def test_column_lineage_of_only_scans_is_empty(fake_reader):
    reader = fake_reader({"dbt.column_lineage": [_lineage_row("model.p.a", "k", "scan")]})
    assert synth.column_lineage(reader) == {}


def test_staged_artifacts_are_json_serializable(v2_parquet_only):
    reader = _reader(v2_parquet_only)
    json.dumps(synth.build_manifest(reader), default=str)


def test_run_results_without_generated_at_use_now(fake_reader):
    tables = {
        "dbt_rt.invocations": [{"invocation_id": "i"}],
        "dbt_rt.run_results": [{"unique_id": "test.p.t", "invocation_id": "i", "status": "pass"}],
    }
    assert synth.build_run_results(fake_reader(tables))["metadata"]["generated_at"]
