"""Integration: run the real generate pipeline against real dbt artifacts.

Unlike the unit tests, these do **not** mock dbterd/sqlglot. They stage the
bundled jaffle-shop (manifest schema v12) artifacts into a throwaway dbt project
and exercise ``ReportBuilder.generate()`` end to end, asserting on the actual
generated ``index.html`` + injected data dict.
"""

import base64
import json
from pathlib import Path

from dbdocs.core.config import DbDocsConfig
from dbdocs.site.builder import ReportBuilder


def _injected_data(index_html: str) -> dict:
    payload = index_html.split('atob("')[1].split('")')[0]
    return json.loads(base64.b64decode(payload).decode("utf-8"))


def test_generate_produces_self_contained_site(jaffle_project):
    cfg = DbDocsConfig(target_dir="target", output_dir="site", site_name="Jaffle Shop Docs")
    out = ReportBuilder(cfg).generate()

    site = Path(out)
    index = site / "index.html"
    assert index.is_file()
    assert (site / "assets" / "app.js").is_file()
    # The React Flow graph bundle is staged (no more Mermaid).
    assert (site / "assets" / "graph" / "index.js").is_file()

    html = index.read_text(encoding="utf-8")
    assert "window.dbdocsData" in html
    assert "assets/graph/index.js" in html
    assert "mermaid" not in html

    data = _injected_data(html)
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
