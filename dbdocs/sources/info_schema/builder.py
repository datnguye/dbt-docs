"""Report builder that reads dbt 2.0's parquet information schema."""

import json
import tempfile
from dataclasses import replace
from pathlib import Path

from dbdocs.core.config import DbDocsConfig
from dbdocs.core.log import logger
from dbdocs.site.builder import ReportBuilder
from dbdocs.sources.info_schema import synth
from dbdocs.sources.info_schema.reader import InfoSchemaReader

ARTIFACT_SOURCE = "info_schema"


def _read_json(path: Path) -> "dict | None":
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


class InfoSchemaReportBuilder(ReportBuilder):
    """Stages synthesized artifacts, then runs the unchanged ``build_data`` on them.

    Parquet is the base; ``manifest.json`` / ``catalog.json`` / ``run_results.json``
    in ``target_dir`` enrich it when present. ``dbt.column_lineage`` rows replace
    the sqlglot column lineage; an empty table keeps the sqlglot result.
    """

    def __init__(self, config: DbDocsConfig) -> None:
        super().__init__(config)
        self.reader = InfoSchemaReader(config.info_schema_path)

    def build_data(self) -> dict:
        target = Path(self.config.target_path)
        run_results = _read_json(Path(self._resolve_run_results_path()))
        with tempfile.TemporaryDirectory() as staging:
            self._stage(Path(staging), target, run_results)
            staged = ReportBuilder(replace(self.config, target_dir=staging, run_results=None))
            data = staged.build_data()
        data["metadata"]["artifact_source"] = ARTIFACT_SOURCE
        lineage = synth.column_lineage(self.reader)
        if lineage:
            data["columnLineage"] = lineage
        else:
            logger.info("dbt.column_lineage is empty — keeping sqlglot column lineage.")
        return data

    def _stage(self, staging: Path, target: Path, run_results: "dict | None") -> None:
        artifacts = {
            "manifest": synth.build_manifest(self.reader, _read_json(target / "manifest.json")),
            "catalog": synth.build_catalog(self.reader, _read_json(target / "catalog.json")),
            "run_results": synth.build_run_results(self.reader, run_results),
        }
        for name, artifact in artifacts.items():
            if artifact is not None:
                (staging / f"{name}.json").write_text(
                    json.dumps(artifact, default=str), encoding="utf-8"
                )
