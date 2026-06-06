from types import SimpleNamespace

from dbdocs.extract.graph import LineageGraph


def test_edges_from_parent_map_drop_dangling_test(fake_manifest):
    result = LineageGraph(fake_manifest).build()
    edges = {(e["source"], e["target"]) for e in result["edges"]}
    assert ("model.shop.stg_customers", "model.shop.customers") in edges
    assert ("source.shop.ecom.raw_customers", "model.shop.stg_customers") in edges
    # The test node isn't a graph node, so its parent edge is dropped.
    assert all("test." not in s and "test." not in t for s, t in edges)


def test_parents_and_children_maps(fake_manifest):
    result = LineageGraph(fake_manifest).build()
    assert result["parents"]["model.shop.customers"] == ["model.shop.stg_customers"]
    assert result["children"]["model.shop.stg_customers"] == ["model.shop.customers"]


def test_falls_back_to_depends_on_without_parent_map():
    # No parent_map → the graph is built from each node's depends_on.nodes, which
    # exercises _lookup for both a model node and a source node.
    manifest = SimpleNamespace(
        nodes={
            "model.shop.a": SimpleNamespace(
                depends_on=SimpleNamespace(nodes=["seed.shop.s", "source.shop.raw"])
            ),
            "seed.shop.s": SimpleNamespace(depends_on=SimpleNamespace(nodes=[])),
        },
        sources={"source.shop.raw": SimpleNamespace(depends_on=SimpleNamespace(nodes=[]))},
    )
    result = LineageGraph(manifest).build()
    edges = {(e["source"], e["target"]) for e in result["edges"]}
    assert ("seed.shop.s", "model.shop.a") in edges
    assert ("source.shop.raw", "model.shop.a") in edges


def test_explicit_node_ids_restrict_graph(fake_manifest):
    only = {"model.shop.customers", "model.shop.stg_customers"}
    result = LineageGraph(fake_manifest, node_ids=only).build()
    nodes_in_edges = {e["source"] for e in result["edges"]} | {e["target"] for e in result["edges"]}
    assert nodes_in_edges <= only


def test_duplicate_edges_are_deduped():
    manifest = SimpleNamespace(
        nodes={
            "model.shop.a": SimpleNamespace(depends_on=SimpleNamespace(nodes=[])),
            "model.shop.b": SimpleNamespace(depends_on=SimpleNamespace(nodes=[])),
        },
        sources={},
        parent_map={"model.shop.b": ["model.shop.a", "model.shop.a"]},
    )
    result = LineageGraph(manifest).build()
    assert len(result["edges"]) == 1
