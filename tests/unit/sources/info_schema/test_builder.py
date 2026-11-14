import json

from dbdocs.site.builder import ReportBuilder
from dbdocs.sources.info_schema.builder import InfoSchemaReportBuilder


def _build(config):
    return InfoSchemaReportBuilder(config).build_data()


def test_build_with_json_enrichment(info_schema_config):
    data = _build(info_schema_config)
    assert data["metadata"]["artifact_source"] == "info_schema"
    assert len(data["nodes"]) == 60
    assert len(data["erd"]["nodes"]) == 13
    assert len(data["erd"]["edges"]) == 3
    assert len(data["lineage"]["edges"]) == 64
    assert sum(len(v) for v in data["columnLineage"].values()) == 182
    assert data["health"]["testResults"]["summary"]["pass"] == 30


def test_build_from_parquet_alone(v2_parquet_only, tmp_path, info_schema_config):
    info_schema_config.target_dir = str(v2_parquet_only)
    data = _build(info_schema_config)
    assert len(data["nodes"]) == 60
    assert len(data["erd"]["edges"]) == 3
    assert data["health"]["testResults"]["summary"]["total"] == 30
    assert data["nodes"]["model.jaffle_shop.orders"]["columns"][0]["type"]


def test_empty_column_lineage_keeps_sqlglot(v2_parquet_only, info_schema_config):
    (v2_parquet_only / "info_schema" / "v1" / "dbt.column_lineage.parquet").unlink()
    info_schema_config.target_dir = str(v2_parquet_only)
    data = _build(info_schema_config)
    assert data["columnLineage"]
    assert data["metadata"]["artifact_source"] == "info_schema"


def test_explicit_run_results_path_is_enrichment(info_schema_config, v2_target, tmp_path):
    for path in (v2_target / "info_schema" / "v1").glob("dbt_rt.*"):
        path.unlink()
    info_schema_config.run_results = str(v2_target / "run_results.json")
    data = _build(info_schema_config)
    assert data["health"]["testResults"]["summary"]["total"] == 30


def test_unreadable_json_artifacts_are_ignored(info_schema_config, v2_target):
    (v2_target / "manifest.json").write_text("{not json", encoding="utf-8")
    assert len(_build(info_schema_config)["nodes"]) == 60


def test_generate_writes_site(info_schema_config, tmp_path):
    out = InfoSchemaReportBuilder(info_schema_config).generate(output_dir=str(tmp_path / "out"))
    payload = json.loads((tmp_path / "out" / "dbdocs-data.json").read_text(encoding="utf-8"))
    assert payload["metadata"]["artifact_source"] == "info_schema"
    assert out == str(tmp_path / "out")


def test_json_path_output_is_unaffected(jaffle_project, config):
    config.target_dir = str(jaffle_project / "target")
    data = ReportBuilder(config).build_data()
    assert "artifact_source" not in data["metadata"]


def test_no_run_results_anywhere_leaves_health_empty(v2_parquet_only, info_schema_config):
    for path in (v2_parquet_only / "info_schema" / "v1").glob("dbt_rt.*"):
        path.unlink()
    info_schema_config.target_dir = str(v2_parquet_only)
    assert _build(info_schema_config)["health"]["testResults"] is None
