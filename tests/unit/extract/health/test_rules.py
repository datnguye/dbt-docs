"""Tests for dbdocs.extract.health.rules (the manifest-derived DPE rules).

Each rule is driven against a tiny in-memory ``FakeGraph`` exposing the same
surface as ``ManifestGraph`` — so the rules are tested in isolation from manifest
parsing, and edge cases (thresholds, layers, access, materializations) are easy
to construct.
"""

from types import SimpleNamespace

import pytest

from dbdocs.extract.health import rules as R

# ---------------------------------------------------------------------------
# A minimal graph stub matching ManifestGraph's rule-facing surface.
# ---------------------------------------------------------------------------


def _node(unique_id, **kw):
    return SimpleNamespace(unique_id=unique_id, **kw)


class FakeGraph:
    """Hand-built graph: nodes + explicit parent edges + per-node attributes."""

    def __init__(
        self, models=None, sources=None, exposures=None, edges=None, attrs=None, thresholds=None
    ):
        self.models = models or []
        self.sources = sources or []
        self.exposures = exposures or []
        self._edges = edges or {}  # child_uid -> [parent_uid, ...]
        self._attrs = attrs or {}  # uid -> {layer, materialization, access, contract, tests}
        self._thresholds = {**R.DEFAULT_THRESHOLDS, **(thresholds or {})}
        self._by_id = {n.unique_id: n for n in (self.models + self.sources + self.exposures)}
        self._children = {}
        for child, parents in self._edges.items():
            for p in parents:
                self._children.setdefault(p, []).append(child)

    def threshold(self, name):
        return self._thresholds[name]

    def parents(self, uid):
        return self._edges.get(uid, [])

    def children(self, uid):
        return self._children.get(uid, [])

    def node(self, uid):
        return self._by_id.get(uid)

    def layer(self, model):
        return self._attrs.get(model.unique_id, {}).get("layer", "other")

    def materialization(self, node):
        return self._attrs.get(node.unique_id, {}).get("materialization", "view")

    def access(self, model):
        return self._attrs.get(model.unique_id, {}).get("access", "protected")

    def contract_enforced(self, model):
        return self._attrs.get(model.unique_id, {}).get("contract", False)

    def tests_for(self, uid):
        return self._attrs.get(uid, {}).get("tests", set())

    def non_physical_chain_depth(self, uid):
        return self._attrs.get(uid, {}).get("chain_depth", 0)


def _rules(findings):
    return [f["rule"] for f in findings]


def _nodes(findings):
    return [f["node"] for f in findings]


# ---------------------------------------------------------------------------
# Modeling
# ---------------------------------------------------------------------------


def test_direct_join_to_source_flags_mixed_parents():
    m = _node("model.p.mart")
    g = FakeGraph(models=[m], edges={"model.p.mart": ["model.p.stg", "source.p.s.raw"]})
    assert _nodes(R.direct_join_to_source(g)) == ["model.p.mart"]


def test_direct_join_to_source_ignores_pure_model_parents():
    m = _node("model.p.mart")
    g = FakeGraph(models=[m], edges={"model.p.mart": ["model.p.a", "model.p.b"]})
    assert R.direct_join_to_source(g) == []


def test_duplicate_sources_flags_same_relation():
    s1 = _node("source.p.s.raw", database="db", schema_="sc", name="raw")
    s2 = _node("source.p.t.raw", database="DB", schema_="SC", name="RAW")
    g = FakeGraph(sources=[s1, s2])
    assert set(_nodes(R.duplicate_sources(g))) == {"source.p.s.raw", "source.p.t.raw"}


def test_duplicate_sources_distinct_relations_ok():
    s1 = _node("source.p.s.a", database="db", schema_="sc", name="a")
    s2 = _node("source.p.s.b", database="db", schema_="sc", name="b")
    g = FakeGraph(sources=[s1, s2])
    assert R.duplicate_sources(g) == []


def test_model_fanout_threshold():
    parent = _node("model.p.hub")
    g = FakeGraph(
        models=[parent],
        edges={f"model.p.c{i}": ["model.p.hub"] for i in range(4)},  # 4 children > 3
    )
    assert _nodes(R.model_fanout(g)) == ["model.p.hub"]


def test_model_fanout_under_threshold_ok():
    parent = _node("model.p.hub")
    g = FakeGraph(models=[parent], edges={f"model.p.c{i}": ["model.p.hub"] for i in range(3)})
    assert R.model_fanout(g) == []


def test_multiple_sources_joined():
    m = _node("model.p.stg")
    g = FakeGraph(models=[m], edges={"model.p.stg": ["source.p.s.a", "source.p.s.b"]})
    assert _nodes(R.multiple_sources_joined(g)) == ["model.p.stg"]


