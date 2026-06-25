"""Assemble the report data dict and write the self-contained site.

``ReportBuilder.generate`` is the whole ``dbdocs generate`` pipeline: load
artifacts → build the one data dict (metadata, nodes, node-level lineage,
column-level lineage, ERDs, nav tree, health) → stage the bundled SPA → write
the external ``dbdocs-data.json.gz`` the SPA fetches at load + a plain-JSON
debug dump + a static ``api/v1/`` tree from the same dict.
"""

import gzip
import json
from datetime import datetime
from pathlib import Path
from shutil import copyfile, copytree, rmtree
from typing import Any

from dbdocs.core.artifacts import adapter_type, load_artifacts
from dbdocs.core.config import DbDocsConfig, _resolve_within_cwd
from dbdocs.core.exceptions import DbDocsConfigError
from dbdocs.core.log import logger
from dbdocs.extract.column_lineage import ColumnLineageExtractor
from dbdocs.extract.erd import build_erd, build_erd_data, erd_algo
from dbdocs.extract.graph import LineageGraph
from dbdocs.extract.health import HealthCheckExtractor
from dbdocs.extract.nodes import build_nodes, build_tree
from dbdocs.site.api_schema import SCHEMA_FILES
from dbdocs.site.inject import strip_marker

#: Characters forbidden in a filesystem path segment — guard unique_ids before
#: writing them as filenames under api/v1/nodes/.
_UNSAFE_ID_CHARS = frozenset("/\\")

#: The bundled SPA (shell + assets), shipped in the wheel.
BUNDLE_DIR = Path(__file__).resolve().parent / "bundle"


def _index_column_lineage(column_lineage: dict) -> dict:
    """Group the flat ``{unique_id}.{column}`` column-lineage map by node id.

    The payload keys column lineage as ``f"{node_id}.{column}"``. Bucketing it
    once into ``{node_id: {key: upstream}}`` keeps ``_write_api`` linear in the
    number of edges instead of re-scanning every entry per node (``O(N²)`` on a
    3000-model project).
    """
    by_node: dict = {}
    for key, upstream in column_lineage.items():
        node_id = str(key).rsplit(".", 1)[0]
        by_node.setdefault(node_id, {})[key] = upstream
    return by_node


def _invert_column_lineage(column_lineage: dict) -> dict:
    """Invert the upstream column-lineage map into a downstream (children) map.

    Each key ``"<node>.<col>"`` in *column_lineage* maps to a list of upstream
    refs ``[{"node": ..., "column": ...}, ...]``.  This function builds the
    reverse: for every upstream ref ``u`` in that list, it appends
    ``{"node": <owner_node>, "column": <owner_col>}`` to
    ``children["<u.node>.<u.column>"]``.  The result answers the impact-analysis
    question "which downstream columns depend on this one?" — mirroring
    ``lineage.children`` at the node level.
    """
    children: dict = {}
    for key, upstream_refs in column_lineage.items():
        owner_node, owner_col = str(key).rsplit(".", 1)
        for ref in upstream_refs:
            upstream_key = f"{ref['node']}.{ref['column']}"
            children.setdefault(upstream_key, []).append({"node": owner_node, "column": owner_col})
    return children


