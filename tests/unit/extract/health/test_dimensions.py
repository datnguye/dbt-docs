"""Tests for dbdocs.extract.health.dimensions (ManifestGraph + DimensionAnalyzer)."""

from types import SimpleNamespace

import pytest

from dbdocs.core.artifacts import load_artifacts
from dbdocs.extract.health.dimensions import DimensionAnalyzer, ManifestGraph

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_ALL_DIMENSIONS = {"testing", "modeling", "documentation", "structure", "performance", "governance"}


@pytest.fixture
def jaffle_manifest():
    manifest, _ = load_artifacts("tests/fixtures/jaffle_shop")
    return manifest


def _mk_node(uid, parents=None, **kw):
    depends_on = SimpleNamespace(nodes=list(parents or []))
    return SimpleNamespace(unique_id=uid, depends_on=depends_on, **kw)


def _mk_manifest(nodes=None, sources=None, exposures=None):
    return SimpleNamespace(
        nodes={n.unique_id: n for n in (nodes or [])},
        sources={s.unique_id: s for s in (sources or [])},
        exposures={e.unique_id: e for e in (exposures or [])},
    )


# ---------------------------------------------------------------------------
# ManifestGraph: adjacency
# ---------------------------------------------------------------------------


def test_graph_adjacency_parents_and_children():
    a = _mk_node("model.p.a")
    b = _mk_node("model.p.b", parents=["model.p.a"])
    g = ManifestGraph(_mk_manifest(nodes=[a, b]))
    assert g.parents("model.p.b") == ["model.p.a"]
    assert g.children("model.p.a") == ["model.p.b"]
    assert g.parents("model.p.a") == []


def test_graph_handles_none_manifest():
    g = ManifestGraph(None)
    assert g.models == []
    assert g.sources == []
    assert g.parents("anything") == []


def test_graph_skips_node_with_empty_unique_id():
    # A malformed node carrying no unique_id is skipped during adjacency build.
    good = _mk_node("model.p.a")
    bad = _mk_node("", parents=["model.p.a"])
    manifest = SimpleNamespace(nodes={"model.p.a": good, "": bad}, sources={}, exposures={})
    g = ManifestGraph(manifest)
    assert g.parents("model.p.a") == []
    assert g.children("model.p.a") == []  # the bad edge was not indexed


def test_graph_node_lookup_model_and_source():
    m = _mk_node("model.p.a")
    s = _mk_node("source.p.s.raw")
    g = ManifestGraph(_mk_manifest(nodes=[m], sources=[s]))
    assert g.node("model.p.a") is m
    assert g.node("source.p.s.raw") is s
    assert g.node("missing") is None


# ---------------------------------------------------------------------------
# ManifestGraph: metadata accessors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fqn, expected",
    [
        (["pkg", "staging", "stg_x"], "staging"),
        (["pkg", "intermediate", "int_x"], "intermediate"),
        (["pkg", "marts", "fct_x"], "marts"),
        (["pkg", "stg", "x"], "staging"),
        (["pkg", "int", "x"], "intermediate"),
        (["pkg", "mart", "x"], "marts"),
        (["pkg", "x"], "other"),
    ],
)
def test_graph_layer(fqn, expected):
    node = SimpleNamespace(fqn=fqn)
    assert ManifestGraph.layer(node) == expected


def test_graph_materialization_from_config():
    node = SimpleNamespace(config=SimpleNamespace(materialized="Table"))
    assert ManifestGraph.materialization(node) == "table"


def test_graph_materialization_missing():
    assert ManifestGraph.materialization(SimpleNamespace(config=None)) == ""


def test_graph_access_default_protected():
    assert ManifestGraph.access(SimpleNamespace(config=None)) == "protected"


def test_graph_access_from_config():
    node = SimpleNamespace(config=SimpleNamespace(access="Public"))
    assert ManifestGraph.access(node) == "public"


def test_graph_contract_enforced():
    node = SimpleNamespace(contract=SimpleNamespace(enforced=True))
    assert ManifestGraph.contract_enforced(node) is True
    assert ManifestGraph.contract_enforced(SimpleNamespace(contract=None)) is False


def test_graph_tests_for():
    test_node = SimpleNamespace(
        attached_node="model.p.a",
        test_metadata=SimpleNamespace(name="unique"),
        depends_on=SimpleNamespace(nodes=[]),
    )
    test_node.unique_id = "test.p.unique_a_id"
    g = ManifestGraph(_mk_manifest(nodes=[_mk_node("model.p.a"), test_node]))
    assert g.tests_for("model.p.a") == {"unique"}
    assert g.tests_for("model.p.b") == set()


def test_graph_singular_test_has_singular_type():
    test_node = SimpleNamespace(
        attached_node="model.p.a", test_metadata=None, depends_on=SimpleNamespace(nodes=[])
    )
    test_node.unique_id = "test.p.assert_thing"
    g = ManifestGraph(_mk_manifest(nodes=[test_node]))
    assert g.tests_for("model.p.a") == {"singular"}


# ---------------------------------------------------------------------------
# ManifestGraph: non-physical chain depth
# ---------------------------------------------------------------------------