def test_rejoining_of_upstream_concepts():
    # A → B, A → C, B → C, and B's only child is C.
    a, b, c = _node("model.p.a"), _node("model.p.b"), _node("model.p.c")
    g = FakeGraph(
        models=[a, b, c],
        edges={"model.p.b": ["model.p.a"], "model.p.c": ["model.p.a", "model.p.b"]},
    )
    assert _nodes(R.rejoining_of_upstream_concepts(g)) == ["model.p.b"]


def test_rejoining_ignored_when_b_has_multiple_children():
    a, b = _node("model.p.a"), _node("model.p.b")
    g = FakeGraph(
        models=[a, b],
        edges={"model.p.c1": ["model.p.b"], "model.p.c2": ["model.p.b"]},
    )
    assert R.rejoining_of_upstream_concepts(g) == []


def test_root_models_flags_parentless():
    m = _node("model.p.orphan")
    g = FakeGraph(models=[m], edges={})
    assert _nodes(R.root_models(g)) == ["model.p.orphan"]


def test_root_models_ok_with_parent():
    m = _node("model.p.child")
    g = FakeGraph(models=[m], edges={"model.p.child": ["source.p.s.raw"]})
    assert R.root_models(g) == []


def test_source_fanout():
    s = _node("source.p.s.raw")
    g = FakeGraph(
        sources=[s],
        edges={"model.p.a": ["source.p.s.raw"], "model.p.b": ["source.p.s.raw"]},
    )
    assert _nodes(R.source_fanout(g)) == ["source.p.s.raw"]


def test_staging_dependent_on_staging():
    a, b = _node("model.p.stg_a"), _node("model.p.stg_b")
    g = FakeGraph(
        models=[a, b],
        edges={"model.p.stg_b": ["model.p.stg_a"]},
        attrs={"model.p.stg_a": {"layer": "staging"}, "model.p.stg_b": {"layer": "staging"}},
    )
    assert _nodes(R.staging_dependent_on_staging(g)) == ["model.p.stg_b"]


def test_staging_dependent_on_staging_ignores_source_parent():
    # A staging model on a source (the normal case) must NOT be flagged, even
    # though sources live in a staging/ folder (so layer(source) == staging).
    b = _node("model.p.stg_b")
    g = FakeGraph(
        models=[b],
        sources=[_node("source.p.s.raw")],
        edges={"model.p.stg_b": ["source.p.s.raw"]},
        attrs={"model.p.stg_b": {"layer": "staging"}, "source.p.s.raw": {"layer": "staging"}},
    )
    assert R.staging_dependent_on_staging(g) == []


def test_staging_dependent_on_staging_ok_when_parent_is_other_layer():
    # A staging model with a model parent in a different layer is NOT flagged by
    # the staging-on-staging rule (the parent-loop falls through without a match).
    stg, other = _node("model.p.stg_x"), _node("model.p.misc")
    g = FakeGraph(
        models=[stg, other],
        edges={"model.p.stg_x": ["model.p.misc"]},
        attrs={"model.p.stg_x": {"layer": "staging"}, "model.p.misc": {"layer": "other"}},
    )
    assert R.staging_dependent_on_staging(g) == []


def test_staging_dependent_on_marts_or_intermediate():
    stg, mart = _node("model.p.stg_x"), _node("model.p.fct_y")
    g = FakeGraph(
        models=[stg, mart],
        edges={"model.p.stg_x": ["model.p.fct_y"]},
        attrs={"model.p.stg_x": {"layer": "staging"}, "model.p.fct_y": {"layer": "marts"}},
    )
    assert _nodes(R.staging_dependent_on_marts_or_intermediate(g)) == ["model.p.stg_x"]


def test_staging_dependent_on_marts_ok_when_parent_is_staging():
    # The marts/intermediate rule must NOT fire on a staging→staging parent edge.
    stg, stg2 = _node("model.p.stg_x"), _node("model.p.stg_y")
    g = FakeGraph(
        models=[stg, stg2],
        edges={"model.p.stg_x": ["model.p.stg_y"]},
        attrs={"model.p.stg_x": {"layer": "staging"}, "model.p.stg_y": {"layer": "staging"}},
    )
    assert R.staging_dependent_on_marts_or_intermediate(g) == []


def test_unused_sources():
    s = _node("source.p.s.orphan")
    g = FakeGraph(sources=[s], edges={})
    assert _nodes(R.unused_sources(g)) == ["source.p.s.orphan"]


def test_unused_sources_ok_when_referenced():
    s = _node("source.p.s.used")
    g = FakeGraph(sources=[s], edges={"model.p.stg": ["source.p.s.used"]})
    assert R.unused_sources(g) == []


def test_too_many_joins():
    m = _node("model.p.wide")
    g = FakeGraph(models=[m], edges={"model.p.wide": [f"model.p.u{i}" for i in range(7)]})
    assert _nodes(R.too_many_joins(g)) == ["model.p.wide"]


