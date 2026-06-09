"""Integration: run the real generate pipeline against real dbt artifacts.

Unlike the unit tests, these do **not** mock dbterd/sqlglot. They stage the
bundled jaffle-shop (manifest schema v12) artifacts into a throwaway dbt project
and exercise ``ReportBuilder.generate()`` end to end, asserting on the actual
generated ``index.html`` + the external ``dbdocs-data.json.gz`` payload the SPA
fetches.
"""

import dataclasses
import gzip
import json
from pathlib import Path

from dbdocs.core.config import DbDocsConfig
from dbdocs.site.builder import ReportBuilder

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_CONFIG = REPO_ROOT / "docs" / "dbdocs-demo.yml"


def _site_data(site: Path) -> dict:
    """The data dict the SPA loads — read back from the gzipped payload."""
    return json.loads(gzip.decompress((site / "dbdocs-data.json.gz").read_bytes()))


def test_generate_produces_self_contained_site(jaffle_project):
    cfg = DbDocsConfig(target_dir="target", output_dir="site", site_name="Jaffle Shop Docs")
    out = ReportBuilder(cfg).generate()

    site = Path(out)
    index = site / "index.html"
    assert index.is_file()
    assert (site / "assets" / "js" / "app.js").is_file()
    # The React Flow graph bundle is staged (no more Mermaid).
    assert (site / "assets" / "graph" / "index.js").is_file()

    html = index.read_text(encoding="utf-8")
    # Data is external (not inlined): the HTML stays small, the marker is gone.
    assert "window.dbdocsData" not in html
    assert "<!-- DBDOCS_DATA -->" not in html
    assert "assets/graph/index.js" in html
    assert "mermaid" not in html

    data = _site_data(site)
    assert data["metadata"]["site_name"] == "Jaffle Shop Docs"
    assert data["metadata"]["adapter_type"] == "snowflake"
    # jaffle-shop: 15 models + 6 sources + 6 seeds.
    assert data["metadata"]["counts"]["model"] == 15
    assert data["metadata"]["counts"]["source"] == 6

    # Structured ERD: nodes (entities with columns) + foreign-key edges.
    assert data["erd"]["nodes"]
    assert all("columns" in n for n in data["erd"]["nodes"])
    assert isinstance(data["erd"]["edges"], list)

    # Column-level lineage resolves the customers model.
    customer_cols = [
        k for k in data["columnLineage"] if k.startswith("model.jaffle_shop.customers.")
    ]
    assert customer_cols
    assert "model.jaffle_shop.customers.customer_id" in data["columnLineage"]

    # DB/schema nav tree is populated.
    assert data["tree"]["byDatabase"]


def test_generate_is_idempotent(jaffle_project):
    cfg = DbDocsConfig(target_dir="target", output_dir="site")
    ReportBuilder(cfg).generate()
    ReportBuilder(cfg).generate()  # second pass over a populated site/
    assert (Path(jaffle_project) / "site" / "index.html").is_file()


def test_demo_config_generates_a_valid_site(tmp_path, monkeypatch):
    """Headless verify the live-demo build: the real ``docs/dbdocs-demo.yml``
    config + committed ``tests/fixtures/jaffle_shop`` artifacts must produce a
    valid site.

    The demo config's ``target_dir`` (``tests/fixtures/jaffle_shop``) and
    ``output_dir`` (``docs/demo``) are relative, resolved against the cwd, so the
    build runs from the repo root. The output is redirected to a throwaway dir so
    the real (gitignored) ``docs/demo`` is never touched.
    """
    cfg = DbDocsConfig.load(DEMO_CONFIG)
    cfg = dataclasses.replace(cfg, output_dir=str(tmp_path / "demo"))
    monkeypatch.chdir(REPO_ROOT)

    out = ReportBuilder(cfg).generate()

    site = Path(out)
    index = site / "index.html"
    assert index.is_file()
    assert (site / "assets" / "js" / "app.js").is_file()
    assert (site / "assets" / "graph" / "index.js").is_file()

    html = index.read_text(encoding="utf-8")
    assert "window.dbdocsData" not in html

    data = _site_data(site)
    # Display metadata comes straight from the demo config.
    assert data["metadata"]["site_name"] == "dbdocs demo — jaffle_shop"
    assert data["metadata"]["adapter_type"] == "snowflake"
    # Same jaffle-shop artifacts: 15 models + 6 sources.
    assert data["metadata"]["counts"]["model"] == 15
    assert data["metadata"]["counts"]["source"] == 6

    # The README named in the demo config is rendered onto the overview.
    assert data["readme"]

    # The demo config narrows the ERD via dbterd select; the structured ERD
    # still resolves entities with columns + a foreign-key edge list.
    assert data["erd"]["nodes"]
    assert all("columns" in n for n in data["erd"]["nodes"])
    assert isinstance(data["erd"]["edges"], list)

    # Column-level lineage and the nav tree are populated end to end.
    assert "model.jaffle_shop.customers.customer_id" in data["columnLineage"]
    assert data["tree"]["byDatabase"]
