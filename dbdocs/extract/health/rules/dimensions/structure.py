"""Structure — naming-convention and directory-layout rules.

Each rule is ``(graph) -> list[dict]``; see ``dbdocs.extract.health.rules``
for the shared finding shape and the registry that assembles these.
"""

from typing import Any

from dbdocs.extract.health.rules.base import LAYER_PREFIXES, finding

# ``ManifestGraph`` annotations are strings (forward ref) to avoid a circular
# import (rules ← graph ← analyzer); resolved lazily by the type checker only.
ManifestGraph = Any


def model_naming_conventions(graph: "ManifestGraph") -> "list[dict]":
    """Models whose name lacks the prefix expected for their layer."""
    out = []
    for model in graph.models:
        layer = graph.layer(model)
        prefixes = LAYER_PREFIXES.get(layer)
        if not prefixes:
            continue
        name = str(getattr(model, "name", "") or "")
        if not name.startswith(prefixes):
            expected = "/".join(prefixes)
            out.append(
                finding(
                    "model_naming_conventions",
                    "structure",
                    model.unique_id,
                    "model",
                    f"{layer} model '{name}' should be prefixed {expected}.",
                )
            )
    return out


def model_directories(graph: "ManifestGraph") -> "list[dict]":
    """Models not in a directory matching their layer."""
    out = []
    for model in graph.models:
        layer = graph.layer(model)
        if layer == "other":
            continue
        path = str(getattr(model, "path", "") or "")
        if layer not in path.split("/"):
            out.append(
                finding(
                    "model_directories",
                    "structure",
                    model.unique_id,
                    "model",
                    f"{layer} model is not under a '{layer}/' directory.",
                )
            )
    return out


def test_directories(graph: "ManifestGraph") -> "list[dict]":
    """Singular (custom SQL) tests not stored under a ``tests/`` directory."""
    out = []
    for test in graph.singular_tests:
        path = str(getattr(test, "original_file_path", "") or getattr(test, "path", "") or "")
        if "tests" not in path.split("/"):
            out.append(
                finding(
                    "test_directories",
                    "structure",
                    test.unique_id,
                    "test",
                    "Singular test is not under a 'tests/' directory.",
                )
            )
    return out


def source_directories(graph: "ManifestGraph") -> "list[dict]":
    """Source YAML not under a staging/ directory."""
    out = []
    seen = set()
    for src in graph.sources:
        path = str(getattr(src, "path", "") or "")
        if path in seen:
            continue
        seen.add(path)
        if "staging" not in path.split("/"):
            out.append(
                finding(
                    "source_directories",
                    "structure",
                    src.unique_id,
                    "source",
                    "Source definition is not under a 'staging/' directory.",
                )
            )
    return out
