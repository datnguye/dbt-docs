import importlib

import pytest

from dbdocs.core.config import DbDocsConfig
from dbdocs.core.exceptions import DbDocsConfigError
from dbdocs.site.builder import ReportBuilder
from dbdocs.sources.factory import builder_for
from dbdocs.sources.info_schema.builder import InfoSchemaReportBuilder


def test_flag_off_returns_plain_report_builder():
    assert type(builder_for(DbDocsConfig())) is ReportBuilder


def test_flag_on_returns_info_schema_builder(info_schema_config):
    assert isinstance(builder_for(info_schema_config), InfoSchemaReportBuilder)


def _duckdb_missing(name):
    raise ModuleNotFoundError("duckdb")


def test_flag_on_without_duckdb_raises(monkeypatch):
    monkeypatch.setattr(importlib, "import_module", _duckdb_missing)
    with pytest.raises(DbDocsConfigError, match="dbdocs\\[info-schema\\]"):
        builder_for(DbDocsConfig(info_schema=True))


def test_flag_on_with_missing_dir_raises(tmp_path):
    config = DbDocsConfig(target_dir=str(tmp_path), info_schema=True)
    with pytest.raises(DbDocsConfigError, match="not found"):
        builder_for(config)
