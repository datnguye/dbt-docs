import json
from pathlib import Path

import pytest

from dbdocs.extract import erd as erd_mod
from dbdocs.site.builder import ReportBuilder


class _FakeErd:
    """Stands in for DbtErd(target="json"): get_erd() returns the json payload."""

    def get_erd(self):
        return json.dumps(
            {
                "tables": [
                    {
                        "name": "customers",
                        "database": "db",
                        "schema": "analytics",
                        "resource_type": "model",
                        "node_name": "model.shop.customers",
                        "columns": [{"name": "id", "data_type": "int", "is_primary_key": True}],
                    },
                    {
                        "name": "stg_customers",
                        "database": "db",
                        "schema": "raw",
                        "resource_type": "model",
                        "node_name": "model.shop.stg_customers",
                        "columns": [{"name": "cust_id", "data_type": "int"}],
                    },
                ],
                "relationships": [
                    {
                        "name": "fk1",
                        "type": "n1",
                        "table_map": ["stg_customers", "customers"],
                        "column_map": [["cust_id"], ["id"]],
                        "relationship_label": "c_to_s",
                    }
                ],
            }
        )


def _patch_boundaries(monkeypatch, fake_manifest, fake_catalog):
    monkeypatch.setattr(
        "dbdocs.site.builder.load_artifacts", lambda target_path: (fake_manifest, fake_catalog)
    )
    monkeypatch.setattr("dbdocs.site.builder.adapter_type", lambda target_path: "snowflake")
    monkeypatch.setattr(
        "dbdocs.site.builder.build_erd", lambda options, artifacts_dir=None: _FakeErd()
    )


def test_build_data_assembles_all_sections(monkeypatch, config, fake_manifest, fake_catalog):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    data = ReportBuilder(config).build_data()

    assert set(data) == {"metadata", "nodes", "lineage", "columnLineage", "erd", "tree", "readme"}
    assert data["metadata"]["adapter_type"] == "snowflake"
    assert data["metadata"]["dialect"] == "snowflake"
    assert data["metadata"]["counts"]["model"] == 2
    assert data["metadata"]["counts"]["source"] == 1
    assert "model.shop.customers" in data["nodes"]
    assert data["lineage"]["edges"]
    # ERD is now structured nodes/edges.
    assert {n["id"] for n in data["erd"]["nodes"]} == {
        "model.shop.customers",
        "model.shop.stg_customers",
    }
    assert data["erd"]["edges"][0]["source"] == "model.shop.stg_customers"
    assert data["tree"]["byDatabase"]["db"]


def test_build_data_uses_config_dialect_override(monkeypatch, config, fake_manifest, fake_catalog):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    config.dialect = "bigquery"
    data = ReportBuilder(config).build_data()
    assert data["metadata"]["dialect"] == "bigquery"


def test_generate_writes_site(monkeypatch, config, fake_manifest, fake_catalog):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    out = ReportBuilder(config).generate()

    index = Path(out) / "index.html"
    assert index.is_file()
    text = index.read_text(encoding="utf-8")
    assert "window.dbdocsData" in text
    assert (Path(out) / "dbdocs-data.json").is_file()
    # Bundled assets are staged alongside (incl. the React Flow graph bundle).
    assert (Path(out) / "assets" / "app.js").is_file()
    assert (Path(out) / "assets" / "graph" / "index.js").is_file()


def test_generate_into_explicit_dir(monkeypatch, config, fake_manifest, fake_catalog, tmp_path):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    target = tmp_path / "explicit"
    out = ReportBuilder(config).generate(output_dir=str(target))
    assert out == str(target)
    assert (target / "index.html").is_file()


def test_json_default_stringifies():
    assert ReportBuilder._json_default(object()) is not None


def test_build_erd_data_parses_json_to_nodes_edges():
    data = erd_mod.build_erd_data(_FakeErd())
    by_id = {n["id"]: n for n in data["nodes"]}
    customers = by_id["model.shop.customers"]
    assert customers["label"] == "customers"
    # `id` is the PK on customers and the FK target column.
    pk = [c for c in customers["columns"] if c["is_primary_key"]]
    fk = [c for c in customers["columns"] if c["is_foreign_key"]]
    assert [c["name"] for c in pk] == ["id"]
    assert [c["name"] for c in fk] == ["id"]
    edge = data["edges"][0]
    assert edge["source"] == "model.shop.stg_customers"
    assert edge["target"] == "model.shop.customers"


