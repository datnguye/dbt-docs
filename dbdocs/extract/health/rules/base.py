"""Shared building blocks for the per-dimension health rules.

Public API for rule authors (built-in and plugin): :func:`finding` to emit a
finding, plus the layout constants the rules read. The package ``__init__``
assembles the dimension modules into ``DIMENSION_RULES`` and owns the registry.
"""

# DPE rule docs live one page per category; build the per-rule anchor from these.
_RULES_BASE = "https://dbt-labs.github.io/dbt-project-evaluator/latest/rules"

# Default thresholds (DPE defaults). Overridable via ``dbdocs.yml`` →
# ``health.thresholds`` and read at run time through ``graph.threshold(...)``.
DEFAULT_THRESHOLDS = {
    "model_fanout": 3,
    "too_many_joins": 7,
    "chained_view_dependencies": 4,
}

# Materializations that are *not* a physical table (for chained-view detection).
NON_PHYSICAL = {"view", "ephemeral"}

# Model-layer prefixes (DPE naming conventions).
LAYER_PREFIXES = {
    "staging": ("stg_",),
    "intermediate": ("int_",),
    "marts": ("fct_", "dim_"),
}


def docs_url(category: str, rule: str) -> str:
    """The DPE docs URL for a rule under *category* (anchor = the rule name)."""
    return f"{_RULES_BASE}/{category}/#{rule.replace('_', '-')}"


def finding(rule: str, category: str, node: str, node_type: str, message: str) -> dict:
    """Build a health finding dict (the unit every rule returns)."""
    return {
        "rule": rule,
        "node": node,
        "node_type": node_type,
        "message": message,
        "docs_url": docs_url(category, rule),
    }
