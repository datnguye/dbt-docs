"""Integration: run the real generate pipeline against the larger artifacts.

The ``big_project`` fixture (96 models, 149 tests, snowflake, manifest schema
v12) exercises ``ReportBuilder.generate()`` end to end at a scale the jaffle-shop
fixture doesn't reach — many more entities and a wide foreign-key ERD — asserting
on the actual ``dbdocs-data.json.gz`` payload the SPA fetches.
"""

import gzip
import json
from pathlib import Path

from dbdocs.core.config import DbDocsConfig
from dbdocs.site.builder import ReportBuilder


def _site_data(site: Path) -> dict:
    """The data dict the SPA loads — read back from the gzipped payload."""
    return json.loads(gzip.decompress((site / "dbdocs-data.json.gz").read_bytes()))


def test_generate_big_project_site(big_project):
    cfg = DbDocsConfig(target_dir="target", output_dir="site", site_name="Big Project Docs")
    out = ReportBuilder(cfg).generate()

    site = Path(out)
    assert (site / "index.html").is_file()
    assert (site / "assets" / "graph" / "index.js").is_file()

    data = _site_data(site)
    assert data["metadata"]["site_name"] == "Big Project Docs"
    assert data["metadata"]["adapter_type"] == "snowflake"
    assert data["metadata"]["counts"]["model"] == 96

    assert len(data["erd"]["nodes"]) == 96
    assert all("columns" in n for n in data["erd"]["nodes"])
    assert data["erd"]["edges"]

    assert data["tree"]["byDatabase"]

    health = data["health"]
    assert health["enabled"] is True
    assert set(health["dimensions"]) == {
        "testing",
        "modeling",
        "documentation",
        "structure",
        "performance",
        "governance",
    }
    assert health["testResults"] is None


def test_generate_big_project_is_idempotent(big_project):
    cfg = DbDocsConfig(target_dir="target", output_dir="site")
    ReportBuilder(cfg).generate()
    ReportBuilder(cfg).generate()
    assert (Path(big_project) / "site" / "index.html").is_file()
