import json
import subprocess
from pathlib import Path
from shutil import rmtree

import pytest

from dbdocs.core.config import DbDocsConfig
from dbdocs.core.exceptions import DeployError
from dbdocs.site import deploy as deploy_mod


@pytest.fixture
def patched_builder(monkeypatch):
    """Stub ReportBuilder.generate so deploy tests don't touch dbterd/sqlglot."""

    def _fake_generate(self, output_dir=None, versioned=False):
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.html").write_text("<html></html>", encoding="utf-8")
        return str(out)

    monkeypatch.setattr(deploy_mod.ReportBuilder, "generate", _fake_generate)


def test_deploy_creates_version_dir_and_index(patched_builder, tmp_path):
    cfg = DbDocsConfig(output_dir=str(tmp_path / "site"))
    deploy_mod.deploy(cfg, version="1.0")
    assert (tmp_path / "site" / "1.0" / "index.html").is_file()
    versions = json.loads((tmp_path / "site" / "versions.json").read_text())
    assert versions == [{"version": "1.0", "title": "1.0", "aliases": []}]


def test_deploy_with_alias_copies_and_records(patched_builder, tmp_path):
    cfg = DbDocsConfig(output_dir=str(tmp_path / "site"))
    deploy_mod.deploy(cfg, version="1.0", alias="latest", title="One")
    assert (tmp_path / "site" / "latest" / "index.html").is_file()
    versions = json.loads((tmp_path / "site" / "versions.json").read_text())
    assert versions[0] == {"version": "1.0", "title": "One", "aliases": ["latest"]}


def test_deploy_moves_alias_off_old_version(patched_builder, tmp_path):
    cfg = DbDocsConfig(output_dir=str(tmp_path / "site"))
    deploy_mod.deploy(cfg, version="1.0", alias="latest")
    deploy_mod.deploy(cfg, version="2.0", alias="latest")
    versions = {
        v["version"]: v for v in json.loads((tmp_path / "site" / "versions.json").read_text())
    }
    assert versions["2.0"]["aliases"] == ["latest"]
    assert versions["1.0"]["aliases"] == []
    # Newest first.
    order = [v["version"] for v in json.loads((tmp_path / "site" / "versions.json").read_text())]
    assert order == ["2.0", "1.0"]


def test_deploy_overwrites_existing_version(patched_builder, tmp_path):
    cfg = DbDocsConfig(output_dir=str(tmp_path / "site"))
    deploy_mod.deploy(cfg, version="1.0")
    deploy_mod.deploy(cfg, version="1.0", alias="latest")
    assert (tmp_path / "site" / "latest" / "index.html").is_file()


def test_read_versions_ignores_bad_file(tmp_path):
    (tmp_path / "versions.json").write_text("{not json", encoding="utf-8")
    assert deploy_mod._read_versions(Path(tmp_path)) == []


def test_read_versions_ignores_non_list(tmp_path):
    (tmp_path / "versions.json").write_text('{"a": 1}', encoding="utf-8")
    assert deploy_mod._read_versions(Path(tmp_path)) == []


