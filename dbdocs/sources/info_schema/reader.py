"""Read dbt 2.0's parquet information schema (``dbt.*`` / ``dbt_rt.*`` tables)."""

from pathlib import Path

import duckdb

from dbdocs.core.exceptions import DbDocsConfigError

SUPPORTED_SCHEMA_VERSION = 1


class InfoSchemaReader:
    """Rows of the information-schema parquet files under ``directory``.

    A table with no parquet file reads as ``[]``. Construction fails unless the
    directory exists and ``dbt.project.schema_version`` is the supported one.
    """

    def __init__(self, directory: "str | Path") -> None:
        self.directory = Path(directory)
        if not self.directory.is_dir():
            raise DbDocsConfigError(f"info_schema directory not found: {self.directory}")
        project = self.table("dbt.project")
        version = project[0].get("schema_version") if project else None
        if version != SUPPORTED_SCHEMA_VERSION:
            raise DbDocsConfigError(
                f"Unsupported info_schema schema_version {version!r} in {self.directory} "
                f"(supported: {SUPPORTED_SCHEMA_VERSION})."
            )

    def table(self, name: str) -> "list[dict]":
        path = self.directory / f"{name}.parquet"
        if not path.is_file():
            return []
        cursor = duckdb.connect().execute("SELECT * FROM read_parquet(?)", [str(path)])
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
