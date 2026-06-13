"""Tests for the health rule-engine plugin system (register_rule + config)."""

from types import SimpleNamespace

import pytest

from dbdocs.core.artifacts import load_artifacts
from dbdocs.extract.health import rules as R
from dbdocs.extract.health.dimensions import DimensionAnalyzer


@pytest.fixture
def jaffle_manifest():
    manifest, _ = load_artifacts("tests/fixtures/jaffle_shop")
    return manifest


def _custom_rule(graph):
    return [
        {"rule": "custom", "node": "model.x", "node_type": "model", "message": "hi", "docs_url": ""}
    ]


# ---------------------------------------------------------------------------
# register_rule
# ---------------------------------------------------------------------------


def test_register_rule_as_decorator():
    @R.register_rule("modeling")
    def my_rule(graph):
        return []

    assert my_rule in R.DIMENSION_RULES["modeling"]


def test_register_rule_direct_call():
    R.register_rule("modeling", _custom_rule)
    assert _custom_rule in R.DIMENSION_RULES["modeling"]


def test_register_rule_new_dimension():
    R.register_rule("brand_new", _custom_rule)
    assert R.DIMENSION_RULES["brand_new"] == [_custom_rule]


def test_register_rule_idempotent():
    R.register_rule("modeling", _custom_rule)
    R.register_rule("modeling", _custom_rule)
    assert R.DIMENSION_RULES["modeling"].count(_custom_rule) == 1


def test_reset_rules_drops_plugins():
    R.register_rule("modeling", _custom_rule)
    R.reset_rules()
    assert _custom_rule not in R.DIMENSION_RULES["modeling"]
    # Built-ins survive the reset.
    assert R.test_coverage in R.DIMENSION_RULES["testing"]


# ---------------------------------------------------------------------------
# load_rules_module
# ---------------------------------------------------------------------------


def test_load_rules_module_imports(monkeypatch):
    imported = {}
    monkeypatch.setattr(
        "dbdocs.extract.health.rules.registry.importlib.import_module",
        lambda path: imported.setdefault("path", path),
    )
    R.load_rules_module("my_pkg.my_rules")
    assert imported["path"] == "my_pkg.my_rules"


def test_load_rules_module_failure_is_logged(monkeypatch):
    msgs = []
    monkeypatch.setattr(
        "dbdocs.extract.health.rules.registry.logger.warning", lambda m, *a: msgs.append(m % a)
    )
    R.load_rules_module("does.not.exist.anywhere")
    assert any("could not be imported" in m for m in msgs)


# ---------------------------------------------------------------------------
# load_entry_point_rules
# ---------------------------------------------------------------------------


def _fake_ep(name, loader):
    return SimpleNamespace(name=name, load=loader)


def test_load_entry_point_rules_invokes_callable(monkeypatch):
    called = {"n": 0}

    def _loader():
        def _register():
            called["n"] += 1

        return _register

    monkeypatch.setattr(
        "dbdocs.extract.health.rules.registry.importlib.metadata.entry_points",
        lambda group: [_fake_ep("p", _loader)],
    )
    R.load_entry_point_rules()
    assert called["n"] == 1


def test_load_entry_point_rules_failure_is_logged(monkeypatch):
    msgs = []
    monkeypatch.setattr(
        "dbdocs.extract.health.rules.registry.logger.warning", lambda m, *a: msgs.append(m % a)
    )

    def _bad_loader():
        raise ImportError("nope")

    monkeypatch.setattr(
        "dbdocs.extract.health.rules.registry.importlib.metadata.entry_points",
        lambda group: [_fake_ep("bad", _bad_loader)],
    )
    R.load_entry_point_rules()
    assert any("failed to load" in m for m in msgs)


def test_load_entry_point_rules_non_callable_ignored(monkeypatch):
    monkeypatch.setattr(
        "dbdocs.extract.health.rules.registry.importlib.metadata.entry_points",
        lambda group: [_fake_ep("p", lambda: "not callable")],
    )
    R.load_entry_point_rules()  # must not raise


# ---------------------------------------------------------------------------
# DimensionAnalyzer config wiring
# ---------------------------------------------------------------------------


def test_analyzer_threshold_override(jaffle_manifest):
    default = DimensionAnalyzer(jaffle_manifest).analyze()["modeling"]["issues"]
    strict = DimensionAnalyzer(
        jaffle_manifest, config={"thresholds": {"model_fanout": 0}}
    ).analyze()["modeling"]["issues"]
    assert strict > default


def test_analyzer_disable_rule(jaffle_manifest):
    dims = DimensionAnalyzer(
        jaffle_manifest, config={"disable": ["model_naming_conventions"]}
    ).analyze()
    rules = {f["rule"] for f in dims["structure"]["findings"]}
    assert "model_naming_conventions" not in rules


def test_analyzer_disable_dimension(jaffle_manifest):
    dims = DimensionAnalyzer(
        jaffle_manifest, config={"disable_dimensions": ["governance"]}
    ).analyze()
    assert "governance" not in dims


def test_analyzer_loads_rules_module(jaffle_manifest, monkeypatch):
    loaded = {}
    monkeypatch.setattr(
        "dbdocs.extract.health.dimensions.load_rules_module",
        lambda path: loaded.setdefault("path", path),
    )
    DimensionAnalyzer(jaffle_manifest, config={"rules_module": "my.rules"})
    assert loaded["path"] == "my.rules"


def test_analyzer_ignores_non_dict_thresholds(jaffle_manifest):
    # A malformed thresholds value falls back to defaults rather than crashing.
    dims = DimensionAnalyzer(jaffle_manifest, config={"thresholds": "oops"}).analyze()
    assert dims["modeling"]["issues"] >= 0


def test_analyzer_custom_rule_surfaces(jaffle_manifest):
    R.register_rule("modeling", _custom_rule)
    dims = DimensionAnalyzer(jaffle_manifest).analyze()
    assert any(f["rule"] == "custom" for f in dims["modeling"]["findings"])


def test_analyzer_bad_plugin_is_fail_soft(jaffle_manifest, monkeypatch):
    msgs = []
    monkeypatch.setattr(
        "dbdocs.extract.health.dimensions.logger.warning", lambda m, *a: msgs.append(m % a)
    )

    @R.register_rule("modeling")
    def _boom(graph):
        raise ValueError("bad plugin")

    dims = DimensionAnalyzer(jaffle_manifest).analyze()
    assert any("failed" in m for m in msgs)
    # The other modeling rules still produced their findings.
    assert "modeling" in dims
