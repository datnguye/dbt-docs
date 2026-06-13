"""Testing — manifest-derived coverage (which models lack tests / a PK test).

The per-test pass/fail detail comes from run_results.json and is surfaced on
each model page by the SPA, not here.

Each rule is ``(graph) -> list[dict]``; see ``dbdocs.extract.health.rules``
for the shared finding shape and the registry that assembles these.
"""

from typing import Any

from dbdocs.extract.health.rules.base import finding

# ``ManifestGraph`` annotations are strings (forward ref) to avoid a circular
# import (rules ← graph ← analyzer); resolved lazily by the type checker only.
ManifestGraph = Any


def test_coverage(graph: "ManifestGraph") -> "list[dict]":
    """Models with no data tests at all (the untested set)."""
    out = []
    for model in graph.models:
        if not graph.tests_for(model.unique_id):
            out.append(
                finding(
                    "test_coverage",
                    "testing",
                    model.unique_id,
                    "model",
                    "Model has no data tests.",
                )
            )
    return out


def missing_primary_key_tests(graph: "ManifestGraph") -> "list[dict]":
    """Models with no ``unique``/``not_null`` test (no enforced primary key)."""
    out = []
    for model in graph.models:
        types = graph.tests_for(model.unique_id)
        if not ({"unique", "not_null", "unique_combination_of_columns"} & types):
            out.append(
                finding(
                    "missing_primary_key_tests",
                    "testing",
                    model.unique_id,
                    "model",
                    "No unique/not_null test — primary key is not enforced.",
                )
            )
    return out
