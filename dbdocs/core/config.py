from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

import yaml

from dbdocs.core.exceptions import DbDocsConfigError

DEFAULT_CONFIG_FILENAME = "dbdocs.yml"


@dataclass
class DbDocsConfig:
    """Site configuration for a dbdocs build.

    Loaded from a ``dbdocs.yml`` in the working directory; every field has a
    default so the file is optional. ``version`` is intentionally absent — it is
    a ``deploy`` CLI argument, not site config.

    ``target_dir`` is where the dbt artifacts are read from; ``output_dir`` is
    where the generated self-contained site is written.
    """

    site_name: str = "dbt docs"
    site_url: str = "https://github.com/datnguye/dbt-docs"
    site_author: str = "Dat Nguyen"
    site_description: str = "Alternative dbt documentation site"
    repo_name: str = "datnguye/dbt-docs"
    repo_url: str = "https://github.com/datnguye/dbt-docs"
    project_name: str = "dbt docs"
    #: The footer's Buy-me-a-coffee badge shows by default; set false to hide it.
    show_buy_me_a_coffee: bool = True
    #: Project README rendered on the overview (relative to the working dir). Set
    #: empty to omit the README section. Missing file ⇒ section simply absent.
    readme: str = "README.md"
    target_dir: str = "target"
    #: Where the generated site is written. Nested under the dbt ``target/`` by
    #: default so docs sit alongside the artifacts they're built from.
    output_dir: str = "target/site"
    #: SQL dialect for column-lineage parsing; ``None`` ⇒ derive from the
    #: artifact's ``adapter_type`` (e.g. snowflake, bigquery, postgres).
    dialect: "str | None" = None
    #: Alias the SPA's version switcher treats as the default landing version.
    default_version: str = "latest"
    #: dbterd ERD options (``algo``, ``entity_name_format``, ``select``,
    #: ``resource_type``, …) passed straight to ``DbtErd``. Configured here so the
    #: ERD shape lives in ``dbdocs.yml`` rather than a separate ``.dbterd.yml``.
    dbterd: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: "str | Path | None" = None) -> "DbDocsConfig":
        """Load config from ``path`` (or ``./dbdocs.yml``); all-defaults if absent."""
        config_path = Path(path) if path is not None else Path.cwd() / DEFAULT_CONFIG_FILENAME
        if not config_path.is_file():
            return cls()

        try:
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise DbDocsConfigError(f"Could not parse {config_path}: {exc}") from exc

        if raw is None:
            return cls()
        if not isinstance(raw, dict):
            raise DbDocsConfigError(
                f"{config_path} must contain a mapping, got {type(raw).__name__}"
            )

        known = {f.name for f in fields(cls)}
        unknown = set(raw) - known
        if unknown:
            raise DbDocsConfigError(
                f"Unknown keys in {config_path}: {', '.join(sorted(unknown))}. "
                f"Allowed keys: {', '.join(sorted(known))}."
            )
        return cls(**raw)

    #: Build-control fields that are not part of the site's display metadata.
    _NON_METADATA_FIELDS = (
        "target_dir",
        "output_dir",
        "dialect",
        "default_version",
        "dbterd",
        "readme",
    )

    def render_context(self) -> dict:
        """The site display metadata injected into the SPA's ``metadata`` block.

        Excludes build-control fields (where artifacts are read, where the site
        is written, the lineage dialect override) that aren't site metadata.
        """
        context = asdict(self)
        for field_name in self._NON_METADATA_FIELDS:
            context.pop(field_name, None)
        return context

    @property
    def target_path(self) -> str:
        """Absolute path to the dbt target/ dir where the artifacts live.

        A relative ``target_dir`` is resolved against the current working
        directory **at access time** — this is intentional and must stay aligned
        with dbterd's ``DbtErd``, which also reads artifacts from ``./target``
        relative to the cwd. An absolute ``target_dir`` is returned unchanged.
        """
        return str(Path.cwd() / self.target_dir)

    @property
    def output_path(self) -> str:
        """Absolute path to the dir the generated site is written into.

        Resolved against the cwd at access time, mirroring ``target_path`` — a
        relative ``output_dir`` follows the working directory, an absolute one is
        returned unchanged.
        """
        return str(Path.cwd() / self.output_dir)
