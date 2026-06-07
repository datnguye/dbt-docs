import pytest

from dbdocs.core.config import DbDocsConfig
from dbdocs.core.exceptions import DbDocsConfigError


def test_load_missing_file_returns_defaults(tmp_path):
    cfg = DbDocsConfig.load(tmp_path / "dbdocs.yml")
    assert cfg.site_name == "dbt docs"
    assert cfg.target_dir == "target"
    assert cfg.output_dir == "target/site"
    assert cfg.dialect is None


def test_load_empty_file_returns_defaults(tmp_path):
    path = tmp_path / "dbdocs.yml"
    path.write_text("", encoding="utf-8")
    assert DbDocsConfig.load(path).site_name == "dbt docs"


def test_load_reads_overrides(tmp_path):
    path = tmp_path / "dbdocs.yml"
    path.write_text("site_name: My Docs\noutput_dir: public\ndialect: bigquery\n", encoding="utf-8")
    cfg = DbDocsConfig.load(path)
    assert cfg.site_name == "My Docs"
    assert cfg.output_dir == "public"
    assert cfg.dialect == "bigquery"


def test_load_defaults_to_cwd(tmp_path, monkeypatch):
    (tmp_path / "dbdocs.yml").write_text("site_name: CwdDocs\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert DbDocsConfig.load(None).site_name == "CwdDocs"


def test_load_malformed_yaml_raises(tmp_path):
    path = tmp_path / "dbdocs.yml"
    path.write_text("site_name: [unterminated\n", encoding="utf-8")
    with pytest.raises(DbDocsConfigError, match="Could not parse"):
        DbDocsConfig.load(path)


def test_load_non_mapping_raises(tmp_path):
    path = tmp_path / "dbdocs.yml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(DbDocsConfigError, match="must contain a mapping"):
        DbDocsConfig.load(path)


def test_load_unknown_key_raises(tmp_path):
    path = tmp_path / "dbdocs.yml"
    # `template` was removed in the SPA rebuild — it's now an unknown key.
    path.write_text("template: standard\n", encoding="utf-8")
    with pytest.raises(DbDocsConfigError, match="Unknown keys"):
        DbDocsConfig.load(path)


def test_render_context_excludes_build_fields():
    context = DbDocsConfig().render_context()
    for field in ("target_dir", "output_dir", "dialect", "default_version", "dbterd"):
        assert field not in context
    assert context["site_name"] == "dbt docs"
    assert context["project_name"] == "dbt docs"


def test_dbterd_block_loaded(tmp_path):
    path = tmp_path / "dbdocs.yml"
    path.write_text(
        "dbterd:\n  algo: model_contract\n  select:\n    - wildcard:m_*\n", encoding="utf-8"
    )
    cfg = DbDocsConfig.load(path)
    assert cfg.dbterd == {"algo": "model_contract", "select": ["wildcard:m_*"]}


def test_dbterd_defaults_to_empty():
    assert DbDocsConfig().dbterd == {}


def test_target_path_absolute(tmp_path):
    abs_target = str(tmp_path / "out")
    assert DbDocsConfig(target_dir=abs_target).target_path == abs_target


def test_output_path_absolute(tmp_path):
    abs_out = str(tmp_path / "site")
    assert DbDocsConfig(output_dir=abs_out).output_path == abs_out


def test_relative_paths_follow_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = DbDocsConfig(target_dir="target", output_dir="site")
    assert cfg.target_path == str(tmp_path / "target")
    assert cfg.output_path == str(tmp_path / "site")


# ---------------------------------------------------------------------------
# _resolve_within_cwd — containment checks
# ---------------------------------------------------------------------------


def test_output_dir_relative_within_cwd_resolves(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = DbDocsConfig(output_dir="target/site")
    assert cfg.output_path == str(tmp_path / "target" / "site")


def test_output_dir_relative_escaping_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = DbDocsConfig(output_dir="../escape")
    with pytest.raises(DbDocsConfigError, match="output_dir.*escapes"):
        _ = cfg.output_path


def test_output_dir_absolute_is_returned_unchanged(tmp_path):
    abs_out = str(tmp_path / "srv" / "www")
    cfg = DbDocsConfig(output_dir=abs_out)
    assert cfg.output_path == str((tmp_path / "srv" / "www").resolve())


def test_target_dir_relative_within_cwd_resolves(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = DbDocsConfig(target_dir="my/target")
    assert cfg.target_path == str(tmp_path / "my" / "target")


def test_target_dir_relative_escaping_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = DbDocsConfig(target_dir="../../escape")
    with pytest.raises(DbDocsConfigError, match="target_dir.*escapes"):
        _ = cfg.target_path


def test_target_dir_absolute_is_returned_unchanged(tmp_path):
    abs_target = str(tmp_path / "data")
    cfg = DbDocsConfig(target_dir=abs_target)
    assert cfg.target_path == str((tmp_path / "data").resolve())


def test_resolve_within_cwd_equal_to_base_is_allowed(tmp_path, monkeypatch):
    """A path that resolves to exactly cwd (e.g. ".") must be accepted."""
    monkeypatch.chdir(tmp_path)
    cfg = DbDocsConfig(output_dir=".")
    assert cfg.output_path == str(tmp_path.resolve())
