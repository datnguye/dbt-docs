"""Loading dbt artifacts (manifest/catalog) via the dbterd parser.

dbterd parses ``manifest.json`` / ``catalog.json`` into ``dbt_artifacts_parser``
Pydantic models. Two cross-cutting gotchas live here so the rest of dbdocs never
has to think about them:

* **Schema field aliasing.** ``dbt_artifacts_parser`` aliases the ``schema``
  field to ``schema_`` to avoid clobbering Pydantic's ``BaseModel.schema()`` —
  so ``node.schema`` is a *bound method*, not the value. Always read
  ``node.schema_``; :func:`db_schema` centralizes that.
* **Schema-version relaxation.** Passing the detected schema version to
  ``read_manifest``/``read_catalog`` makes dbterd apply its relaxation policies,
  keeping parsing robust across dbt versions (including dbt Core 2.0).
"""

import json
from pathlib import Path
from typing import Any

from dbterd.helpers import file

#: Bucket label used when a node/source has no database or schema set.
UNKNOWN = "_unknown"

#: unique_id prefixes surfaced as catalog nodes (tests/macros/etc. excluded).
NODE_PREFIXES = ("model.", "seed.", "snapshot.")

#: unique_id prefixes for manifest.nodes entries that carry only code (no columns).
CODE_ONLY_PREFIXES = ("analysis.", "operation.")

#: Manifest collections outside manifest.nodes, mapping id_prefix → attribute name.
COLLECTION_ATTRS: "dict[str, str]" = {
    "metric.": "metrics",
    "semantic_model.": "semantic_models",
    "saved_query.": "saved_queries",
    "unit_test.": "unit_tests",
    "exposure.": "exposures",
}


def artifact_version(target_path: str, artifact: str) -> "int | None":
    """Resolve a dbt artifact's schema version int from its ``dbt_schema_version``.

    Returns ``None`` (auto-detect, strict) if the version can't be determined —
    e.g. the file is missing or not valid JSON.
    """
    artifact_path = Path(target_path) / f"{artifact}.json"
    try:
        metadata = json.loads(artifact_path.read_text(encoding="utf-8")).get("metadata", {})
    except (OSError, json.JSONDecodeError):
        return None
    extracted = file.extract_artifact_version_from_file(metadata.get("dbt_schema_version", ""))
    return int(extracted) if extracted else None


def load_artifacts(target_path: str) -> "tuple[Any, Any]":
    """Return the dbterd-parsed ``(manifest, catalog)`` for a dbt target dir."""
    manifest = file.read_manifest(
        path=target_path, version=artifact_version(target_path, "manifest")
    )
    catalog = file.read_catalog(path=target_path, version=artifact_version(target_path, "catalog"))
    return manifest, catalog


def adapter_type(target_path: str) -> "str | None":
    """The warehouse adapter (``snowflake``/``bigquery``/…) from manifest metadata.

    Read from the raw JSON rather than the parsed model so it works regardless of
    how the parser exposes ``metadata``. Used as the default sqlglot dialect for
    column-level lineage. ``None`` if unreadable.
    """
    manifest_path = Path(target_path) / "manifest.json"
    try:
        metadata = json.loads(manifest_path.read_text(encoding="utf-8")).get("metadata", {})
    except (OSError, json.JSONDecodeError):
        return None
    return metadata.get("adapter_type")


def db_schema(entity: Any) -> "tuple[str, str]":
    """The ``(database, schema)`` an entity lands in, with safe fallbacks.

    Reads ``schema_`` (the Pydantic alias — ``schema`` is a bound method) and
    falls back to :data:`UNKNOWN` when either part is missing, so grouping never
    produces a ``None`` bucket.
    """
    database = getattr(entity, "database", None) or UNKNOWN
    schema = getattr(entity, "schema_", None) or UNKNOWN
    return str(database), str(schema)


def node_name(unique_id: str) -> str:
    """The dbt node's short name — the last dotted segment of its unique_id."""
    return unique_id.split(".")[-1]
