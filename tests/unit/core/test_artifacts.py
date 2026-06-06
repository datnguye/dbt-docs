from types import SimpleNamespace

from dbdocs.core import artifacts


def test_artifact_version_extracts_int(tmp_path):
    (tmp_path / "manifest.json").write_text(
        '{"metadata": {"dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12.json"}}',
        encoding="utf-8",
    )
    assert artifacts.artifact_version(str(tmp_path), "manifest") == 12


def test_artifact_version_none_when_unparseable(tmp_path):
    (tmp_path / "catalog.json").write_text('{"metadata": {}}', encoding="utf-8")
    assert artifacts.artifact_version(str(tmp_path), "catalog") is None


def test_artifact_version_none_when_file_missing(tmp_path):
    assert artifacts.artifact_version(str(tmp_path), "manifest") is None


def test_artifact_version_none_on_bad_json(tmp_path):
    (tmp_path / "manifest.json").write_text("{not json", encoding="utf-8")
    assert artifacts.artifact_version(str(tmp_path), "manifest") is None


def test_adapter_type_read(tmp_path):
    (tmp_path / "manifest.json").write_text(
        '{"metadata": {"adapter_type": "snowflake"}}', encoding="utf-8"
    )
    assert artifacts.adapter_type(str(tmp_path)) == "snowflake"


def test_adapter_type_none_on_missing(tmp_path):
    assert artifacts.adapter_type(str(tmp_path)) is None


def test_db_schema_reads_alias_not_method():
    # `schema` here is a callable (mimicking Pydantic's BaseModel.schema); the
    # value must come from `schema_`.
    entity = SimpleNamespace(database="DB", schema_="SCH", schema=lambda: "WRONG")
    assert artifacts.db_schema(entity) == ("DB", "SCH")


def test_db_schema_falls_back_to_unknown():
    entity = SimpleNamespace(database=None, schema_=None)
    assert artifacts.db_schema(entity) == (artifacts.UNKNOWN, artifacts.UNKNOWN)


def test_node_name():
    assert artifacts.node_name("model.shop.customers") == "customers"


def test_load_artifacts_uses_dbterd(monkeypatch):
    calls = {}
    monkeypatch.setattr(artifacts, "artifact_version", lambda path, artifact: 12)
    monkeypatch.setattr(
        artifacts.file,
        "read_manifest",
        lambda path, version: calls.setdefault("m", (path, version)),
    )
    monkeypatch.setattr(
        artifacts.file, "read_catalog", lambda path, version: calls.setdefault("c", (path, version))
    )
    manifest, catalog = artifacts.load_artifacts("/tmp/target")
    assert manifest == ("/tmp/target", 12)
    assert catalog == ("/tmp/target", 12)
