"""Pick the report builder for the configured artifact source."""

import importlib

from dbdocs.core.config import DbDocsConfig
from dbdocs.core.exceptions import DbDocsConfigError
from dbdocs.site.builder import ReportBuilder

INFO_SCHEMA_BUILDER_MODULE = "dbdocs.sources.info_schema.builder"


def builder_for(config: DbDocsConfig) -> ReportBuilder:
    """``ReportBuilder`` for the JSON artifacts; the info-schema builder when opted in."""
    if not config.info_schema:
        return ReportBuilder(config)
    try:
        module = importlib.import_module(INFO_SCHEMA_BUILDER_MODULE)
    except ModuleNotFoundError as exc:
        raise DbDocsConfigError(
            "info_schema needs DuckDB: install it with `pip install 'dbdocs[info-schema]'`."
        ) from exc
    return module.InfoSchemaReportBuilder(config)