def test_chain_depth_counts_view_chain():
    # raw(source) → v1(view) → v2(view) → v3(view): v3's chain depth is 3.
    s = _mk_node("source.p.s.raw")
    v1 = SimpleNamespace(
        unique_id="model.p.v1",
        depends_on=SimpleNamespace(nodes=["source.p.s.raw"]),
        config=SimpleNamespace(materialized="view"),
    )
    v2 = SimpleNamespace(
        unique_id="model.p.v2",
        depends_on=SimpleNamespace(nodes=["model.p.v1"]),
        config=SimpleNamespace(materialized="view"),
    )
    v3 = SimpleNamespace(
        unique_id="model.p.v3",
        depends_on=SimpleNamespace(nodes=["model.p.v2"]),
        config=SimpleNamespace(materialized="view"),
    )
    g = ManifestGraph(_mk_manifest(nodes=[v1, v2, v3], sources=[s]))
    assert g.non_physical_chain_depth("model.p.v3") == 3
    assert g.non_physical_chain_depth("model.p.v1") == 1


def test_chain_depth_table_breaks_chain():
    t = SimpleNamespace(
        unique_id="model.p.t",
        depends_on=SimpleNamespace(nodes=[]),
        config=SimpleNamespace(materialized="table"),
    )
    v = SimpleNamespace(
        unique_id="model.p.v",
        depends_on=SimpleNamespace(nodes=["model.p.t"]),
        config=SimpleNamespace(materialized="view"),
    )
    g = ManifestGraph(_mk_manifest(nodes=[t, v]))
    # The view itself counts (1); its table parent stops the chain.
    assert g.non_physical_chain_depth("model.p.v") == 1


def test_chain_depth_cycle_guard():
    # Pathological self-cycle must not recurse forever.
    v = SimpleNamespace(
        unique_id="model.p.v",
        depends_on=SimpleNamespace(nodes=["model.p.v"]),
        config=SimpleNamespace(materialized="view"),
    )
    g = ManifestGraph(_mk_manifest(nodes=[v]))
    assert g.non_physical_chain_depth("model.p.v") == 1


def test_chain_depth_multi_node_cycle_guard():
    # A 3-node cycle of views must terminate (the iterative walk treats an
    # in-progress ancestor as a chain stop).
    nodes = []
    for i in range(3):
        nodes.append(
            SimpleNamespace(
                unique_id=f"model.p.c{i}",
                depends_on=SimpleNamespace(nodes=[f"model.p.c{(i + 1) % 3}"]),
                config=SimpleNamespace(materialized="view"),
            )
        )
    g = ManifestGraph(_mk_manifest(nodes=nodes))
    # Must terminate (the in-progress ancestor breaks the cycle). The depth is the
    # finite acyclic run from the entry node — bounded by the cycle length, never
    # infinite.
    depth = g.non_physical_chain_depth("model.p.c0")
    assert 1 <= depth <= 3


def test_chain_depth_deep_chain_is_iterative():
    # A chain far deeper than Python's recursion limit must compute, not crash.
    depth = 2500  # > sys.getrecursionlimit() default (1000)
    nodes = [
        SimpleNamespace(
            unique_id=f"model.p.v{i}",
            depends_on=SimpleNamespace(nodes=[f"model.p.v{i - 1}"] if i else []),
            config=SimpleNamespace(materialized="view"),
        )
        for i in range(depth)
    ]
    g = ManifestGraph(_mk_manifest(nodes=nodes))
    assert g.non_physical_chain_depth(f"model.p.v{depth - 1}") == depth


# ---------------------------------------------------------------------------
# DimensionAnalyzer
# ---------------------------------------------------------------------------


def test_analyze_returns_all_dimensions(jaffle_manifest):
    dims = DimensionAnalyzer(jaffle_manifest).analyze()
    assert set(dims) == _ALL_DIMENSIONS
    for d in dims.values():
        assert set(d) == {"issues", "checked", "findings"}
        assert d["issues"] == len(d["findings"])


def test_analyze_jaffle_known_findings(jaffle_manifest):
    dims = DimensionAnalyzer(jaffle_manifest).analyze()
    # jaffle_shop's marts intentionally drop fct_/dim_ prefixes → structure issues.
    assert dims["structure"]["issues"] > 0
    structure_rules = {f["rule"] for f in dims["structure"]["findings"]}
    assert "model_naming_conventions" in structure_rules
    # Every staging model only depends on sources → no staging-on-staging false positives.
    modeling_rules = {f["rule"] for f in dims["modeling"]["findings"]}
    assert "staging_dependent_on_staging" not in modeling_rules


def test_analyze_checked_denominators(jaffle_manifest):
    dims = DimensionAnalyzer(jaffle_manifest).analyze()
    # 15 models + 6 sources.
    assert dims["modeling"]["checked"] == 21
    assert dims["documentation"]["checked"] == 21
    assert dims["structure"]["checked"] == 21
    # model-centric dimensions: 15 models.
    assert dims["testing"]["checked"] == 15
    assert dims["performance"]["checked"] == 15
    assert dims["governance"]["checked"] == 15


def test_analyze_empty_manifest():
    dims = DimensionAnalyzer(None).analyze()
    assert set(dims) == _ALL_DIMENSIONS
    for d in dims.values():
        assert d["issues"] == 0
        assert d["findings"] == []


def test_analyze_rule_failure_is_fail_soft(monkeypatch):
    """A rule raising on a malformed node is caught, logged, and skipped."""
    msgs = []
    monkeypatch.setattr(
        "dbdocs.extract.health.dimensions.logger.warning", lambda m, *a: msgs.append(m % a)
    )

    def _boom(_graph):
        raise ValueError("bad node")

    monkeypatch.setattr(
        "dbdocs.extract.health.dimensions.DIMENSION_RULES",
        {"modeling": (_boom,)},
    )
    dims = DimensionAnalyzer(None).analyze()
    assert dims["modeling"]["issues"] == 0
    assert any("failed" in m for m in msgs)