def test_build_erd_data_empty_relationships():
    class _Empty:
        def get_erd(self):
            return json.dumps({"tables": [], "relationships": []})

    assert erd_mod.build_erd_data(_Empty()) == {"nodes": [], "edges": []}


def test_build_erd_forwards_options_and_forces_json(monkeypatch):
    captured = {}
    monkeypatch.setattr(erd_mod, "DbtErd", lambda **kw: captured.update(kw) or captured)
    erd_mod.build_erd({"algo": "model_contract", "target": "dbml"})
    assert captured["algo"] == "model_contract"
    # The caller's target is overridden — the SPA always needs the json target.
    assert captured["target"] == "json"


def test_build_erd_handles_no_options(monkeypatch):
    captured = {}
    monkeypatch.setattr(erd_mod, "DbtErd", lambda **kw: captured.update(kw) or captured)
    erd_mod.build_erd(None)
    assert captured == {"target": "json"}


def test_build_erd_threads_artifacts_dir(monkeypatch):
    captured = {}
    monkeypatch.setattr(erd_mod, "DbtErd", lambda **kw: captured.update(kw) or captured)
    erd_mod.build_erd(None, artifacts_dir="custom/target")
    # dbterd reads the manifest/catalog from this dir, not the default ./target.
    assert captured == {"target": "json", "artifacts_dir": "custom/target"}


def test_build_erd_explicit_artifacts_dir_wins(monkeypatch):
    captured = {}
    monkeypatch.setattr(erd_mod, "DbtErd", lambda **kw: captured.update(kw) or captured)
    erd_mod.build_erd({"artifacts_dir": "from/options"}, artifacts_dir="from/config")
    # An explicit artifacts_dir in the dbterd: block takes precedence.
    assert captured["artifacts_dir"] == "from/options"


def test_read_readme_present(monkeypatch, config, fake_manifest, fake_catalog, tmp_path):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    readme = tmp_path / "README.md"
    readme.write_text("# Hello\n\nA project.", encoding="utf-8")
    config.readme = str(readme)
    data = ReportBuilder(config).build_data()
    assert data["readme"].startswith("# Hello")


def test_read_readme_missing_is_empty(monkeypatch, config, fake_manifest, fake_catalog):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    config.readme = "/no/such/README.md"
    assert ReportBuilder(config).build_data()["readme"] == ""


def test_read_readme_disabled_is_empty(monkeypatch, config, fake_manifest, fake_catalog):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    config.readme = ""
    assert ReportBuilder(config).build_data()["readme"] == ""


def test_read_readme_escaping_relative_path_returns_empty(
    monkeypatch, config, fake_manifest, fake_catalog, tmp_path
):
    """A relative readme path that climbs out of cwd must silently yield ''."""
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    monkeypatch.chdir(tmp_path)
    config.readme = "../../../secret"
    assert ReportBuilder(config).build_data()["readme"] == ""


@pytest.mark.parametrize("readme_val", ["README.md", "docs/README.md"])
def test_read_readme_within_cwd_relative_works(
    monkeypatch, config, fake_manifest, fake_catalog, tmp_path, readme_val
):
    """A relative readme path that stays inside cwd resolves and is read."""
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    monkeypatch.chdir(tmp_path)
    readme_path = tmp_path / readme_val
    readme_path.parent.mkdir(parents=True, exist_ok=True)
    readme_path.write_text("# Project\n", encoding="utf-8")
    config.readme = readme_val
    assert ReportBuilder(config).build_data()["readme"] == "# Project\n"


def test_generate_removes_stale_files_on_rerun(monkeypatch, config, fake_manifest, fake_catalog):
    """Files that existed before re-generate must be gone afterwards."""
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    builder = ReportBuilder(config)
    out = Path(builder.generate())

    # Plant a stale file that should NOT survive the next generate.
    stale = out / "stale_asset.js"
    stale.write_text("old stuff", encoding="utf-8")
    assert stale.is_file()

    builder.generate()
    assert not stale.is_file()


def test_generate_dbdocs_data_json_keys_are_sorted(
    monkeypatch, config, fake_manifest, fake_catalog
):
    """dbdocs-data.json must have deterministically sorted keys."""
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    out = Path(ReportBuilder(config).generate())
    raw = (out / "dbdocs-data.json").read_text(encoding="utf-8")
    parsed = json.loads(raw)
    # Re-dump with sort_keys and compare — if already sorted, they must match.
    assert raw == json.dumps(parsed, separators=(",", ":"), sort_keys=True, default=str)
