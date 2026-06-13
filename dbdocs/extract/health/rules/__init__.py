"""Manifest-derived project-health rules (the six dbt-project-evaluator dimensions).

These reimplement the well-known `dbt-project-evaluator
<https://dbt-labs.github.io/dbt-project-evaluator/>`_ rules **from the static
``manifest.json`` we already load** — no extra dbt package, no warehouse, no
intermediate models. Each rule is ``(graph) -> list[dict]`` returning one finding
per flagged node; the rules live one module per dimension (``modeling``,
``testing``, …), the shared finding shape + constants in :mod:`base`, and the
registry + plugin loading in :mod:`registry`.

A finding is ``{rule, node, node_type, message, docs_url}``. Thresholds mirror
DPE's defaults (``model_fanout`` > 3, ``too_many_joins`` ≥ 7,
``chained_view_dependencies`` ≥ 4), overridable via ``dbdocs.yml`` →
``health.thresholds``.

**Plugins.** Register custom rules with :func:`register_rule` (a decorator or a
direct call); installed packages ship rules via the ``dbdocs.health_rules`` entry
point, and a project can point ``health.rules_module`` at a module that registers
rules on import. ``DimensionAnalyzer`` calls the loaders before iterating.

This package's ``__init__`` is a thin facade — it only re-exports the public API
of :mod:`base` and :mod:`registry`; no implementation lives here.
"""

from dbdocs.extract.health.rules.base import DEFAULT_THRESHOLDS, NON_PHYSICAL, docs_url, finding
from dbdocs.extract.health.rules.dimensions.documentation import (
    documentation_coverage,
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
    downstream_models_dependent_on_source,
    duplicate_sources,
    hard_coded_references,
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
    test_directories,
)
from dbdocs.extract.health.rules.dimensions.testing import (
    missing_primary_key_tests,
    missing_source_freshness,
    test_coverage,
)
from dbdocs.extract.health.rules.registry import (
    DIMENSION_RULES,
    ENTRY_POINT_GROUP,
    load_entry_point_rules,
    load_rules_module,
    register_rule,
    reset_rules,
)

__all__ = [
    # base
    "DEFAULT_THRESHOLDS",
    "NON_PHYSICAL",
    "finding",
    "docs_url",
    # registry / plugins
    "DIMENSION_RULES",
    "ENTRY_POINT_GROUP",
    "register_rule",
    "reset_rules",
    "load_entry_point_rules",
    "load_rules_module",
    # rule functions (re-exported for direct access / testing)
    "test_coverage",
    "missing_primary_key_tests",
    "missing_source_freshness",
    "direct_join_to_source",
    "downstream_models_dependent_on_source",
    "duplicate_sources",
    "hard_coded_references",
    "model_fanout",
    "multiple_sources_joined",
    "rejoining_of_upstream_concepts",
    "root_models",
    "source_fanout",
    "staging_dependent_on_staging",
    "staging_dependent_on_marts_or_intermediate",
    "unused_sources",
    "too_many_joins",
    "documentation_coverage",
    "undocumented_models",
    "undocumented_sources",
    "undocumented_source_tables",
    "model_naming_conventions",
    "model_directories",
    "source_directories",
    "test_directories",
    "chained_view_dependencies",
    "exposure_parents_materializations",
    "public_models_without_contracts",
    "undocumented_public_models",
    "exposures_dependent_on_private_models",
]
