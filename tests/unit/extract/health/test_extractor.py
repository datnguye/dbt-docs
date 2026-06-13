"""Tests for dbdocs.extract.health (HealthCheckExtractor).

The extractor turns an ordinary ``run_results.json`` (no special dbt package)
into a categorized dbt-test health report: every ``test.*`` result is a finding,
bucketed by test type (not_null/unique → integrity, relationships → referential,
…). The test type / tested model / column come from the **manifest**, so the
end-to-end tests pair the committed ``run_results.json`` fixture with the
committed ``jaffle_shop`` manifest.
"""

import json
from types import SimpleNamespace

import pytest

from dbdocs.core.artifacts import load_artifacts
from dbdocs.extract.health.extractor import (
    TEST_CATEGORIES,
    HealthCheckExtractor,
    _infer_test_type,
    _is_test_result,
    _is_unit_test,
    _short_name,
    _status_value,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def jaffle_manifest():
    """The dbterd-parsed manifest for the committed jaffle_shop fixtures."""
    manifest, _ = load_artifacts("tests/fixtures/jaffle_shop")
    return manifest


def _test_result(unique_id, status="pass", failures=0, message=None):
    """A parsed-result-like object (mirrors artifact-parser's ``Result``)."""
    return SimpleNamespace(
        unique_id=unique_id,
        status=SimpleNamespace(value=status),
        failures=failures,
        message=message,
    )


def _manifest_node(test_type=None, column=None, attached=None):
    """A manifest test node stub exposing test_metadata / column / attached_node."""
    metadata = SimpleNamespace(name=test_type) if test_type is not None else None
    return SimpleNamespace(
        test_metadata=metadata,
        column_name=column,
        attached_node=attached,
    )


def _fake_manifest(nodes):
    return SimpleNamespace(nodes=nodes)


def _write_run_results(path, results):
    """Write a minimal but parser-valid run_results.json (v6 required fields)."""
    payload = {
        "metadata": {
            "dbt_schema_version": "https://schemas.getdbt.com/dbt/run-results/v6.json",
            "dbt_version": "1.11.0",
            "generated_at": "2024-01-15T10:00:00.000000Z",
            "invocation_id": "00000000-0000-0000-0000-000000000000",
            "env": {},
        },
        "results": [_full_result(r) for r in results],
        "elapsed_time": 1.0,
        "args": {},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _full_result(partial):
    """Fill the v6-required structural fields the extractor doesn't read."""
    base = {
        "status": "pass",
        "failures": 0,
        "message": None,
        "execution_time": 0.0,
        "thread_id": "Thread-1",
        "timing": [],
        "adapter_response": {},
        "compiled": True,
        "compiled_code": "",
        "relation_name": None,
    }
    base.update(partial)
    return base


# ---------------------------------------------------------------------------
# Unit: _is_test_result
# ---------------------------------------------------------------------------


def test_is_test_result_true_for_test():
    assert _is_test_result(_test_result("test.proj.not_null_orders_id.abc")) is True


def test_is_test_result_false_for_model():
    assert _is_test_result(_test_result("model.proj.orders")) is False


def test_is_test_result_true_for_unit_test():
    assert _is_test_result(_test_result("unit_test.proj.orders.test_totals")) is True


def test_is_test_result_missing_unique_id():
    assert _is_test_result(SimpleNamespace(unique_id=None)) is False


def test_is_unit_test():
    assert _is_unit_test("unit_test.proj.orders.test_totals") is True
    assert _is_unit_test("test.proj.not_null_orders_id.abc") is False


# ---------------------------------------------------------------------------
# Unit: _status_value
# ---------------------------------------------------------------------------


def test_status_value_unwraps_enum():
    assert _status_value(SimpleNamespace(value="warn")) == "warn"


def test_status_value_plain_string():
    assert _status_value("fail") == "fail"


def test_status_value_none_falls_back():
    assert _status_value(None) == "unknown"


# ---------------------------------------------------------------------------
# Unit: _short_name
# ---------------------------------------------------------------------------


def test_short_name_last_segment():
    assert _short_name("model.jaffle_shop.stg_orders") == "stg_orders"


def test_short_name_empty():
    assert _short_name("") == ""


# ---------------------------------------------------------------------------
# Unit: _infer_test_type (manifest-less fallback)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "unique_id, expected",
    [
        ("test.proj.not_null_orders_id.h", "not_null"),
        ("test.proj.unique_orders_id.h", "unique"),
        ("test.proj.relationships_orders_customer.h", "relationships"),
        # longest-match: relationships_where must beat relationships
        ("test.proj.relationships_where_orders_x.h", "relationships_where"),
        ("test.proj.accepted_values_orders_status.h", "accepted_values"),
        ("test.proj.expression_is_true_orders_x.h", "expression_is_true"),
        ("test.proj.some_singular_custom_test.h", ""),
    ],
)
def test_infer_test_type(unique_id, expected):
    assert _infer_test_type(unique_id) == expected


# ---------------------------------------------------------------------------
# Unit: TEST_CATEGORIES coverage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "test_type, expected_cat",
    [
        ("not_null", "integrity"),
        ("unique", "integrity"),
        ("unique_combination_of_columns", "integrity"),
        ("relationships", "referential"),
        ("accepted_values", "validity"),
        ("expression_is_true", "business_logic"),
        ("freshness", "freshness"),
    ],
)
def test_test_categories_mapping(test_type, expected_cat):
    assert TEST_CATEGORIES[test_type] == expected_cat


