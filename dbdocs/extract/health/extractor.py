"""Health Check extractor — the six dbt-project-evaluator dimensions.

Builds a project-health report **from the static artifacts we already load** — no
extra dbt package, no warehouse. Two data sources feed it:

* The **manifest** drives the rule engine (:mod:`dbdocs.extract.health.dimensions`
  + :mod:`dbdocs.extract.health.rules`): all six DPE dimensions (testing,
  modeling, documentation, structure, performance, governance) as
  manifest-derived findings.
* An optional **``run_results.json``** adds the per-test pass/fail detail to the
  *testing* dimension (every ``test.*`` result categorized by test type). It is
  parsed with `artifact-parser <https://github.com/datnguye/artifact-parser>`_
  (``artifact_parser.dbt.parse_run_results``) — a versioned-Pydantic parser
  covering run-results schema v1–v6, so a status enum / field rename in a new dbt
  release surfaces as a caught error rather than a silent mis-read.

If ``run_results.json`` is **absent**, the test pass/fail detail is skipped and a
``note`` records the path it looked for — the manifest-derived dimensions
(including test *coverage*) still render. ``run_results.json`` itself doesn't
carry the test type; that lives in the manifest (``test_metadata.name``,
``column_name``, ``attached_node``), read when available and otherwise inferred
from the ``unique_id``.

**Fail-soft throughout**: a missing/malformed artifact never sinks ``generate``.
"""

import json
from pathlib import Path
from typing import Any

from artifact_parser.core.exceptions import ArtifactParserError
from artifact_parser.dbt import parse_run_results
from pydantic import ValidationError

from dbdocs.core.log import logger
from dbdocs.extract.health.dimensions import DimensionAnalyzer

# ---------------------------------------------------------------------------
# Test type → category mapping
# Generic dbt tests (and the common dbt_utils ones) are bucketed by what they
# assert. A test type we don't recognize lands in the honest "other" bucket
# rather than being silently misfiled.
# ---------------------------------------------------------------------------
# fmt: off
TEST_CATEGORIES: dict[str, str] = {
    # Integrity — keys & non-null guarantees
    "not_null":                         "integrity",
    "unique":                           "integrity",
    "unique_combination_of_columns":    "integrity",
    "not_null_proportion":              "integrity",
    "not_constant":                     "integrity",
    # Referential — relationships between models
    "relationships":                    "referential",
    "relationships_where":              "referential",
    "relationships_test":               "referential",
    # Validity — value-domain constraints
    "accepted_values":                  "validity",
    "accepted_range":                   "validity",
    "not_accepted_values":              "validity",
    "mutually_exclusive_ranges":        "validity",
    # Business logic — expressions & row-level assertions
    "expression_is_true":               "business_logic",
    "equal_rowcount":                   "business_logic",
    "fewer_rows_than":                  "business_logic",
    "cardinality_equality":             "business_logic",
    "at_least_one":                     "business_logic",
    # Freshness — source freshness
    "freshness":                        "freshness",
    "source_freshness":                 "freshness",
}
# fmt: on

# Category display order. "other" catches unrecognized data-test types; "unit"
# holds unit tests (a distinct dbt test family from data tests).
_CATEGORIES = (
    "integrity",
    "referential",
    "validity",
    "business_logic",
    "freshness",
)
_FALLBACK_CATEGORY = "other"
_UNIT_CATEGORY = "unit"
_ALL_CATEGORIES = _CATEGORIES + (_FALLBACK_CATEGORY, _UNIT_CATEGORY)

# dbt test docs (one page per family).
_TESTS_DOCS = "https://docs.getdbt.com/docs/build/data-tests"
_UNIT_TESTS_DOCS = "https://docs.getdbt.com/docs/build/unit-tests"

#: Prefix marking a dbt **data** test result (vs models, seeds, snapshots).
_DATA_TEST_PREFIX = "test."
#: Prefix marking a dbt **unit** test result (`dbt test` unit tests).
_UNIT_TEST_PREFIX = "unit_test."

