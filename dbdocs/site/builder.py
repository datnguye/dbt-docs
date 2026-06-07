"""Assemble the report data dict and write the self-contained site.

``ReportBuilder.generate`` is the whole ``dbdocs generate`` pipeline: load
artifacts → build the one data dict (metadata, nodes, node-level lineage,
column-level lineage, ERDs, nav tree) → stage the bundled SPA → base64-inject the
data → write ``index.html`` + a debug ``dbdocs-data.json``.
"""

import json
from datetime import datetime
from pathlib import Path
from shutil import copytree, rmtree
from typing import Any

from dbdocs.core.artifacts import adapter_type, load_artifacts
from dbdocs.core.config import DbDocsConfig, _resolve_within_cwd
from dbdocs.core.exceptions import DbDocsConfigError
from dbdocs.core.log import logger
from dbdocs.extract.column_lineage import ColumnLineageExtractor
from dbdocs.extract.erd import build_erd, build_erd_data
from dbdocs.extract.graph import LineageGraph
from dbdocs.extract.nodes import build_nodes, build_tree
from dbdocs.site.inject import inject

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

        return {
            "metadata": {
                **self.config.render_context(),
                "generated_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
                "adapter_type": adapter,
                "dialect": dialect,
                "counts": self._counts(manifest),
            },
            "nodes": nodes,
            "lineage": graph,
            "columnLineage": column_lineage,
            "erd": erd_data,
            "tree": {"byDatabase": tree},
            "readme": self._read_readme(),
        }

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
        """Render the site into ``output_dir`` (or config's). Returns its path."""
        out = Path(output_dir) if output_dir else Path(self.config.output_path)
        if out.exists():
            rmtree(out)
        out.mkdir(parents=True)
        copytree(src=BUNDLE_DIR, dst=out, dirs_exist_ok=True)

        data = self.build_data()
        index = out / "index.html"
        index.write_text(inject(index.read_text(encoding="utf-8"), data), encoding="utf-8")
        # Compact, not indented — keeps the debug dump cheap on large projects.
        (out / "dbdocs-data.json").write_text(
            json.dumps(data, separators=(",", ":"), sort_keys=True, default=self._json_default),
            encoding="utf-8",
        )

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