class ReportBuilder:
    """Builds the dbdocs site for a project from its config."""

    def __init__(self, config: DbDocsConfig) -> None:
        self.config = config

    def build_data(self) -> dict:
        """Build the full data dict injected into / dumped alongside the SPA."""
        target_path = self.config.target_path
        manifest, catalog = load_artifacts(target_path)
        adapter = adapter_type(target_path)

        nodes = build_nodes(manifest, catalog)
        tree = build_tree(nodes)
        graph = LineageGraph(manifest, node_ids=set(nodes)).build()

        erd = build_erd(self.config.dbterd, artifacts_dir=target_path)
        erd_data = build_erd_data(erd)

        dialect = self.config.dialect or adapter
        cl_extractor = ColumnLineageExtractor(manifest, catalog, dialect=dialect)
        column_lineage = cl_extractor.extract()

        data: dict = {
            "metadata": {
                **self.config.render_context(),
                "generated_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
                "adapter_type": adapter,
                "dialect": dialect,
                "erd_algo": erd_algo(self.config.dbterd),
                "counts": self._counts(manifest),
            },
            "nodes": nodes,
            "lineage": graph,
            "columnLineage": column_lineage,
            "columnLineageMeta": {"skipped": cl_extractor.skipped},
            "erd": erd_data,
            "tree": {"byDatabase": tree},
            "readme": self._read_readme(),
            "health": HealthCheckExtractor(
                self._resolve_run_results_path(), manifest, config=self.config.health
            ).extract(),
        }
        return data

    def _resolve_run_results_path(self) -> str:
        """Return the path to ``run_results.json`` for the health check extractor.

        If ``config.run_results`` is set, resolve it (fail-soft on escape).
        Otherwise fall back to ``<target_dir>/run_results.json``.
        """
        if self.config.run_results:
            try:
                return str(_resolve_within_cwd(self.config.run_results, "run_results"))
            except DbDocsConfigError:
                logger.warning(
                    "run_results path %r escapes the project directory — using default.",
                    self.config.run_results,
                )
        return str(Path(self.config.target_path) / "run_results.json")

    def _read_readme(self) -> str:
        """The project README markdown (rendered on the overview), or ``""``.

        ``config.readme`` is a path relative to the cwd; a missing file, an
        empty config value, or a relative path that escapes the cwd all yield
        no README section (fail-soft — a bad README must never sink generate).
        """
        if not self.config.readme:
            return ""
        try:
            path = _resolve_within_cwd(self.config.readme, "readme")
        except DbDocsConfigError:
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""

    def _stage_branding(self, out: Path) -> dict:
        """Copy any custom logo/favicon into the output and return their metadata.

        Returns a dict with ``logo`` / ``favicon`` keys set to the deployed asset
        URL (e.g. ``assets/logo.png``) for each override that resolved to a real
        file. Absent/unresolvable overrides are simply omitted — the SPA then
        keeps the bundled default. Fail-soft, mirroring ``_read_readme``.
        """
        meta: dict = {}
        for field_name in ("logo", "favicon"):
            url = self._copy_branding_asset(getattr(self.config, field_name), field_name, out)
            if url:
                meta[field_name] = url
        return meta

    @staticmethod
    def _copy_branding_asset(source: str, name: str, out: Path) -> str:
        """Copy *source* into ``out/assets`` as ``<name><ext>``; return its URL.

        ``""`` for an empty config value, a path escaping the cwd, or a missing
        file (fail-soft — bad branding must never sink generate).
        """
        if not source:
            return ""
        try:
            path = _resolve_within_cwd(source, name)
        except DbDocsConfigError:
            return ""
        if not path.is_file():
            return ""
        target_name = f"{name}{path.suffix}"
        copyfile(path, out / "assets" / target_name)
        return f"assets/{target_name}"

    #: Manifest collections that aren't keyed by a ``<type>.`` unique_id prefix,
    #: mapped to the resource-type label to report them under.
    _MANIFEST_COLLECTIONS = {
        "sources": "source",
        "exposures": "exposure",
        "metrics": "metric",
        "semantic_models": "semantic_model",
        "saved_queries": "saved_query",
        "unit_tests": "unit_test",
    }

    @classmethod
    def _counts(cls, manifest: Any) -> dict:
        """Count every dbt resource type present, not just the headline four.

        ``manifest.nodes`` is keyed ``<resource_type>.<pkg>.<name>`` (model, seed,
        snapshot, test, operation, …); the remaining resource types live in their
        own top-level collections (sources, exposures, metrics, …).
        """
        counts: dict = {}
        for unique_id in getattr(manifest, "nodes", {}) or {}:
            rtype = str(unique_id).split(".")[0]
            counts[rtype] = counts.get(rtype, 0) + 1
        for attr, label in cls._MANIFEST_COLLECTIONS.items():
            collection = getattr(manifest, attr, None)
            if collection:
                counts[label] = counts.get(label, 0) + len(collection)
        return counts

    def generate(self, output_dir: "str | None" = None) -> str:
        """Render the site into ``output_dir`` (or config's). Returns its path.

        The data dict is written as an external ``dbdocs-data.json.gz`` that the
        SPA fetches at load — never inlined into ``index.html``. This keeps the
        HTML tiny regardless of project size, where a multi-MB inlined base64
        payload would otherwise make the page slow to parse. The site must be
        served over HTTP (``dbdocs serve`` or any static host); a plain
        ``dbdocs-data.json`` is written alongside for debugging.

        A static ``api/v1/`` tree is also written from the same ``data`` dict —
        see ``_write_api`` for the layout. The api/ directory is created after the
        bundle copytree (so the rmtree + copytree cycle doesn't touch it) and is
        not shipped in the wheel.
        """
        out = Path(output_dir) if output_dir else Path(self.config.output_path)
        if out.exists():
            rmtree(out)
        out.mkdir(parents=True)
        copytree(src=BUNDLE_DIR, dst=out, dirs_exist_ok=True)

        data = self.build_data()
        data["metadata"].update(self._stage_branding(out))
        index = out / "index.html"
        index.write_text(strip_marker(index.read_text(encoding="utf-8")), encoding="utf-8")
        payload = self._serialize(data)
        (out / "dbdocs-data.json").write_bytes(payload)
        (out / "dbdocs-data.json.gz").write_bytes(gzip.compress(payload, mtime=0))

        self._write_api(out, data)

        logger.info(
            "Generated site at %s (%s nodes, %s column-lineage edges).",
            out,
            len(data["nodes"]),
            len(data["columnLineage"]),
        )
        return str(out)

    def _serialize(self, value: Any) -> bytes:
        """Serialize *value* to compact, deterministic JSON bytes.

        ``sort_keys=True`` and compact ``separators`` keep the output stable
        across runs; ``_json_default`` stringifies non-JSON-native types.
        """
        return json.dumps(
            value, separators=(",", ":"), sort_keys=True, default=self._json_default
        ).encode("utf-8")

    def _write_api(self, out: Path, data: dict) -> None:
        """Write the static ``api/v1/`` tree from the already-assembled data dict.

        Layout::

            api/v1/schema/index.schema.json          — JSON Schema for index.json
            api/v1/schema/node.schema.json            — JSON Schema for per-node files
            api/v1/schema/lineage.schema.json         — JSON Schema for lineage.json
            api/v1/schema/health.schema.json          — JSON Schema for health.json
            api/v1/schema/column-lineage.schema.json  — JSON Schema for column-lineage.json
            api/v1/index.json           — entry-point index: metadata + node stubs
            api/v1/nodes/<id>.json      — one file per node, self-contained
            api/v1/lineage.json         — the full node-level lineage graph
            api/v1/health.json          — the health-check section
            api/v1/column-lineage.json  — whole-graph column lineage (upstream + downstream)

        Each emitted doc carries a relative ``$schema`` self-pointer so tooling
        that understands JSON Schema can validate docs without a network round-trip.
        All files use the same deterministic serialization as the main payload.
        Unique_ids that contain path-separator characters (``/`` or ``\\``) are
        skipped with a warning — dbt unique_ids should never contain them, but the
        guard prevents path-traversal writes.
        """
        api_dir = out / "api" / "v1"
        nodes_dir = api_dir / "nodes"
        schema_dir = api_dir / "schema"
        nodes_dir.mkdir(parents=True, exist_ok=True)
        schema_dir.mkdir(parents=True, exist_ok=True)

        for filename, schema in SCHEMA_FILES.items():
            (schema_dir / filename).write_bytes(self._serialize(schema))

        lineage = data.get("lineage", {})
        raw_column_lineage = data.get("columnLineage", {})
        column_lineage_meta = data.get("columnLineageMeta", {})
        column_lineage_by_node = _index_column_lineage(raw_column_lineage)
        inverted_column_lineage = _invert_column_lineage(raw_column_lineage)
        column_referenced_by_node = _index_column_lineage(inverted_column_lineage)
        nodes = data.get("nodes", {})
        metadata = data.get("metadata", {})

        node_stubs = []
        for node_id, node_record in nodes.items():
            if _UNSAFE_ID_CHARS.intersection(node_id):
                logger.warning(
                    "api/v1: skipping node %r — id contains an unsafe character.", node_id
                )
                continue

            node_stubs.append(
                {
                    "$schema": "schema/node.schema.json",
                    "id": node_id,
                    "name": node_record.get("name", ""),
                    "label": node_record.get("label", ""),
                    "resource_type": node_record.get("resource_type", ""),
                    "database": node_record.get("database", ""),
                    "schema": node_record.get("schema", ""),
                    "description": node_record.get("description", ""),
                    "node_url": f"nodes/{node_id}.json",
                }
            )

            enriched = {
                "$schema": "../schema/node.schema.json",
                **node_record,
                "depends_on": (lineage.get("parents") or {}).get(node_id, []),
                "referenced_by": (lineage.get("children") or {}).get(node_id, []),
                "columnLineage": column_lineage_by_node.get(node_id, {}),
                "column_referenced_by": column_referenced_by_node.get(node_id, {}),
            }
            (nodes_dir / f"{node_id}.json").write_bytes(self._serialize(enriched))

        index_doc = {
            "$schema": "schema/index.schema.json",
            "metadata": metadata,
            "counts": metadata.get("counts", {}),
            "generated_at": metadata.get("generated_at", ""),
            "nodes": node_stubs,
        }
        (api_dir / "index.json").write_bytes(self._serialize(index_doc))
        lineage_doc = {"$schema": "schema/lineage.schema.json", **lineage}
        (api_dir / "lineage.json").write_bytes(self._serialize(lineage_doc))
        health = data.get("health", {})
        health_doc = {"$schema": "schema/health.schema.json", **health}
        (api_dir / "health.json").write_bytes(self._serialize(health_doc))
        column_lineage_doc = {
            "$schema": "schema/column-lineage.schema.json",
            "skipped": column_lineage_meta.get("skipped", 0),
            "edges": raw_column_lineage,
            "children": inverted_column_lineage,
        }
        (api_dir / "column-lineage.json").write_bytes(self._serialize(column_lineage_doc))

    @staticmethod
    def _json_default(value: Any) -> str:
        return str(value)