#: Known generic test-type tokens, longest-first so e.g. ``relationships_where``
#: is matched before ``relationships`` when inferring the type from a unique_id.
_KNOWN_TYPES = tuple(sorted(TEST_CATEGORIES, key=len, reverse=True))


def _is_test_result(result: Any) -> bool:
    """True if this run_results entry is a dbt test (data or unit)."""
    uid = str(getattr(result, "unique_id", "") or "")
    return uid.startswith(_DATA_TEST_PREFIX) or uid.startswith(_UNIT_TEST_PREFIX)


def _is_unit_test(unique_id: str) -> bool:
    """True for a dbt unit test (``unit_test.<proj>.<model>.<name>``)."""
    return unique_id.startswith(_UNIT_TEST_PREFIX)


def _status_value(status: Any) -> str:
    """The plain status string for a result.

    artifact-parser models ``status`` as a versioned enum (e.g. ``Status1.pass_``
    with value ``"pass"``); fall back to ``str`` for anything that isn't enum-like.
    """
    return str(getattr(status, "value", status) or "unknown")


def _short_name(unique_id: str) -> str:
    """The bare node name (last dot-segment) of a ``model.<proj>.<name>`` id."""
    return unique_id.rsplit(".", 1)[-1] if unique_id else ""


def _infer_test_type(unique_id: str) -> str:
    """Best-effort test type from a unique_id when the manifest is unavailable.

    Generic test names are ``<type>_<model>_<column>...`` — match the longest
    known type that the name starts with; unknown ⇒ ``""`` (lands in "other").
    """
    parts = unique_id.split(".")
    name = (parts[2] if len(parts) >= 3 else unique_id).lower()
    for test_type in _KNOWN_TYPES:
        if name.startswith(test_type + "_") or name == test_type:
            return test_type
    return ""