def test_push_runs_git(patched_builder, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(deploy_mod.subprocess, "run", lambda cmd, check: calls.append(cmd))
    cfg = DbDocsConfig(output_dir=str(tmp_path / "site"))
    deploy_mod.deploy(cfg, version="1.0", push=True)
    assert any(cmd[:2] == ["git", "push"] for cmd in calls)


def test_push_failure_raises_deploy_error(patched_builder, tmp_path, monkeypatch):
    def _fail(cmd, check):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(deploy_mod.subprocess, "run", _fail)
    cfg = DbDocsConfig(output_dir=str(tmp_path / "site"))
    with pytest.raises(DeployError, match="failed"):
        deploy_mod.deploy(cfg, version="1.0", push=True)


def test_delete_removes_version_dir_and_index(patched_builder, tmp_path):
    cfg = DbDocsConfig(output_dir=str(tmp_path / "site"))
    deploy_mod.deploy(cfg, version="1.0", alias="latest")
    deploy_mod.deploy(cfg, version="2.0")
    deploy_mod.delete(cfg, version="1.0")
    assert not (tmp_path / "site" / "1.0").exists()
    assert not (tmp_path / "site" / "latest").exists()  # alias removed too
    versions = json.loads((tmp_path / "site" / "versions.json").read_text())
    assert [v["version"] for v in versions] == ["2.0"]


def test_delete_unknown_version_raises(patched_builder, tmp_path):
    cfg = DbDocsConfig(output_dir=str(tmp_path / "site"))
    deploy_mod.deploy(cfg, version="1.0")
    with pytest.raises(DeployError, match="not deployed"):
        deploy_mod.delete(cfg, version="9.9")


def test_delete_with_push(patched_builder, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(deploy_mod.subprocess, "run", lambda cmd, check: calls.append(cmd))
    cfg = DbDocsConfig(output_dir=str(tmp_path / "site"))
    deploy_mod.deploy(cfg, version="1.0")
    deploy_mod.delete(cfg, version="1.0", push=True)
    assert any(cmd[:2] == ["git", "push"] for cmd in calls)


def test_delete_when_dirs_already_gone(patched_builder, tmp_path):
    # Index lists the version + an alias, but the on-disk dirs are absent: delete
    # must still succeed and prune the index (covers the missing-dir branches).
    cfg = DbDocsConfig(output_dir=str(tmp_path / "site"))
    deploy_mod.deploy(cfg, version="1.0", alias="latest")
    rmtree(tmp_path / "site" / "1.0")
    rmtree(tmp_path / "site" / "latest")
    deploy_mod.delete(cfg, version="1.0")
    assert json.loads((tmp_path / "site" / "versions.json").read_text()) == []


# ---------------------------------------------------------------------------
# _validate_segment tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["1.0", "latest", "v2-beta", "v2_rc1", "abc123"])
def test_validate_segment_accepts_safe_values(value):
    deploy_mod._validate_segment(value, "version")  # must not raise


@pytest.mark.parametrize(
    "value",
    [
        "..",
        ".",
        "foo/bar",
        "foo\\bar",
        "../etc",
        "",
        "has space",
        "na!me",
    ],
)
def test_validate_segment_rejects_unsafe_values(value):
    with pytest.raises(DeployError, match="Invalid version"):
        deploy_mod._validate_segment(value, "version")


def test_deploy_rejects_unsafe_version(patched_builder, tmp_path):
    cfg = DbDocsConfig(output_dir=str(tmp_path / "site"))
    with pytest.raises(DeployError, match="Invalid version"):
        deploy_mod.deploy(cfg, version="../evil")


def test_deploy_rejects_unsafe_alias(patched_builder, tmp_path):
    cfg = DbDocsConfig(output_dir=str(tmp_path / "site"))
    with pytest.raises(DeployError, match="Invalid alias"):
        deploy_mod.deploy(cfg, version="1.0", alias="../evil")


def test_delete_rejects_unsafe_version(patched_builder, tmp_path):
    cfg = DbDocsConfig(output_dir=str(tmp_path / "site"))
    with pytest.raises(DeployError, match="Invalid version"):
        deploy_mod.delete(cfg, version="..")


def test_deploy_passes_versioned_true_to_generate(tmp_path, monkeypatch):
    calls = []

    def _fake_generate(self, output_dir=None, versioned=False):
        calls.append({"output_dir": output_dir, "versioned": versioned})
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.html").write_text("<html></html>", encoding="utf-8")
        return str(out)

    monkeypatch.setattr(deploy_mod.ReportBuilder, "generate", _fake_generate)
    cfg = DbDocsConfig(output_dir=str(tmp_path / "site"))
    deploy_mod.deploy(cfg, version="1.0")
    assert calls[0]["versioned"] is True


def test_deploy_dotdot_version_rejected(patched_builder, tmp_path):
    cfg = DbDocsConfig(output_dir=str(tmp_path / "site"))
    with pytest.raises(DeployError, match="Invalid version"):
        deploy_mod.deploy(cfg, version="..")


def test_deploy_dot_version_rejected(patched_builder, tmp_path):
    cfg = DbDocsConfig(output_dir=str(tmp_path / "site"))
    with pytest.raises(DeployError, match="Invalid version"):
        deploy_mod.deploy(cfg, version=".")


def test_delete_rejects_malicious_alias_in_versions_json(patched_builder, tmp_path):
    # Simulate a tampered versions.json where an alias contains a path-traversal
    # segment that would escape the output tree if passed directly to rmtree.
    site = tmp_path / "site"
    site.mkdir(parents=True)
    evil_target = tmp_path / "evil"
    evil_target.mkdir()
    versions_data = [{"version": "1.0", "title": "1.0", "aliases": ["../evil"]}]
    (site / "versions.json").write_text(json.dumps(versions_data), encoding="utf-8")

    cfg = DbDocsConfig(output_dir=str(site))
    with pytest.raises(DeployError, match="Invalid alias"):
        deploy_mod.delete(cfg, version="1.0")

    # The would-be target must NOT have been removed.
    assert evil_target.exists()
