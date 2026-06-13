"""Assemble the report data dict and write the self-contained site.

``ReportBuilder.generate`` is the whole ``dbdocs generate`` pipeline: load
artifacts → build the one data dict (metadata, nodes, node-level lineage,
column-level lineage, ERDs, nav tree) → stage the bundled SPA → base64-inject the
data → write ``index.html`` + a debug ``dbdocs-data.json``.
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
from dbdocs.site.inject import strip_marker

#: The bundled SPA (shell + assets), shipped in the wheel.
BUNDLE_DIR = Path(__file__).resolve().parent / "bundle"


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
        column_lineage = ColumnLineageExtractor(manifest, catalog, dialect=dialect).extract()

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
            "erd": erd_data,
            "tree": {"byDatabase": tree},
            "readme": self._read_readme(),
            # Health Check is always built — fail-soft to an empty (but enabled)
            # section when no run_results.json is present. ``config.health`` tunes
            # thresholds / disables rules / loads plugin rules.
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
        # Serialize once (compact, not indented — keeps it cheap on large
        # projects); write the plain debug dump and the gzipped payload the SPA
        # fetches.
        payload = json.dumps(
            data, separators=(",", ":"), sort_keys=True, default=self._json_default
        ).encode("utf-8")
        (out / "dbdocs-data.json").write_bytes(payload)
        # mtime=0 keeps the gzip header byte-for-byte reproducible across runs.
        (out / "dbdocs-data.json.gz").write_bytes(gzip.compress(payload, mtime=0))

        logger.info(
            "Generated site at %s (%s nodes, %s column-lineage edges).",
            out,
            len(data["nodes"]),
            len(data["columnLineage"]),
        )
        return str(out)

    @staticmethod
    def _json_default(value: Any) -> str:
        return str(value)
