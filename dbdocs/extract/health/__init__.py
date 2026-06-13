"""Project Health Check — the six dbt-project-evaluator dimensions.

The public entry point is :class:`HealthCheckExtractor`, which composes the
manifest-derived rule engine (:mod:`dbdocs.extract.health.dimensions` +
:mod:`dbdocs.extract.health.rules`) with the optional ``run_results.json``
per-test detail.  Custom rules can be registered via
:func:`dbdocs.extract.health.rules.register_rule` (see the plugin docs).
"""

from dbdocs.extract.health.extractor import HealthCheckExtractor

__all__ = ["HealthCheckExtractor"]