def test_too_many_joins_under_threshold_ok():
    m = _node("model.p.ok")
    g = FakeGraph(models=[m], edges={"model.p.ok": [f"model.p.u{i}" for i in range(6)]})
    assert R.too_many_joins(g) == []


# ---------------------------------------------------------------------------
# Testing (coverage)
# ---------------------------------------------------------------------------


def test_missing_primary_key_tests():
    m = _node("model.p.untested")
    g = FakeGraph(models=[m], attrs={"model.p.untested": {"tests": {"accepted_values"}}})
    assert _nodes(R.missing_primary_key_tests(g)) == ["model.p.untested"]


def test_missing_primary_key_tests_ok_with_unique():
    m = _node("model.p.tested")
    g = FakeGraph(models=[m], attrs={"model.p.tested": {"tests": {"unique"}}})
    assert R.missing_primary_key_tests(g) == []


def test_test_coverage_flags_untested():
    m = _node("model.p.bare")
    g = FakeGraph(models=[m], attrs={"model.p.bare": {"tests": set()}})
    assert _nodes(R.test_coverage(g)) == ["model.p.bare"]


def test_test_coverage_ok_with_any_test():
    m = _node("model.p.covered")
    g = FakeGraph(models=[m], attrs={"model.p.covered": {"tests": {"not_null"}}})
    assert R.test_coverage(g) == []


# ---------------------------------------------------------------------------
# Documentation
# ---------------------------------------------------------------------------


def test_undocumented_models():
    a = _node("model.p.a", description="")
    b = _node("model.p.b", description="documented")
    g = FakeGraph(models=[a, b])
    assert _nodes(R.undocumented_models(g)) == ["model.p.a"]


def test_undocumented_sources_dedupes_by_source_name():
    s1 = _node("source.p.ecom.a", source_name="ecom", source_description="")
    s2 = _node("source.p.ecom.b", source_name="ecom", source_description="")
    g = FakeGraph(sources=[s1, s2])
    # One finding per undocumented *source* (not per table).
    assert _nodes(R.undocumented_sources(g)) == ["source.ecom"]


def test_undocumented_sources_ok_when_described():
    s = _node("source.p.ecom.a", source_name="ecom", source_description="the shop")
    g = FakeGraph(sources=[s])
    assert R.undocumented_sources(g) == []


def test_undocumented_source_tables():
    s = _node("source.p.ecom.a", description="")
    g = FakeGraph(sources=[s])
    assert _nodes(R.undocumented_source_tables(g)) == ["source.p.ecom.a"]


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------


def test_model_naming_conventions_flags_bad_prefix():
    m = _node("model.p.orders", name="orders")
    g = FakeGraph(models=[m], attrs={"model.p.orders": {"layer": "staging"}})
    assert _nodes(R.model_naming_conventions(g)) == ["model.p.orders"]


def test_model_naming_conventions_ok_with_prefix():
    m = _node("model.p.stg_orders", name="stg_orders")
    g = FakeGraph(models=[m], attrs={"model.p.stg_orders": {"layer": "staging"}})
    assert R.model_naming_conventions(g) == []


def test_model_naming_conventions_skips_other_layer():
    m = _node("model.p.whatever", name="whatever")
    g = FakeGraph(models=[m], attrs={"model.p.whatever": {"layer": "other"}})
    assert R.model_naming_conventions(g) == []


def test_model_directories_flags_wrong_folder():
    m = _node("model.p.stg_orders", name="stg_orders", path="marts/stg_orders.sql")
    g = FakeGraph(models=[m], attrs={"model.p.stg_orders": {"layer": "staging"}})
    assert _nodes(R.model_directories(g)) == ["model.p.stg_orders"]


def test_model_directories_ok_in_right_folder():
    m = _node("model.p.stg_orders", name="stg_orders", path="staging/stg_orders.sql")
    g = FakeGraph(models=[m], attrs={"model.p.stg_orders": {"layer": "staging"}})
    assert R.model_directories(g) == []


def test_source_directories_flags_non_staging():
    s = _node("source.p.s.raw", path="models/raw/__sources.yml")
    g = FakeGraph(sources=[s])
    assert _nodes(R.source_directories(g)) == ["source.p.s.raw"]


def test_source_directories_ok_in_staging():
    s = _node("source.p.s.raw", path="models/staging/__sources.yml")
    g = FakeGraph(sources=[s])
    assert R.source_directories(g) == []


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------


def test_chained_view_dependencies():
    m = _node("model.p.deep")
    g = FakeGraph(
        models=[m],
        attrs={"model.p.deep": {"materialization": "view", "chain_depth": 4}},
    )
    assert _nodes(R.chained_view_dependencies(g)) == ["model.p.deep"]


