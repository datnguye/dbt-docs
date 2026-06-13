"""Performance — materialization and view-chain rules.

Each rule is ``(graph) -> list[dict]``; see ``dbdocs.extract.health.rules``
for the shared finding shape and the registry that assembles these.
"""

from typing import Any

from dbdocs.extract.health.rules.base import NON_PHYSICAL, finding

# ``ManifestGraph`` annotations are strings (forward ref) to avoid a circular
# import (rules ← graph ← analyzer); resolved lazily by the type checker only.
ManifestGraph = Any


def chained_view_dependencies(graph: "ManifestGraph") -> "list[dict]":
    """Models at the end of a chain of >= the ``chained_view_dependencies`` threshold."""
    limit = graph.threshold("chained_view_dependencies")
    out = []
    for model in graph.models:
        if graph.materialization(model) not in NON_PHYSICAL:
            continue
        depth = graph.non_physical_chain_depth(model.unique_id)
        if depth >= limit:
            out.append(
                finding(
                    "chained_view_dependencies",
                    "performance",
                    model.unique_id,
                    "model",
                    f"At the end of a {depth}-deep view/ephemeral chain — materialize as a table.",
                )
            )
    return out


def exposure_parents_materializations(graph: "ManifestGraph") -> "list[dict]":
    """Exposures depending on a source, or a model not materialized table/incremental."""
    out = []
    for exposure in graph.exposures:
        for parent in graph.parents(exposure.unique_id):
            if parent.startswith("source."):
                out.append(
                    finding(
                        "exposure_parents_materializations",
                        "performance",
                        exposure.unique_id,
                        "exposure",
                        "Exposure depends directly on a source — route through a model.",
                    )
                )
                break
            pnode = graph.node(parent)
            if pnode is not None and graph.materialization(pnode) not in ("table", "incremental"):
                out.append(
                    finding(
                        "exposure_parents_materializations",
                        "performance",
                        exposure.unique_id,
                        "exposure",
                        "Exposure depends on a non-table/incremental model.",
                    )
                )
                break
    return out
