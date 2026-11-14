import duckdb
import pytest

from dbdocs.core.exceptions import DbDocsConfigError
from dbdocs.sources.info_schema.reader import InfoSchemaReader


def _write_project(directory, schema_version):
    directory.mkdir(parents=True, exist_ok=True)
    duckdb.connect().execute(
        f"COPY (SELECT {schema_version} AS schema_version) "
        f"TO '{directory / 'dbt.project.parquet'}' (FORMAT PARQUET)"
    )


def test_reads_rows_as_dicts(v2_parquet_only):
    reader = InfoSchemaReader(v2_parquet_only / "info_schema" / "v1")
    models = reader.table("dbt.models")
    assert len(models) == 13
    assert models[0]["unique_id"].startswith("model.")


def test_missing_table_reads_empty(v2_parquet_only):
    reader = InfoSchemaReader(v2_parquet_only / "info_schema" / "v1")
    assert reader.table("dbt.nope") == []


def test_each_table_is_read_once(v2_parquet_only):
    reader = InfoSchemaReader(v2_parquet_only / "info_schema" / "v1")
    models = reader.table("dbt.models")
    (v2_parquet_only / "info_schema" / "v1" / "dbt.models.parquet").unlink()
    assert reader.table("dbt.models") is models


def test_missing_directory_raises(tmp_path):
    with pytest.raises(DbDocsConfigError, match="not found"):
        InfoSchemaReader(tmp_path / "absent")


def test_unsupported_schema_version_raises(tmp_path):
    _write_project(tmp_path, 2)
    with pytest.raises(DbDocsConfigError, match="schema_version 2"):
        InfoSchemaReader(tmp_path)


def test_missing_project_table_raises(tmp_path):
    with pytest.raises(DbDocsConfigError, match="schema_version None"):
        InfoSchemaReader(tmp_path)


def test_supported_schema_version_accepted(tmp_path):
    _write_project(tmp_path, 1)
    assert InfoSchemaReader(tmp_path).table("dbt.project")[0]["schema_version"] == 1
