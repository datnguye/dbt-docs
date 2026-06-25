"""Node-level lineage (the DAG) from a dbt manifest.

``LineageGraph`` turns the manifest's ``parent_map`` (falling back to per-node
``depends_on.nodes``) into directed parent→child edges plus adjacency maps,
covering all surfaced resource types (models/seeds/snapshots/sources/analyses/
operations/metrics/semantic_models/saved_queries/unit_tests/exposures) so that
``dependsOn``/``referencedBy`` on new pages resolve correctly.

The visual DAG view filters by ``data-rtype`` in the graph bundle, so including
non-physical types in the lineage graph does not pollute the DAG display. Macros
and test nodes are still excluded — they are never surfaced as navigable pages.
"""

from typing import Any

from dbdocs.core.artifacts import CODE_ONLY_PREFIXES, COLLECTION_ATTRS, NODE_PREFIXES


class LineageGraph:
    """The project lineage as ``{edges, parents, children}`` over surfaced nodes."""

    def __init__(self, manifest: Any, node_ids: "set | None" = None) -> None:
        self.manifest = manifest
        self.node_ids = node_ids if node_ids is not None else self._default_node_ids()

    def _default_node_ids(self) -> set:
        ids = {
            uid
            for uid in (getattr(self.manifest, "nodes", {}) or {})
            if str(uid).startswith(NODE_PREFIXES + CODE_ONLY_PREFIXES)
        }
        ids.update(getattr(self.manifest, "sources", {}) or {})
        for attr in COLLECTION_ATTRS.values():
            ids.update(getattr(self.manifest, attr, None) or {})
        return ids

    def build(self) -> dict:
        """Return ``{"edges": [...], "parents": {...}, "children": {...}}``."""
        edges = self._edges()
        parents: dict = {n: [] for n in self.node_ids}
        children: dict = {n: [] for n in self.node_ids}
        for edge in edges:
            parents[edge["target"]].append(edge["source"])
            children[edge["source"]].append(edge["target"])
        return {"edges": edges, "parents": parents, "children": children}

    def _edges(self) -> list:
        seen = set()
        edges = []
        for child, raw_parents in self._parent_pairs():
            if child not in self.node_ids:
                continue
            for parent in raw_parents:
                if parent not in self.node_ids:
                    continue
                key = (parent, child)
                if key in seen:
                    continue
                seen.add(key)
                edges.append({"source": parent, "target": child})
        return edges

    def _parent_pairs(self):
        parent_map = getattr(self.manifest, "parent_map", None)
        if parent_map:
            yield from parent_map.items()
            return
        for unique_id in self.node_ids:
            entity = self._lookup(unique_id)
            depends_on = getattr(entity, "depends_on", None)
            yield unique_id, list(getattr(depends_on, "nodes", []) or [])

    def _lookup(self, unique_id: str) -> Any:
        if str(unique_id).startswith("source."):
            return (getattr(self.manifest, "sources", {}) or {}).get(unique_id)
        for prefix, attr in COLLECTION_ATTRS.items():
            if str(unique_id).startswith(prefix):
                return (getattr(self.manifest, attr, None) or {}).get(unique_id)
        return (getattr(self.manifest, "nodes", {}) or {}).get(unique_id)
