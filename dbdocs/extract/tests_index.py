"""Build a per-node, per-column test-definition index from the manifest.

``build_column_tests_index`` scans every ``test.*`` node that has both an
``attached_node`` and a ``column_name`` and groups the test types by the column
they cover. The resulting index is consumed by the column extractor (to annotate
each column record with its defined tests) and by the health extractor (to resolve
a data-test result's type and column from the manifest).

``manifest_test_node_metadata`` extracts ``(test_type, attached_node, column_name)``
from a single parsed manifest test node — shared by both consumers so the field
access pattern is defined once.

Column keys are stored **lowercase** so lookups are case-insensitive — Snowflake
upper-cases catalog column names while the manifest keeps the modeled casing.
Test-type lists are de-duplicated and sorted for deterministic output.
"""

from typing import Any


def manifest_test_node_metadata(node: Any) -> "tuple[str, str, str]":
    """Extract ``(test_type, attached_node, column_name)`` from a manifest test node.

    Returns empty strings for any field that is absent or blank. ``test_type``
    comes from ``test_metadata.name``; the other two are direct node attributes.
    """
    metadata = getattr(node, "test_metadata", None)
    test_type = str(getattr(metadata, "name", "") or "") if metadata is not None else ""
    attached = str(getattr(node, "attached_node", "") or "")
    column = str(getattr(node, "column_name", "") or "")
    return test_type, attached, column


#: Test-metadata kwargs that already appear in their own columns or are noise
#: in the SPA (model/column duplicated; severity/where rarely useful per-row).
_KWARGS_HIDE = {"model", "column_name", "severity", "where", "limit", "warn_if", "error_if"}


def manifest_test_node_details(node: Any) -> "tuple[str, dict]":
    """Extract ``(description, kwargs)`` for surfacing on the per-model Tests table.

    ``description`` is the test node's YAML docstring (often empty). ``kwargs``
    is a filtered copy of ``test_metadata.kwargs`` — the user-supplied test args
    like ``accepted_values: ["bronze","silver"]`` — minus the noise keys already
    shown elsewhere (the tested model/column). Values are stringified so the SPA
    can render them as code chips without further normalization.
    """
    description = str(getattr(node, "description", "") or "")
    metadata = getattr(node, "test_metadata", None)
    raw_kwargs = getattr(metadata, "kwargs", None) if metadata is not None else None
    kwargs: dict = {}
    if isinstance(raw_kwargs, dict):
        for key, value in raw_kwargs.items():
            if key in _KWARGS_HIDE:
                continue
            kwargs[str(key)] = (
                value if isinstance(value, (str, int, float, bool, list)) else str(value)
            )
    return description, kwargs


def build_column_tests_index(manifest: Any) -> dict:
    """Return ``{attached_node_id: {column_lower: [test_type, ...]}}`` from the manifest.

    Only ``test.*`` nodes that have **both** ``attached_node`` and ``column_name``
    are included — table-level tests (no column) are out of scope for per-column
    badges. The test type is read from ``test_metadata.name``; nodes without
    ``test_metadata`` or a blank type are skipped.
    """
    index: dict = {}
    for unique_id, node in (getattr(manifest, "nodes", {}) or {}).items():
        if not str(unique_id).startswith("test."):
            continue
        test_type, attached, column_name = manifest_test_node_metadata(node)
        if not test_type or not attached or not column_name:
            continue
        column_lower = column_name.lower()
        node_index = index.setdefault(attached, {})
        types = node_index.setdefault(column_lower, set())
        types.add(test_type)

    return {
        node_id: {col: sorted(types) for col, types in columns.items()}
        for node_id, columns in index.items()
    }