# ---------------------------------------------------------------------------
# Unit: _resolve_metadata (manifest-first, fallback)
# ---------------------------------------------------------------------------


def test_resolve_metadata_from_manifest():
    nodes = {
        "test.p.not_null_orders_id.h": _manifest_node(
            test_type="not_null", column="id", attached="model.p.orders"
        )
    }
    ext = HealthCheckExtractor("x.json", manifest=_fake_manifest(nodes))
    test_type, model, column = ext._resolve_metadata("test.p.not_null_orders_id.h")
    assert test_type == "not_null"
    assert model == "orders"
    assert column == "id"


def test_resolve_metadata_singular_test_has_empty_type():
    # A singular (custom SQL) test has no test_metadata.
    nodes = {"test.p.assert_something.h": _manifest_node(test_type=None)}
    ext = HealthCheckExtractor("x.json", manifest=_fake_manifest(nodes))
    test_type, model, column = ext._resolve_metadata("test.p.assert_something.h")
    assert test_type == ""
    assert model == ""


def test_resolve_metadata_falls_back_to_unique_id_when_no_manifest():
    ext = HealthCheckExtractor("x.json", manifest=None)
    test_type, model, column = ext._resolve_metadata("test.p.unique_orders_id.h")
    assert test_type == "unique"
    assert model == ""
    assert column == ""


# ---------------------------------------------------------------------------
# HealthCheckExtractor: composed shape (dimensions + testResults / note)
# ---------------------------------------------------------------------------


def test_extract_shape(run_results_path, jaffle_manifest):
    result = HealthCheckExtractor(run_results_path, manifest=jaffle_manifest).extract()
    assert result["enabled"] is True
    # The six manifest-derived dimensions are always present.
    assert set(result["dimensions"]) == {
        "testing",
        "modeling",
        "documentation",
        "structure",
        "performance",
        "governance",
    }
    # Per-test detail present when run_results.json is found.
    assert result["testResults"] is not None
    assert "note" not in result


def test_extract_test_results_summary(run_results_path, jaffle_manifest):
    tr = HealthCheckExtractor(run_results_path, manifest=jaffle_manifest).extract()["testResults"]
    summary = tr["summary"]
    # The fixture is a sanitized real jaffle_shop run: 29 data tests + 3 unit
    # tests = 32 (17 pass, 1 fail, 14 skipped — the skips are downstream of the
    # one failing test). Data + unit tests are tallied together.
    assert summary["total"] == 32
    assert summary["pass"] == 17
    assert summary["fail"] == 1
    assert summary["skipped"] == 14


def test_extract_test_results_categories(run_results_path, jaffle_manifest):
    tr = HealthCheckExtractor(run_results_path, manifest=jaffle_manifest).extract()["testResults"]
    assert set(tr["categories"].keys()) == {
        "integrity",
        "referential",
        "validity",
        "business_logic",
        "freshness",
        "other",
        "unit",
    }
    # Every fixture test maps to a known category — none fall to 'other'.
    assert tr["categories"]["other"] == []
    # Integrity holds not_null/unique; the finding has no redundant 'category' key.
    integrity = tr["categories"]["integrity"]
    assert {"not_null", "unique"} <= {f["test_type"] for f in integrity}
    assert all("category" not in f for f in integrity)
    assert all(f["kind"] == "data" for f in integrity)
    assert any(f["model"] and f["column"] for f in integrity)