class HealthCheckExtractor:
    """Turn a ``run_results.json`` into a categorized dbt-test health report.

    Input: path to ``run_results.json`` + an optional (dbterd-parsed) manifest
    used to resolve each test's authoritative type, column, and tested model.
    Output: a ``health`` dict ready for the top-level data dict.
    """

    def __init__(
        self,
        run_results_path: "str | Path",
        manifest: "Any | None" = None,
        config: "dict | None" = None,
    ) -> None:
        self._path = Path(run_results_path)
        self._manifest = manifest
        self._config = config or {}
        self._nodes = self._manifest_nodes(manifest, "nodes")
        self._unit_tests = self._manifest_nodes(manifest, "unit_tests")

    @staticmethod
    def _manifest_nodes(manifest: "Any | None", attr: str) -> dict:
        """The manifest's *attr* mapping (e.g. ``nodes``/``unit_tests``), or ``{}``."""
        nodes = getattr(manifest, attr, None)
        return nodes if isinstance(nodes, dict) else {}

    def extract(self) -> dict:
        """Build the ``health`` section of the data dict.

        Always returns the manifest-derived ``dimensions`` (all six DPE
        dimensions). When ``run_results.json`` is present, attaches the per-test
        pass/fail detail under ``testResults``; when absent, attaches a ``note``
        recording the path it looked for. Fail-soft throughout.
        """
        dimensions = DimensionAnalyzer(self._manifest, config=self._config).analyze()
        health: dict = {"enabled": True, "dimensions": dimensions}

        results = self._load_results()
        if results is None:
            # No run_results.json — keep the dimensions, note the missing artifact.
            health["testResults"] = None
            health["note"] = f"run_results.json not found at {self._path} — test results skipped."
            return health

        health["testResults"] = self._build_test_results(results)
        return health

    def _build_test_results(self, results: list) -> dict:
        """The per-test pass/fail detail (status summary + by-category findings)."""
        findings = [self._to_finding(r) for r in results if _is_test_result(r)]
        categories: dict[str, list] = {cat: [] for cat in _ALL_CATEGORIES}
        for finding in findings:
            cat = finding["category"]
            categories.setdefault(cat, []).append(
                {k: v for k, v in finding.items() if k != "category"}
            )
        return {"summary": self._summary(findings), "categories": categories}

    def _to_finding(self, result: Any) -> dict:
        """Convert a single parsed test result to a categorized health finding.

        ``kind`` is ``"data"`` or ``"unit"`` so the SPA can split the two test
        families; unit tests carry no column and a ``unit_test`` category.
        """
        uid = str(getattr(result, "unique_id", "") or "")
        is_unit = _is_unit_test(uid)
        if is_unit:
            test_type, model, column, category = "unit_test", self._unit_test_model(uid), "", "unit"
        else:
            test_type, model, column = self._resolve_metadata(uid)
            category = TEST_CATEGORIES.get(test_type, _FALLBACK_CATEGORY)
        return {
            "rule": _short_name(uid),
            "kind": "unit" if is_unit else "data",
            "test_type": test_type or "custom",
            "model": model,
            "column": column,
            "status": _status_value(getattr(result, "status", "unknown")),
            "failures": int(getattr(result, "failures", 0) or 0),
            "message": str(getattr(result, "message", "") or ""),
            "category": category,
            "docs_url": _UNIT_TESTS_DOCS if is_unit else _TESTS_DOCS,
        }

    def _resolve_metadata(self, unique_id: str) -> "tuple[str, str, str]":
        """``(test_type, model, column)`` for a *data* test, manifest-first.

        Reads the authoritative test type / tested model / column from the
        manifest node when available; falls back to inferring the type from the
        ``unique_id`` (model/column then unknown) when it isn't.
        """
        node = self._nodes.get(unique_id)
        if node is not None:
            metadata = getattr(node, "test_metadata", None)
            test_type = str(getattr(metadata, "name", "") or "") if metadata else ""
            model = _short_name(str(getattr(node, "attached_node", "") or ""))
            column = str(getattr(node, "column_name", "") or "")
            return test_type, model, column
        return _infer_test_type(unique_id), "", ""

    def _unit_test_model(self, unique_id: str) -> str:
        """The model a unit test covers (manifest ``unit_tests[*].model``, else uid).

        Unit-test unique_ids are ``unit_test.<proj>.<model>.<name>`` — the model is
        the third dot-segment; the manifest's ``unit_tests`` mapping is preferred
        when present (authoritative ``.model`` field).
        """
        node = self._unit_tests.get(unique_id)
        if node is not None:
            model = str(getattr(node, "model", "") or "")
            if model:
                return model
        parts = unique_id.split(".")
        return parts[2] if len(parts) >= 4 else ""

    def _load_results(self) -> "list | None":
        """Load + parse run_results.json, returning ``.results``; None on failure."""
        try:
            text = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.warning(
                "Health check: run_results.json not found at %s — skipping.",
                self._path,
            )
            return None
        except OSError as exc:
            logger.warning("Health check: could not read %s: %s — skipping.", self._path, exc)
            return None

        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.warning("Health check: could not parse %s: %s — skipping.", self._path, exc)
            return None

        try:
            run_results = parse_run_results(raw)
        except (ArtifactParserError, ValidationError) as exc:
            logger.warning(
                "Health check: %s is not a valid run_results artifact: %s — skipping.",
                self._path,
                exc,
            )
            return None

        return list(run_results.results)

    @staticmethod
    def _blank_summary() -> dict:
        """A zeroed status tally for the test-results summary."""
        return {"pass": 0, "warn": 0, "fail": 0, "error": 0, "skipped": 0, "total": 0}

    @staticmethod
    def _summary(findings: list) -> dict:
        summary = HealthCheckExtractor._blank_summary()
        for f in findings:
            status = f.get("status", "unknown")
            if status in summary:
                summary[status] += 1
            summary["total"] += 1
        return summary
