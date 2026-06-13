"""Documentation — model and source description coverage rules.

Each rule is ``(graph) -> list[dict]``; see ``dbdocs.extract.health.rules``
for the shared finding shape and the registry that assembles these.
"""

from typing import Any

from dbdocs.extract.health.rules.base import finding

# ``ManifestGraph`` annotations are strings (forward ref) to avoid a circular
# import (rules ← graph ← analyzer); resolved lazily by the type checker only.
ManifestGraph = Any


def undocumented_models(graph: "ManifestGraph") -> "list[dict]":
    """Models with no description."""
    out = []
    for model in graph.models:
        if not str(getattr(model, "description", "") or "").strip():
            out.append(
                finding(
                    "undocumented_models",
                    "documentation",
                    model.unique_id,
                    "model",
                    "No model-level description.",
                )
            )
    return out


def undocumented_sources(graph: "ManifestGraph") -> "list[dict]":
    """Sources whose source-level description is missing."""
    out = []
    seen = set()
    for src in graph.sources:
        source_name = str(getattr(src, "source_name", "") or "")
        if source_name in seen:
            continue
        # A source is documented at the source level via its source_description.
        desc = getattr(src, "source_description", None)
        if not str(desc or "").strip():
            seen.add(source_name)
            out.append(
                finding(
                    "undocumented_sources",
                    "documentation",
                    "source." + source_name if source_name else src.unique_id,
                    "source",
                    f"Source '{source_name or src.unique_id}' has no description.",
                )
            )
    return out


def undocumented_source_tables(graph: "ManifestGraph") -> "list[dict]":
    """Source tables (the individual relations) with no description."""
    out = []
    for src in graph.sources:
        if not str(getattr(src, "description", "") or "").strip():
            out.append(
                finding(
                    "undocumented_source_tables",
                    "documentation",
                    src.unique_id,
                    "source",
                    "Source table has no description.",
                )
            )
    return out