def test_extract_unit_tests_categorized(tmp_path):
    """unit_test.* results become 'unit' findings with the model resolved from the uid."""
    path = tmp_path / "run_results.json"
    _write_run_results(
        path,
        [
            {"unique_id": "unit_test.proj.orders.test_totals", "status": "pass"},
            {
                "unique_id": "unit_test.proj.customers.test_segments",
                "status": "fail",
                "failures": 1,
            },
        ],
    )
    tr = HealthCheckExtractor(path).extract()["testResults"]
    unit = tr["categories"]["unit"]
    assert len(unit) == 2
    assert {u["kind"] for u in unit} == {"unit"}
    assert {u["model"] for u in unit} == {"orders", "customers"}
    assert {u["test_type"] for u in unit} == {"unit_test"}
    # Data and unit tests are tallied together in the summary.
    assert tr["summary"]["total"] == 2
    assert tr["summary"]["fail"] == 1


def test_extract_unit_test_model_from_manifest():
    """The unit test's model is read from manifest.unit_tests[*].model when present."""
    unit_node = SimpleNamespace(model="orders_renamed")
    manifest = SimpleNamespace(
        nodes={},
        unit_tests={"unit_test.proj.orders.test_x": unit_node},
    )
    ext = HealthCheckExtractor("x.json", manifest=manifest)
    assert ext._unit_test_model("unit_test.proj.orders.test_x") == "orders_renamed"


def test_extract_unit_test_model_uid_fallback():
    """Without a manifest entry, the model is the unit_test uid's third segment."""
    ext = HealthCheckExtractor("x.json", manifest=None)
    assert ext._unit_test_model("unit_test.proj.orders.test_x") == "orders"
    assert ext._unit_test_model("unit_test.proj") == ""


def test_extract_unit_test_manifest_node_without_model_falls_back():
    """A manifest unit_test node with an empty model falls back to the uid segment."""
    manifest = SimpleNamespace(
        nodes={},
        unit_tests={"unit_test.proj.orders.test_x": SimpleNamespace(model="")},
    )
    ext = HealthCheckExtractor("x.json", manifest=manifest)
    assert ext._unit_test_model("unit_test.proj.orders.test_x") == "orders"


def test_extract_dimensions_have_findings(run_results_path, jaffle_manifest):
    dims = HealthCheckExtractor(run_results_path, manifest=jaffle_manifest).extract()["dimensions"]
    # Structure flags jaffle's prefix-less marts; testing flags untested models.
    assert dims["structure"]["issues"] > 0
    assert dims["testing"]["issues"] > 0
    for d in dims.values():
        assert set(d) == {"issues", "checked", "findings"}


# ---------------------------------------------------------------------------
# HealthCheckExtractor: run_results absent → note, dimensions still present
# ---------------------------------------------------------------------------


def test_extract_missing_run_results_keeps_dimensions(tmp_path, jaffle_manifest):
    path = tmp_path / "run_results.json"  # never created
    result = HealthCheckExtractor(path, manifest=jaffle_manifest).extract()
    assert result["enabled"] is True
    # Dimensions still computed from the manifest.
    assert result["dimensions"]["structure"]["issues"] > 0
    # Test detail skipped, with a note naming the path.
    assert result["testResults"] is None
    assert str(path) in result["note"]


def _capture_warnings(monkeypatch):
    """Patch health.logger.warning and return the captured messages list."""
    msgs = []

    def _warn(msg, *a):
        msgs.append(msg % a)

    monkeypatch.setattr("dbdocs.extract.health.extractor.logger.warning", _warn)
    return msgs


def test_extract_missing_file_logs_warning(tmp_path, monkeypatch):
    msgs = _capture_warnings(monkeypatch)
    HealthCheckExtractor(tmp_path / "run_results.json").extract()
    assert any("not found" in m for m in msgs)


def test_extract_malformed_json_notes_skip(tmp_path):
    path = tmp_path / "run_results.json"
    path.write_text("not json {{{", encoding="utf-8")
    result = HealthCheckExtractor(path).extract()
    assert result["testResults"] is None
    assert "note" in result


def test_extract_malformed_json_logs_warning(tmp_path, monkeypatch):
    msgs = _capture_warnings(monkeypatch)
    path = tmp_path / "run_results.json"
    path.write_text("not json {{{", encoding="utf-8")
    HealthCheckExtractor(path).extract()
    assert any("parse" in m.lower() for m in msgs)


