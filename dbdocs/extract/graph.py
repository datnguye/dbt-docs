"""Node-level lineage (the DAG) from a dbt manifest.

``LineageGraph`` turns the manifest's ``parent_map`` (falling back to per-node
``depends_on.nodes``) into directed parent→child edges plus adjacency maps,
restricted to the nodes the SPA actually surfaces (models/seeds/snapshots/
sources) so test/macro dependencies don't dangle. The result feeds the
interactive DAG view.
"""

from typing import Any

from dbdocs.core.artifacts import NODE_PREFIXES


class LineageGraph:
    """The project lineage as ``{edges, parents, children}`` over surfaced nodes."""

    def __init__(self, manifest: Any, node_ids: "set | None" = None) -> None:
        self.manifest = manifest
        #: Restrict edges to these ids. Defaults to models/seeds/snapshots +
        #: sources derived from the manifest, matching ``nodes.build_nodes``.
        self.node_ids = node_ids if node_ids is not None else self._default_node_ids()

    def _default_node_ids(self) -> set:
        ids = {
            uid
            for uid in (getattr(self.manifest, "nodes", {}) or {})
            if str(uid).startswith(NODE_PREFIXES)
        }
        ids.update(getattr(self.manifest, "sources", {}) or {})
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
        return (getattr(self.manifest, "nodes", {}) or {}).get(unique_id)
