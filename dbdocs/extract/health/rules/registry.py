"""The health-rule registry + plugin loading.

Assembles the per-dimension rule modules into the live ``DIMENSION_RULES`` mapping
``DimensionAnalyzer`` iterates, and provides the plugin surface: ``register_rule``
(decorator/call), entry-point discovery (``dbdocs.health_rules``), and dotted-path
module loading. The package ``__init__`` re-exports this module's public names.
"""

import importlib
import importlib.metadata
from typing import Any

from dbdocs.core.log import logger
from dbdocs.extract.health.rules.dimensions.documentation import (
    undocumented_models,
    undocumented_source_tables,
    undocumented_sources,
)
from dbdocs.extract.health.rules.dimensions.governance import (
    exposures_dependent_on_private_models,
    public_models_without_contracts,
    undocumented_public_models,
)
from dbdocs.extract.health.rules.dimensions.modeling import (
    direct_join_to_source,
    duplicate_sources,
    model_fanout,
    multiple_sources_joined,
    rejoining_of_upstream_concepts,
    root_models,
    source_fanout,
    staging_dependent_on_marts_or_intermediate,
    staging_dependent_on_staging,
    too_many_joins,
    unused_sources,
)
from dbdocs.extract.health.rules.dimensions.performance import (
    chained_view_dependencies,
    exposure_parents_materializations,
)
from dbdocs.extract.health.rules.dimensions.structure import (
    model_directories,
    model_naming_conventions,
    source_directories,
)
from dbdocs.extract.health.rules.dimensions.testing import missing_primary_key_tests, test_coverage

# The built-in rules grouped by dimension, in DPE's published order. These are the
# *built-ins*. ``DIMENSION_RULES`` (below) starts as a deep copy and is what
# ``DimensionAnalyzer`` iterates — plugins append to it via ``register_rule``
# without mutating this baseline.
_BUILTIN_RULES: "dict[str, tuple]" = {
    "testing": (
        test_coverage,
        missing_primary_key_tests,
    ),
    "modeling": (
        direct_join_to_source,
        duplicate_sources,
        model_fanout,
        multiple_sources_joined,
        rejoining_of_upstream_concepts,
        root_models,
        source_fanout,
        staging_dependent_on_staging,
        staging_dependent_on_marts_or_intermediate,
        unused_sources,
        too_many_joins,
    ),
    "documentation": (
        undocumented_models,
        undocumented_sources,
        undocumented_source_tables,
    ),
    "structure": (
        model_naming_conventions,
        model_directories,
        source_directories,
    ),
    "performance": (
        chained_view_dependencies,
        exposure_parents_materializations,
    ),
    "governance": (
        public_models_without_contracts,
        undocumented_public_models,
        exposures_dependent_on_private_models,
    ),
}

#: The live registry ``DimensionAnalyzer`` iterates: built-ins + any registered
#: plugin rules. Lists (not tuples) so ``register_rule`` can append.
DIMENSION_RULES: "dict[str, list]" = {dim: list(rules) for dim, rules in _BUILTIN_RULES.items()}

#: The entry-point group installed packages use to ship custom health rules.
ENTRY_POINT_GROUP = "dbdocs.health_rules"


def register_rule(dimension: str, rule: "Any | None" = None):
    """Register a custom health rule under *dimension* (creating it if new).

    Usable as a decorator (``@register_rule("modeling")``) or a direct call
    (``register_rule("modeling", my_rule)``). A rule is any callable
    ``(graph) -> list[dict]`` returning findings shaped like
    :func:`dbdocs.extract.health.rules.base.finding`'s output. Idempotent:
    registering the same function twice is a no-op, so module re-import (or
    repeated entry-point loads) won't duplicate it.
    """

    def _add(fn):
        bucket = DIMENSION_RULES.setdefault(dimension, [])
        if fn not in bucket:
            bucket.append(fn)
        return fn

    return _add if rule is None else _add(rule)


def reset_rules() -> None:
    """Restore ``DIMENSION_RULES`` to the built-in baseline (drops all plugins)."""
    DIMENSION_RULES.clear()
    DIMENSION_RULES.update({dim: list(rules) for dim, rules in _BUILTIN_RULES.items()})


def load_entry_point_rules() -> None:
    """Discover + load rules from installed packages' ``dbdocs.health_rules`` entry points.

    Each entry point should resolve to a callable that takes no args and performs
    its own ``register_rule`` calls (or to a module that does so on import). A
    failing entry point is logged and skipped — a bad plugin must never sink
    ``generate``.
    """
    try:
        eps = importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
    except TypeError:  # pragma: no cover - Python < 3.10 select-by-group signature
        eps = importlib.metadata.entry_points().get(ENTRY_POINT_GROUP, [])
    for ep in eps:
        try:
            loaded = ep.load()
            if callable(loaded):
                loaded()
        except (ImportError, AttributeError, TypeError, ValueError) as exc:
            logger.warning("Health check: entry-point rule %r failed to load: %s.", ep.name, exc)


def load_rules_module(dotted_path: str) -> None:
    """Import a user module by dotted path so its ``register_rule`` calls run.

    The module registers its rules at import time (via the ``register_rule``
    decorator). Import failure is logged and skipped (fail-soft).
    """
    try:
        importlib.import_module(dotted_path)
    except (ImportError, ValueError) as exc:
        logger.warning("Health check: rules_module %r could not be imported: %s.", dotted_path, exc)