def test_chained_view_dependencies_ok_when_table():
    m = _node("model.p.tbl")
    g = FakeGraph(models=[m], attrs={"model.p.tbl": {"materialization": "table", "chain_depth": 9}})
    assert R.chained_view_dependencies(g) == []


def test_chained_view_dependencies_ok_short_chain():
    m = _node("model.p.shallow")
    g = FakeGraph(
        models=[m], attrs={"model.p.shallow": {"materialization": "view", "chain_depth": 3}}
    )
    assert R.chained_view_dependencies(g) == []


def test_exposure_parents_materializations_source_parent():
    e = _node("exposure.p.dash")
    g = FakeGraph(exposures=[e], edges={"exposure.p.dash": ["source.p.s.raw"]})
    assert _nodes(R.exposure_parents_materializations(g)) == ["exposure.p.dash"]


def test_exposure_parents_materializations_non_table_model():
    e = _node("exposure.p.dash")
    m = _node("model.p.v")
    g = FakeGraph(
        exposures=[e],
        models=[m],
        edges={"exposure.p.dash": ["model.p.v"]},
        attrs={"model.p.v": {"materialization": "view"}},
    )
    assert _nodes(R.exposure_parents_materializations(g)) == ["exposure.p.dash"]


def test_exposure_parents_materializations_ok_on_table():
    e = _node("exposure.p.dash")
    m = _node("model.p.t")
    g = FakeGraph(
        exposures=[e],
        models=[m],
        edges={"exposure.p.dash": ["model.p.t"]},
        attrs={"model.p.t": {"materialization": "table"}},
    )
    assert R.exposure_parents_materializations(g) == []


# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------


def test_public_models_without_contracts():
    m = _node("model.p.api")
    g = FakeGraph(models=[m], attrs={"model.p.api": {"access": "public", "contract": False}})
    assert _nodes(R.public_models_without_contracts(g)) == ["model.p.api"]


def test_public_models_with_contract_ok():
    m = _node("model.p.api")
    g = FakeGraph(models=[m], attrs={"model.p.api": {"access": "public", "contract": True}})
    assert R.public_models_without_contracts(g) == []


def test_public_models_protected_ok():
    m = _node("model.p.internal")
    g = FakeGraph(
        models=[m], attrs={"model.p.internal": {"access": "protected", "contract": False}}
    )
    assert R.public_models_without_contracts(g) == []


def test_undocumented_public_models():
    m = _node("model.p.api", description="")
    g = FakeGraph(models=[m], attrs={"model.p.api": {"access": "public"}})
    assert _nodes(R.undocumented_public_models(g)) == ["model.p.api"]


def test_undocumented_public_models_ok_when_documented():
    m = _node("model.p.api", description="the api")
    g = FakeGraph(models=[m], attrs={"model.p.api": {"access": "public"}})
    assert R.undocumented_public_models(g) == []


def test_exposures_dependent_on_private_models():
    e = _node("exposure.p.dash")
    m = _node("model.p.private")
    g = FakeGraph(
        exposures=[e],
        models=[m],
        edges={"exposure.p.dash": ["model.p.private"]},
        attrs={"model.p.private": {"access": "protected"}},
    )
    assert _nodes(R.exposures_dependent_on_private_models(g)) == ["exposure.p.dash"]


def test_exposures_on_public_models_ok():
    e = _node("exposure.p.dash")
    m = _node("model.p.public")
    g = FakeGraph(
        exposures=[e],
        models=[m],
        edges={"exposure.p.dash": ["model.p.public"]},
        attrs={"model.p.public": {"access": "public"}},
    )
    assert R.exposures_dependent_on_private_models(g) == []


# ---------------------------------------------------------------------------
# Finding shape + docs URLs
# ---------------------------------------------------------------------------


def test_finding_shape_and_docs_url():
    m = _node("model.p.orphan")
    g = FakeGraph(models=[m], edges={})
    f = R.root_models(g)[0]
    assert set(f) == {"rule", "node", "node_type", "message", "docs_url"}
    assert f["docs_url"] == (
        "https://dbt-labs.github.io/dbt-project-evaluator/latest/rules/modeling/#root-models"
    )


def test_testing_docs_url_uses_testing_category():
    # DPE's testing rules live under /rules/testing/ (not /rules/tests/).
    m = _node("model.p.bare")
    g = FakeGraph(models=[m], attrs={"model.p.bare": {"tests": set()}})
    f = R.test_coverage(g)[0]
    assert f["docs_url"] == (
        "https://dbt-labs.github.io/dbt-project-evaluator/latest/rules/testing/#test-coverage"
    )


@pytest.mark.parametrize("dimension", list(R.DIMENSION_RULES))
def test_dimension_rules_are_callable(dimension):
    """Every registered rule is a callable returning a list on an empty graph."""
    for rule in R.DIMENSION_RULES[dimension]:
        assert rule(FakeGraph()) == []
