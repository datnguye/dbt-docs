"""Governance — contract and model-access rules.

Each rule is ``(graph) -> list[dict]``; see ``dbdocs.extract.health.rules``
for the shared finding shape and the registry that assembles these.
"""

from typing import Any

from dbdocs.extract.health.rules.base import finding

# ``ManifestGraph`` annotations are strings (forward ref) to avoid a circular
# import (rules ← graph ← analyzer); resolved lazily by the type checker only.
ManifestGraph = Any


def public_models_without_contracts(graph: "ManifestGraph") -> "list[dict]":
    """Models with access=public but no enforced contract."""
    out = []
    for model in graph.models:
        if graph.access(model) == "public" and not graph.contract_enforced(model):
            out.append(
                finding(
                    "public_models_without_contracts",
                    "governance",
                    model.unique_id,
                    "model",
                    "Public model has no enforced contract.",
                )
            )
    return out


def undocumented_public_models(graph: "ManifestGraph") -> "list[dict]":
    """Public models with no description."""
    out = []
    for model in graph.models:
        if (
            graph.access(model) == "public"
            and not str(getattr(model, "description", "") or "").strip()
        ):
            out.append(
                finding(
                    "undocumented_public_models",
                    "governance",
                    model.unique_id,
                    "model",
                    "Public model has no description.",
                )
            )
    return out


def exposures_dependent_on_private_models(graph: "ManifestGraph") -> "list[dict]":
    """Exposures depending on a model whose access is not public."""
    out = []
    for exposure in graph.exposures:
        for parent in graph.parents(exposure.unique_id):
            pnode = graph.node(parent)
            is_private_model = (
                pnode is not None
                and pnode.unique_id.startswith("model.")
                and graph.access(pnode) != "public"
            )
            if is_private_model:
                out.append(
                    finding(
                        "exposures_dependent_on_private_models",
                        "governance",
                        exposure.unique_id,
                        "exposure",
                        "Exposure depends on a non-public model.",
                    )
                )
                break
    return out
