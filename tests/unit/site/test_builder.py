import gzip
import json
from datetime import datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from dbdocs.extract import erd as erd_mod
from dbdocs.site.api_schema import SCHEMA_FILES
from dbdocs.site.builder import _UNSAFE_ID_CHARS, ReportBuilder, _invert_column_lineage


class _FakeErd:
    """Stands in for DbtErd(target="json"): get_erd() returns the official payload."""

    def get_erd(self):
        return json.dumps(
            {
                "nodes": [
                    {
                        "id": "model.shop.customers",
                        "name": "customers",
                        "database": "db",
                        "schema_name": "analytics",
                        "resource_type": "model",
                        "columns": [
                            {
                                "name": "id",
                                "data_type": "int",
                                "is_primary_key": True,
                                "is_foreign_key": True,
                            }
                        ],
                    },
                    {
                        "id": "model.shop.stg_customers",
                        "name": "stg_customers",
                        "database": "db",
                        "schema_name": "raw",
                        "resource_type": "model",
                        "columns": [
                            {
                                "name": "cust_id",
                                "data_type": "int",
                                "is_primary_key": False,
                                "is_foreign_key": False,
                            }
                        ],
                    },
                ],
                "edges": [
                    {
                        "id": "fk1",
                        "from_id": "model.shop.customers",
                        "to_id": "model.shop.stg_customers",
                        "from_columns": ["id"],
                        "to_columns": ["cust_id"],
                        "label": "c_to_s",
                        "cardinality": "n1",
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


class _FrozenDatetime:
    """Pins datetime.now() so two generate() runs share one generated_at stamp."""

    @classmethod
    def now(cls):
        return datetime(2026, 1, 1, 0, 0, 0)


def test_build_data_assembles_all_sections(monkeypatch, config, fake_manifest, fake_catalog):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    data = ReportBuilder(config).build_data()

    assert set(data) == {
        "metadata",
        "nodes",
        "lineage",
        "columnLineage",
        "columnLineageMeta",
        "erd",
        "tree",
        "readme",
        "health",
    }
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


def test_build_data_erd_algo_defaults_to_dbterd_default(
    monkeypatch, config, fake_manifest, fake_catalog
):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    data = ReportBuilder(config).build_data()
    assert data["metadata"]["erd_algo"] == "test_relationship"


def test_build_data_erd_algo_uses_configured_algo(monkeypatch, config, fake_manifest, fake_catalog):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    config.dbterd = {"algo": "model_contract"}
    data = ReportBuilder(config).build_data()
    assert data["metadata"]["erd_algo"] == "model_contract"


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
    # Data is loaded externally, never inlined — the marker is stripped, not left
    # as a literal comment, and no payload script is embedded.
    assert "window.dbdocsData" not in text
    assert "<!-- DBDOCS_DATA -->" not in text
    assert (Path(out) / "dbdocs-data.json").is_file()
    # The gzipped payload the SPA fetches decompresses to the data dict.
    gz = (Path(out) / "dbdocs-data.json.gz").read_bytes()
    assert json.loads(gzip.decompress(gz))["metadata"]["adapter_type"] == "snowflake"
    # Bundled assets are staged alongside (incl. the React Flow graph bundle).
    assert (Path(out) / "assets" / "js" / "app.js").is_file()
    assert (Path(out) / "assets" / "graph" / "index.js").is_file()


def test_generate_gzip_matches_plain_json(monkeypatch, config, fake_manifest, fake_catalog):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    out = Path(ReportBuilder(config).generate())
    plain = (out / "dbdocs-data.json").read_bytes()
    assert gzip.decompress((out / "dbdocs-data.json.gz").read_bytes()) == plain


def test_generate_into_explicit_dir(monkeypatch, config, fake_manifest, fake_catalog, tmp_path):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    target = tmp_path / "explicit"
    out = ReportBuilder(config).generate(output_dir=str(target))
    assert out == str(target)
    assert (target / "index.html").is_file()


def test_generate_stages_custom_logo_and_favicon(
    monkeypatch, config, fake_manifest, fake_catalog, tmp_path
):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    logo_src = tmp_path / "brand.png"
    logo_src.write_bytes(b"PNG")
    fav_src = tmp_path / "fav.ico"
    fav_src.write_bytes(b"ICO")
    config.logo = str(logo_src)
    config.favicon = str(fav_src)

    out = Path(ReportBuilder(config).generate())

    # Files copied into assets/, named after the field + the source extension.
    assert (out / "assets" / "logo.png").read_bytes() == b"PNG"
    assert (out / "assets" / "favicon.ico").read_bytes() == b"ICO"
    # Deployed URLs injected into the SPA metadata (base64 payload + debug dump).
    data = json.loads((out / "dbdocs-data.json").read_text(encoding="utf-8"))
    assert data["metadata"]["logo"] == "assets/logo.png"
    assert data["metadata"]["favicon"] == "assets/favicon.ico"


def test_generate_omits_branding_for_missing_file(
    monkeypatch, config, fake_manifest, fake_catalog, tmp_path
):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    config.logo = str(tmp_path / "nope.png")  # never created

    out = Path(ReportBuilder(config).generate())

    assert not (out / "assets" / "logo.png").exists()
    data = json.loads((out / "dbdocs-data.json").read_text(encoding="utf-8"))
    assert "logo" not in data["metadata"]


def test_generate_keeps_default_branding_when_unset(
    monkeypatch, config, fake_manifest, fake_catalog
):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    out = Path(ReportBuilder(config).generate())

    data = json.loads((out / "dbdocs-data.json").read_text(encoding="utf-8"))
    assert "logo" not in data["metadata"]
    assert "favicon" not in data["metadata"]
    # The bundled default favicon is still present, untouched.
    assert (out / "assets" / "favicon.svg").is_file()


def test_copy_branding_asset_rejects_escaping_path(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "site"
    (out / "assets").mkdir(parents=True)
    # A relative path escaping the cwd is rejected → no URL, no copy.
    assert ReportBuilder._copy_branding_asset("../outside.png", "logo", out) == ""
    assert not (out / "assets" / "logo.png").exists()


def test_json_default_stringifies():
    assert ReportBuilder._json_default(object()) is not None


def test_build_erd_data_parses_json_to_nodes_edges():
    data = erd_mod.build_erd_data(_FakeErd())
    by_id = {n["id"]: n for n in data["nodes"]}
    customers = by_id["model.shop.customers"]
    assert customers["label"] == "customers"
    # `id` is both the PK and the FK column on customers.
    pk = [c for c in customers["columns"] if c["is_primary_key"]]
    fk = [c for c in customers["columns"] if c["is_foreign_key"]]
    assert [c["name"] for c in pk] == ["id"]
    assert [c["name"] for c in fk] == ["id"]
    edge = data["edges"][0]
    # source = to_id (parent/referenced side); target = from_id (FK/child side).
    assert edge["source"] == "model.shop.stg_customers"
    assert edge["target"] == "model.shop.customers"


def test_build_erd_data_empty_relationships():
    class _Empty:
        def get_erd(self):
            return json.dumps({"nodes": [], "edges": []})

    assert erd_mod.build_erd_data(_Empty()) == {"nodes": [], "edges": []}


def test_backfill_fk_flags_skips_dangling_edge_and_empty_from_columns():
    """_backfill_fk_flags must not crash on a dangling edge target or empty from_columns."""
    node = {"id": "n1", "columns": [{"name": "col_a", "is_foreign_key": False}]}
    # Dangling edge: target "n_missing" not in nodes list.
    dangling = {"target": "n_missing", "from_columns": ["col_a"]}
    # Edge with no from_columns: target exists but nothing to backfill.
    no_cols = {"target": "n1", "from_columns": []}
    erd_mod._backfill_fk_flags([node], [dangling, no_cols])
    # Neither edge should have set is_foreign_key on node.col_a.
    assert node["columns"][0]["is_foreign_key"] is False


def test_build_erd_data_entity_name_format_resolves_edge_ids():
    """Regression: when entity_name_format is set dbterd emits edge from_id/to_id
    as the short name (e.g. ``orders``) while node id is the full unique_id
    (e.g. ``model.jaffle_shop.orders``). build_erd_data must resolve those back
    to the node id so source/target reference a valid node.

    Also covers FK backfill: the orders.location_id column has is_foreign_key=False
    in the raw node payload (dbterd model_contract quirk), but appears in the
    edge from_columns → build_erd_data sets it to True."""

    class _NameFormatErd:
        def get_erd(self):
            return json.dumps(
                {
                    "nodes": [
                        {
                            "id": "model.jaffle_shop.orders",
                            "name": "orders",
                            "database": "db",
                            "schema_name": "main",
                            "resource_type": "model",
                            "columns": [
                                {
                                    "name": "order_id",
                                    "data_type": "int",
                                    "is_primary_key": True,
                                    "is_foreign_key": False,
                                },
                                {
                                    "name": "location_id",
                                    "data_type": "int",
                                    "is_primary_key": False,
                                    "is_foreign_key": False,
                                },
                            ],
                        },
                        {
                            "id": "model.jaffle_shop.locations",
                            "name": "locations",
                            "database": "db",
                            "schema_name": "main",
                            "resource_type": "model",
                            "columns": [
                                {
                                    "name": "id",
                                    "data_type": "int",
                                    "is_primary_key": True,
                                    "is_foreign_key": False,
                                }
                            ],
                        },
                    ],
                    "edges": [
                        {
                            "id": "fk_loc",
                            "from_id": "orders",
                            "to_id": "locations",
                            "from_columns": ["location_id"],
                            "to_columns": ["id"],
                            "label": "",
                            "cardinality": "n1",
                        }
                    ],
                }
            )

    data = erd_mod.build_erd_data(_NameFormatErd())
    node_ids = {n["id"] for n in data["nodes"]}
    assert node_ids == {"model.jaffle_shop.orders", "model.jaffle_shop.locations"}
    edge = data["edges"][0]
    # source = parent (to_id → locations), target = child (from_id → orders)
    assert edge["source"] == "model.jaffle_shop.locations"
    assert edge["target"] == "model.jaffle_shop.orders"
    # FK backfill: orders.location_id was not_fk in raw payload but is in from_columns.
    orders = next(n for n in data["nodes"] if n["id"] == "model.jaffle_shop.orders")
    by_name = {c["name"]: c for c in orders["columns"]}
    assert by_name["location_id"]["is_foreign_key"] is True
    assert by_name["order_id"]["is_foreign_key"] is False  # not in any from_columns
    # Referenced side (locations.id) is not backfilled as FK.
    locations = next(n for n in data["nodes"] if n["id"] == "model.jaffle_shop.locations")
    assert locations["columns"][0]["is_foreign_key"] is False


def test_build_erd_data_node_without_name_skipped_in_name_map():
    """A node with no ``name`` field is skipped when building the name→id map."""

    class _NoNameErd:
        def get_erd(self):
            return json.dumps(
                {
                    "nodes": [
                        {
                            "id": "model.shop.a",
                            "database": "db",
                            "schema_name": "s",
                            "resource_type": "model",
                            "columns": [],
                        },
                    ],
                    "edges": [],
                }
            )

    data = erd_mod.build_erd_data(_NoNameErd())
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["label"] == ""


def test_build_erd_data_ambiguous_entity_name_left_unresolved():
    """Two nodes sharing the same formatted name produce an ambiguous entry.

    _resolve_edge_id must leave the raw short name intact rather than binding
    it to an arbitrary node — fail-honest, not fail-wrong.
    """

    class _AmbiguousErd:
        def get_erd(self):
            return json.dumps(
                {
                    "nodes": [
                        {
                            "id": "model.pkg_a.orders",
                            "name": "orders",
                            "database": "db",
                            "schema_name": "a",
                            "resource_type": "model",
                            "columns": [],
                        },
                        {
                            "id": "model.pkg_b.orders",
                            "name": "orders",
                            "database": "db",
                            "schema_name": "b",
                            "resource_type": "model",
                            "columns": [],
                        },
                        {
                            "id": "model.pkg_a.customers",
                            "name": "customers",
                            "database": "db",
                            "schema_name": "a",
                            "resource_type": "model",
                            "columns": [],
                        },
                    ],
                    "edges": [
                        {
                            "id": "fk_ambig",
                            "from_id": "orders",
                            "to_id": "customers",
                            "from_columns": [],
                            "to_columns": [],
                            "label": "",
                            "cardinality": "n1",
                        }
                    ],
                }
            )

    data = erd_mod.build_erd_data(_AmbiguousErd())
    edge = data["edges"][0]
    # "customers" is unambiguous → resolves to the full unique_id.
    assert edge["source"] == "model.pkg_a.customers"
    # "orders" is ambiguous (two nodes share that name) → stays as the raw short name.
    assert edge["target"] == "orders"


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


def test_erd_algo_falls_back_to_dbterd_default():
    assert erd_mod.erd_algo(None) == "test_relationship"
    assert erd_mod.erd_algo({}) == "test_relationship"


def test_erd_algo_returns_configured_algo():
    assert erd_mod.erd_algo({"algo": "model_contract"}) == "model_contract"


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


# ---------------------------------------------------------------------------
# Health Check integration in build_data / generate
# ---------------------------------------------------------------------------


def test_build_data_always_has_health_key(
    monkeypatch, config, fake_manifest, fake_catalog, run_results_path
):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    config.run_results = str(run_results_path)
    data = ReportBuilder(config).build_data()
    assert "health" in data
    assert data["health"]["enabled"] is True
    assert "dimensions" in data["health"]
    assert data["health"]["testResults"] is not None


def test_build_data_health_test_results_counts(
    monkeypatch, config, fake_manifest, fake_catalog, run_results_path
):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    config.run_results = str(run_results_path)
    data = ReportBuilder(config).build_data()
    s = data["health"]["testResults"]["summary"]
    # The fixture is a sanitized real jaffle_shop run: 29 data tests + 3 unit
    # tests = 32 (17 pass, 1 fail, 14 skipped); the model-build entry is filtered
    # out. fake_manifest lacks these test nodes, so the type is inferred from ids.
    assert s["pass"] == 17
    assert s["fail"] == 1
    assert s["skipped"] == 14
    assert s["total"] == 32


def test_build_data_health_dimensions_present(
    monkeypatch, config, fake_manifest, fake_catalog, run_results_path
):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    config.run_results = str(run_results_path)
    data = ReportBuilder(config).build_data()
    assert set(data["health"]["dimensions"]) == {
        "testing",
        "modeling",
        "documentation",
        "structure",
        "performance",
        "governance",
    }


def test_build_data_health_fail_soft_on_missing_run_results(
    monkeypatch, config, fake_manifest, fake_catalog, tmp_path
):
    """A missing run_results.json should not crash build_data."""
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    config.run_results = str(tmp_path / "nonexistent_run_results.json")
    data = ReportBuilder(config).build_data()
    assert data["health"]["enabled"] is True
    # Dimensions still built; test detail skipped with a note.
    assert "dimensions" in data["health"]
    assert data["health"]["testResults"] is None
    assert "note" in data["health"]


def test_generate_includes_health_in_payload(
    monkeypatch, config, fake_manifest, fake_catalog, run_results_path
):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    config.run_results = str(run_results_path)
    out = Path(ReportBuilder(config).generate())
    data = json.loads((out / "dbdocs-data.json").read_text(encoding="utf-8"))
    assert "health" in data
    assert data["health"]["enabled"] is True


def test_resolve_run_results_uses_target_dir_default(
    monkeypatch, config, fake_manifest, fake_catalog, tmp_path
):
    """When run_results is None, default to <target_dir>/run_results.json."""
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    monkeypatch.chdir(tmp_path)
    config.run_results = None
    config.target_dir = str(tmp_path / "target")
    (tmp_path / "target").mkdir(parents=True, exist_ok=True)
    # No run_results.json created → fail-soft: dimensions built, test detail noted.
    data = ReportBuilder(config).build_data()
    assert data["health"]["testResults"] is None


def test_resolve_run_results_escaping_path_uses_default(
    monkeypatch, config, fake_manifest, fake_catalog, tmp_path
):
    """An escaping run_results path is silently replaced by the default."""
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    monkeypatch.chdir(tmp_path)
    config.run_results = "../../../etc/passwd"
    # Should not raise; builds a health section (empty because no file there).
    data = ReportBuilder(config).build_data()
    assert "health" in data


# ---------------------------------------------------------------------------
# Static REST api/v1 surface
# ---------------------------------------------------------------------------


def test_generate_writes_api_v1_files(monkeypatch, config, fake_manifest, fake_catalog):
    """generate() must produce api/v1/index.json, lineage.json, and health.json."""
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    out = Path(ReportBuilder(config).generate())

    assert (out / "api" / "v1" / "index.json").is_file()
    assert (out / "api" / "v1" / "lineage.json").is_file()
    assert (out / "api" / "v1" / "health.json").is_file()
    assert (out / "api" / "v1" / "nodes").is_dir()


def test_api_index_lists_all_nodes(monkeypatch, config, fake_manifest, fake_catalog):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    out = Path(ReportBuilder(config).generate())

    index = json.loads((out / "api" / "v1" / "index.json").read_text(encoding="utf-8"))
    node_ids_in_index = {n["id"] for n in index["nodes"]}
    data = json.loads((out / "dbdocs-data.json").read_text(encoding="utf-8"))
    assert node_ids_in_index == set(data["nodes"].keys())


def test_api_index_node_stub_shape(monkeypatch, config, fake_manifest, fake_catalog):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    out = Path(ReportBuilder(config).generate())

    index = json.loads((out / "api" / "v1" / "index.json").read_text(encoding="utf-8"))
    stub = next(n for n in index["nodes"] if n["id"] == "model.shop.customers")
    assert stub["name"] == "customers"
    assert stub["resource_type"] == "model"
    assert stub["database"] == "db"
    assert stub["schema"] == "analytics"
    assert stub["node_url"] == "nodes/model.shop.customers.json"
    assert "id" in stub
    assert "label" in stub
    assert "description" in stub


def test_api_index_has_metadata_and_counts(monkeypatch, config, fake_manifest, fake_catalog):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    out = Path(ReportBuilder(config).generate())

    index = json.loads((out / "api" / "v1" / "index.json").read_text(encoding="utf-8"))
    assert "metadata" in index
    assert "counts" in index
    assert "generated_at" in index
    assert index["counts"] == index["metadata"]["counts"]


def test_api_per_node_file_is_self_contained(monkeypatch, config, fake_manifest, fake_catalog):
    """Each per-node file has depends_on, referenced_by, and columnLineage slices."""
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    out = Path(ReportBuilder(config).generate())

    node_file = out / "api" / "v1" / "nodes" / "model.shop.customers.json"
    assert node_file.is_file()
    node_doc = json.loads(node_file.read_text(encoding="utf-8"))

    assert "depends_on" in node_doc
    assert "referenced_by" in node_doc
    assert "columnLineage" in node_doc
    assert isinstance(node_doc["depends_on"], list)
    assert isinstance(node_doc["referenced_by"], list)
    assert isinstance(node_doc["columnLineage"], dict)
    assert node_doc["id"] == "model.shop.customers"
    assert node_doc["resource_type"] == "model"


def test_api_per_node_lineage_values(monkeypatch, config, fake_manifest, fake_catalog):
    """depends_on and referenced_by match the lineage graph from data dict."""
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    out = Path(ReportBuilder(config).generate())

    data = json.loads((out / "dbdocs-data.json").read_text(encoding="utf-8"))
    lineage = data["lineage"]

    for node_id in data["nodes"]:
        node_file = out / "api" / "v1" / "nodes" / f"{node_id}.json"
        node_doc = json.loads(node_file.read_text(encoding="utf-8"))
        assert node_doc["depends_on"] == lineage["parents"].get(node_id, [])
        assert node_doc["referenced_by"] == lineage["children"].get(node_id, [])


def test_api_per_node_column_lineage_slice(monkeypatch, config, fake_manifest, fake_catalog):
    """columnLineage in per-node file contains only entries prefixed by that node id."""
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    out = Path(ReportBuilder(config).generate())

    data = json.loads((out / "dbdocs-data.json").read_text(encoding="utf-8"))
    for node_id in data["nodes"]:
        node_file = out / "api" / "v1" / "nodes" / f"{node_id}.json"
        node_doc = json.loads(node_file.read_text(encoding="utf-8"))
        expected = {k: v for k, v in data["columnLineage"].items() if k.startswith(f"{node_id}.")}
        assert node_doc["columnLineage"] == expected


def test_api_lineage_json_matches_data_dict(monkeypatch, config, fake_manifest, fake_catalog):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    out = Path(ReportBuilder(config).generate())

    data = json.loads((out / "dbdocs-data.json").read_text(encoding="utf-8"))
    lineage = json.loads((out / "api" / "v1" / "lineage.json").read_text(encoding="utf-8"))
    lineage_without_schema = {k: v for k, v in lineage.items() if k != "$schema"}
    assert lineage_without_schema == data["lineage"]


def test_api_health_json_matches_data_dict(monkeypatch, config, fake_manifest, fake_catalog):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    out = Path(ReportBuilder(config).generate())

    data = json.loads((out / "dbdocs-data.json").read_text(encoding="utf-8"))
    health = json.loads((out / "api" / "v1" / "health.json").read_text(encoding="utf-8"))
    health_without_schema = {k: v for k, v in health.items() if k != "$schema"}
    assert health_without_schema == data["health"]


def test_api_output_is_deterministic(monkeypatch, config, fake_manifest, fake_catalog):
    """Two generate() runs must produce byte-for-byte identical api/v1 files."""
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    monkeypatch.setattr("dbdocs.site.builder.datetime", _FrozenDatetime)
    builder = ReportBuilder(config)

    out1 = Path(builder.generate())
    snapshots_1 = {p.name: p.read_bytes() for p in (out1 / "api" / "v1").rglob("*.json")}

    out2 = Path(builder.generate())
    snapshots_2 = {p.name: p.read_bytes() for p in (out2 / "api" / "v1").rglob("*.json")}

    assert set(snapshots_1) == set(snapshots_2)
    for name in snapshots_1:
        assert snapshots_1[name] == snapshots_2[name], f"api/v1/{name} differs between runs"


def test_api_per_node_file_for_every_node(monkeypatch, config, fake_manifest, fake_catalog):
    """There must be exactly one nodes/<id>.json per node in data['nodes']."""
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    out = Path(ReportBuilder(config).generate())

    data = json.loads((out / "dbdocs-data.json").read_text(encoding="utf-8"))
    node_files = {p.stem for p in (out / "api" / "v1" / "nodes").iterdir()}
    assert node_files == set(data["nodes"].keys())


def test_api_unsafe_id_skipped(monkeypatch, config, fake_manifest, fake_catalog):
    """A node whose unique_id contains '/' is skipped; no file is written for it."""
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)

    original_build = ReportBuilder.build_data

    def patched_build(self):
        data = original_build(self)
        data["nodes"]["bad/id"] = {
            "id": "bad/id",
            "name": "bad",
            "label": "bad",
            "resource_type": "model",
            "database": "db",
            "schema": "s",
            "description": "",
        }
        return data

    monkeypatch.setattr(ReportBuilder, "build_data", patched_build)
    out = Path(ReportBuilder(config).generate())

    node_files = {p.name for p in (out / "api" / "v1" / "nodes").iterdir()}
    assert not any("bad" in f for f in node_files)


def test_unsafe_id_chars_constant():
    assert "/" in _UNSAFE_ID_CHARS
    assert "\\" in _UNSAFE_ID_CHARS


def test_serialize_is_deterministic(config):
    """_serialize must produce sort_keys=True compact JSON bytes."""
    builder = ReportBuilder(config)
    value = {"z": 1, "a": 2, "m": [3, 1, 2]}
    result = builder._serialize(value)
    assert result == b'{"a":2,"m":[3,1,2],"z":1}'


def test_serialize_used_for_main_payload(monkeypatch, config, fake_manifest, fake_catalog):
    """The main dbdocs-data.json must equal _serialize(data) output."""
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    out = Path(ReportBuilder(config).generate())

    plain = (out / "dbdocs-data.json").read_bytes()
    data = json.loads(plain)
    builder = ReportBuilder(config)
    assert plain == builder._serialize(data)


# ---------------------------------------------------------------------------
# JSON Schema drift guard
# ---------------------------------------------------------------------------

_SCHEMA_DOC_PAIRS = [
    ("schema/index.schema.json", "index.json"),
    ("schema/lineage.schema.json", "lineage.json"),
    ("schema/health.schema.json", "health.json"),
]


@pytest.fixture
def api_out(monkeypatch, config, fake_manifest, fake_catalog):
    """Generated site output directory with api/v1/ populated."""
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    return Path(ReportBuilder(config).generate()) / "api" / "v1"


def test_api_schema_files_are_written(api_out):
    """generate() must write all four schema files under api/v1/schema/."""
    for filename in SCHEMA_FILES:
        assert (api_out / "schema" / filename).is_file(), f"missing schema/{filename}"


def test_api_schema_files_are_valid_draft2020(api_out):
    """Every emitted schema file must itself be a valid Draft 2020-12 schema."""
    for filename in SCHEMA_FILES:
        raw = json.loads((api_out / "schema" / filename).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(raw)


@pytest.mark.parametrize("schema_rel, doc_rel", _SCHEMA_DOC_PAIRS)
def test_api_doc_schema_pointer_exists(api_out, schema_rel, doc_rel):
    """Each emitted doc carries a $schema key pointing at an existing schema file."""
    doc = json.loads((api_out / doc_rel).read_text(encoding="utf-8"))
    assert "$schema" in doc, f"{doc_rel} is missing a $schema key"
    schema_path = api_out / doc["$schema"]
    assert schema_path.is_file(), f"{doc_rel}.$schema → {doc['$schema']} not found on disk"


def test_api_node_doc_schema_pointer_exists(api_out):
    """Every per-node file carries a $schema pointing at the node schema."""
    for node_file in (api_out / "nodes").iterdir():
        doc = json.loads(node_file.read_text(encoding="utf-8"))
        assert "$schema" in doc, f"{node_file.name} is missing a $schema key"
        schema_path = (api_out / "nodes") / doc["$schema"]
        assert schema_path.is_file(), (
            f"{node_file.name}.$schema → {doc['$schema']} not found on disk"
        )


@pytest.mark.parametrize("schema_rel, doc_rel", _SCHEMA_DOC_PAIRS)
def test_api_doc_validates_against_schema(api_out, schema_rel, doc_rel):
    """Each top-level doc validates against its committed schema."""
    schema = json.loads((api_out / schema_rel).read_text(encoding="utf-8"))
    doc = json.loads((api_out / doc_rel).read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(doc)


def test_api_node_docs_validate_against_node_schema(api_out):
    """Every per-node file validates against node.schema.json."""
    schema = json.loads((api_out / "schema" / "node.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    for node_file in (api_out / "nodes").iterdir():
        doc = json.loads(node_file.read_text(encoding="utf-8"))
        validator.validate(doc)


def test_api_schema_literals_match_emitted_files(api_out):
    """The in-memory SCHEMA_FILES constants must exactly match what was written to disk."""
    for filename, schema_dict in SCHEMA_FILES.items():
        on_disk = (api_out / "schema" / filename).read_bytes()
        expected = json.dumps(schema_dict, separators=(",", ":"), sort_keys=True).encode("utf-8")
        assert on_disk == expected, f"schema/{filename} on disk differs from SCHEMA_FILES constant"


# ---------------------------------------------------------------------------
# _invert_column_lineage unit tests
# ---------------------------------------------------------------------------


def test_invert_column_lineage_empty():
    assert _invert_column_lineage({}) == {}


def test_invert_column_lineage_single_edge():
    flat = {"model.shop.orders.amount": [{"node": "model.shop.stg_orders", "column": "amount"}]}
    result = _invert_column_lineage(flat)
    assert result == {
        "model.shop.stg_orders.amount": [{"node": "model.shop.orders", "column": "amount"}]
    }


def test_invert_column_lineage_multiple_downstream_dependents():
    flat = {
        "model.shop.orders.customer_id": [{"node": "model.shop.customers", "column": "id"}],
        "model.shop.summaries.customer_id": [{"node": "model.shop.customers", "column": "id"}],
    }
    result = _invert_column_lineage(flat)
    children = result["model.shop.customers.id"]
    assert len(children) == 2
    assert {"node": "model.shop.orders", "column": "customer_id"} in children
    assert {"node": "model.shop.summaries", "column": "customer_id"} in children


def test_invert_column_lineage_multiple_upstream_sources():
    flat = {
        "model.shop.combined.val": [
            {"node": "model.shop.a", "column": "val"},
            {"node": "model.shop.b", "column": "val"},
        ]
    }
    result = _invert_column_lineage(flat)
    assert result["model.shop.a.val"] == [{"node": "model.shop.combined", "column": "val"}]
    assert result["model.shop.b.val"] == [{"node": "model.shop.combined", "column": "val"}]


def test_invert_is_linear_in_edges():
    flat = {
        f"model.shop.m{i}.col": [{"node": "source.shop.s", "column": "col"}] for i in range(100)
    }
    result = _invert_column_lineage(flat)
    assert len(result["source.shop.s.col"]) == 100


# ---------------------------------------------------------------------------
# columnLineageMeta in build_data
# ---------------------------------------------------------------------------


def test_build_data_has_column_lineage_meta(monkeypatch, config, fake_manifest, fake_catalog):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    data = ReportBuilder(config).build_data()
    assert "columnLineageMeta" in data
    assert "skipped" in data["columnLineageMeta"]
    assert isinstance(data["columnLineageMeta"]["skipped"], int)


# ---------------------------------------------------------------------------
# column-lineage.json — new whole-graph file
# ---------------------------------------------------------------------------


def test_generate_writes_column_lineage_json(api_out):
    assert (api_out / "column-lineage.json").is_file()


def test_column_lineage_json_shape(api_out):
    doc = json.loads((api_out / "column-lineage.json").read_text(encoding="utf-8"))
    assert "$schema" in doc
    assert "skipped" in doc
    assert isinstance(doc["skipped"], int)
    assert "edges" in doc
    assert isinstance(doc["edges"], dict)
    assert "children" in doc
    assert isinstance(doc["children"], dict)


def test_column_lineage_json_schema_pointer_exists(api_out):
    doc = json.loads((api_out / "column-lineage.json").read_text(encoding="utf-8"))
    schema_path = api_out / doc["$schema"]
    assert schema_path.is_file()


def test_column_lineage_json_validates_against_schema(api_out):
    schema = json.loads(
        (api_out / "schema" / "column-lineage.schema.json").read_text(encoding="utf-8")
    )
    doc = json.loads((api_out / "column-lineage.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(doc)


def test_column_lineage_edges_match_data_dict(monkeypatch, config, fake_manifest, fake_catalog):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    out = Path(ReportBuilder(config).generate())
    data = json.loads((out / "dbdocs-data.json").read_text(encoding="utf-8"))
    doc = json.loads((out / "api" / "v1" / "column-lineage.json").read_text(encoding="utf-8"))
    assert doc["edges"] == data["columnLineage"]


def test_column_lineage_children_is_inversion_of_edges(
    monkeypatch, config, fake_manifest, fake_catalog
):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    out = Path(ReportBuilder(config).generate())
    data = json.loads((out / "dbdocs-data.json").read_text(encoding="utf-8"))
    doc = json.loads((out / "api" / "v1" / "column-lineage.json").read_text(encoding="utf-8"))
    assert doc["children"] == _invert_column_lineage(data["columnLineage"])


def test_column_lineage_skipped_matches_meta(monkeypatch, config, fake_manifest, fake_catalog):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    out = Path(ReportBuilder(config).generate())
    data = json.loads((out / "dbdocs-data.json").read_text(encoding="utf-8"))
    doc = json.loads((out / "api" / "v1" / "column-lineage.json").read_text(encoding="utf-8"))
    assert doc["skipped"] == data["columnLineageMeta"]["skipped"]


# ---------------------------------------------------------------------------
# column_referenced_by slice in per-node files
# ---------------------------------------------------------------------------


def test_api_per_node_has_column_referenced_by(api_out):
    for node_file in (api_out / "nodes").iterdir():
        doc = json.loads(node_file.read_text(encoding="utf-8"))
        assert "column_referenced_by" in doc, f"{node_file.name} missing column_referenced_by"
        assert isinstance(doc["column_referenced_by"], dict)


def test_api_per_node_column_referenced_by_slice(monkeypatch, config, fake_manifest, fake_catalog):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    out = Path(ReportBuilder(config).generate())
    data = json.loads((out / "dbdocs-data.json").read_text(encoding="utf-8"))
    inverted = _invert_column_lineage(data["columnLineage"])
    for node_id in data["nodes"]:
        node_file = out / "api" / "v1" / "nodes" / f"{node_id}.json"
        doc = json.loads(node_file.read_text(encoding="utf-8"))
        expected = {k: v for k, v in inverted.items() if k.startswith(f"{node_id}.")}
        assert doc["column_referenced_by"] == expected


def test_api_node_docs_with_column_referenced_by_validate_against_schema(api_out):
    schema = json.loads((api_out / "schema" / "node.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    for node_file in (api_out / "nodes").iterdir():
        doc = json.loads(node_file.read_text(encoding="utf-8"))
        validator.validate(doc)


# ---------------------------------------------------------------------------
# versioned flag in metadata
# ---------------------------------------------------------------------------


def test_generate_sets_versioned_false_by_default(monkeypatch, config, fake_manifest, fake_catalog):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    out = Path(ReportBuilder(config).generate())
    data = json.loads((out / "dbdocs-data.json").read_text(encoding="utf-8"))
    assert data["metadata"]["versioned"] is False


def test_generate_sets_versioned_true_when_requested(
    monkeypatch, config, fake_manifest, fake_catalog
):
    _patch_boundaries(monkeypatch, fake_manifest, fake_catalog)
    out = Path(ReportBuilder(config).generate(versioned=True))
    data = json.loads((out / "dbdocs-data.json").read_text(encoding="utf-8"))
    assert data["metadata"]["versioned"] is True