def test_extract_invalid_artifact_notes_skip(tmp_path):
    """Valid JSON that isn't a run_results artifact fails parser validation, fail-soft."""
    path = tmp_path / "run_results.json"
    path.write_text(json.dumps({"results": "oops"}), encoding="utf-8")
    result = HealthCheckExtractor(path).extract()
    assert result["testResults"] is None


def test_extract_invalid_artifact_logs_warning(tmp_path, monkeypatch):
    msgs = _capture_warnings(monkeypatch)
    path = tmp_path / "run_results.json"
    path.write_text(json.dumps({"not": "a run_results doc"}), encoding="utf-8")
    HealthCheckExtractor(path).extract()
    assert any("not a valid run_results" in m.lower() for m in msgs)


def test_extract_oserror_notes_skip(tmp_path, monkeypatch):
    """An OSError that is not FileNotFoundError (e.g. permission denied) is fail-soft."""
    msgs = _capture_warnings(monkeypatch)
    path = tmp_path / "run_results.json"
    path.write_text("{}", encoding="utf-8")

    def _raise(*a, **kw):
        raise PermissionError("denied")

    monkeypatch.setattr("pathlib.Path.read_text", _raise)
    result = HealthCheckExtractor(path).extract()
    assert result["testResults"] is None
    assert any("could not read" in m.lower() for m in msgs)


def test_extract_empty_results_list(tmp_path):
    path = tmp_path / "run_results.json"
    _write_run_results(path, [])
    result = HealthCheckExtractor(path).extract()
    assert result["enabled"] is True
    assert result["testResults"]["summary"]["total"] == 0


def test_extract_only_non_test_results(tmp_path):
    """A file with only model/seed results yields no test findings."""
    path = tmp_path / "run_results.json"
    _write_run_results(path, [{"unique_id": "model.proj.orders", "status": "success"}])
    result = HealthCheckExtractor(path).extract()
    assert result["testResults"]["summary"]["total"] == 0


def test_extract_unknown_test_type_lands_in_other(tmp_path):
    """A singular/custom test (no recognizable type, no manifest) buckets to 'other'."""
    path = tmp_path / "run_results.json"
    _write_run_results(path, [{"unique_id": "test.proj.assert_custom_thing.h", "status": "pass"}])
    tr = HealthCheckExtractor(path).extract()["testResults"]
    assert tr["summary"]["total"] == 1
    assert len(tr["categories"]["other"]) == 1
    assert tr["categories"]["other"][0]["test_type"] == "custom"


# ---------------------------------------------------------------------------
# Test-results summary counting
# ---------------------------------------------------------------------------


def test_summary_counts_all_statuses(tmp_path):
    path = tmp_path / "run_results.json"
    results = [
        {"unique_id": "test.p.not_null_a_id.h", "status": "fail", "failures": 2},
        {"unique_id": "test.p.unique_a_id.h", "status": "warn", "failures": 1},
        {"unique_id": "test.p.relationships_a_b.h", "status": "pass"},
        {"unique_id": "test.p.accepted_values_a_s.h", "status": "error"},
        {"unique_id": "test.p.expression_is_true_a_x.h", "status": "skipped"},
    ]
    _write_run_results(path, results)
    s = HealthCheckExtractor(path).extract()["testResults"]["summary"]
    assert s["fail"] == 1
    assert s["warn"] == 1
    assert s["pass"] == 1
    assert s["error"] == 1
    assert s["skipped"] == 1
    assert s["total"] == 5


def test_summary_unknown_status_counts_in_total_only():
    """An unrecognized status increments total but no specific bucket (defensive)."""
    finding = {"status": "mystery"}
    summary = HealthCheckExtractor._summary([finding])
    assert summary["total"] == 1
    assert summary["pass"] == 0


# ---------------------------------------------------------------------------
# HealthCheckExtractor: manifest argument accepted (no crash)
# ---------------------------------------------------------------------------


def test_extract_accepts_manifest_arg(run_results_path, fake_manifest):
    # fake_manifest has no real test nodes; extraction must still succeed,
    # falling back to unique_id inference per finding.
    result = HealthCheckExtractor(run_results_path, manifest=fake_manifest).extract()
    assert result["enabled"] is True
    assert result["testResults"]["summary"]["total"] == 32
