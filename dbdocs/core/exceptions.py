"""dbdocs exception types.

Multiple exception classes may share one file (per the project's Python style).
"""


class DbDocsError(Exception):
    """Base class for all dbdocs errors."""


class DbDocsConfigError(DbDocsError):
    """Raised when dbdocs.yml is malformed or holds invalid values."""


class LineageError(DbDocsError):
    """Raised when column-level lineage can't be parsed for a model.

    Always caught per-model by the extractor so one unparseable model never
    fails the whole ``generate`` — the model is skipped and logged instead.
    """


class DeployError(DbDocsError):
    """Raised when a versioned deploy step (e.g. the git push) fails."""
