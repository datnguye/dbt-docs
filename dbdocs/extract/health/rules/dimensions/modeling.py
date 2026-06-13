"""Modeling — DAG shape + layering best-practice rules.

Each rule is ``(graph) -> list[dict]``; see ``dbdocs.extract.health.rules``
for the shared finding shape and the registry that assembles these.
"""

import re
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.scope import build_scope

from dbdocs.extract.health.rules.base import finding

# ``ManifestGraph`` annotations are strings (forward ref) to avoid a circular
# import (rules ← graph ← analyzer); resolved lazily by the type checker only.
ManifestGraph = Any

# A ``{{ ref(...) }}`` / ``{{ source(...) }}`` call is rewritten to a uniquely
# numbered sentinel table before parsing (``__dbt_ref_0__``, ``__dbt_ref_1__``, …)
# — unique so sqlglot's scope analysis doesn't choke on a repeated alias — so any
# *other* real table left in the SQL is a hard-coded relation. Any remaining
# ``{{ ... }}`` macro is blanked so it doesn't masquerade as a table.
_REF_SENTINEL_PREFIX = "__dbt_ref_"
_REF_OR_SOURCE = re.compile(r"{{[-\s]*(?:ref|source)\s*\(.*?\)[-\s]*}}", re.IGNORECASE | re.DOTALL)
_OTHER_JINJA = re.compile(r"{[{%].*?[%}]}", re.DOTALL)


def direct_join_to_source(graph: "ManifestGraph") -> "list[dict]":
    """Models that ref a model AND a source in the same query (missing staging)."""
    out = []
    for model in graph.models:
        parents = graph.parents(model.unique_id)
        has_model = any(p.startswith("model.") for p in parents)
        has_source = any(p.startswith("source.") for p in parents)
        if has_model and has_source:
            out.append(
                finding(
                    "direct_join_to_source",
                    "modeling",
                    model.unique_id,
                    "model",
                    "References a model and a source in the same query — add a staging model.",
                )
            )
    return out


def duplicate_sources(graph: "ManifestGraph") -> "list[dict]":
    """Multiple source definitions pointing at the same database.schema.identifier."""
    by_relation: dict[tuple, list[str]] = {}
    for src in graph.sources:
        key = (
            str(getattr(src, "database", "")).lower(),
            str(getattr(src, "schema_", "")).lower(),
            str(getattr(src, "identifier", None) or getattr(src, "name", "")).lower(),
        )
        by_relation.setdefault(key, []).append(src.unique_id)
    out = []
    for ids in by_relation.values():
        if len(ids) > 1:
            for uid in ids:
                out.append(
                    finding(
                        "duplicate_sources",
                        "modeling",
                        uid,
                        "source",
                        "Multiple source definitions point at the same database location.",
                    )
                )
    return out


def model_fanout(graph: "ManifestGraph") -> "list[dict]":
    """Models with more than the ``model_fanout`` threshold of direct model children."""
    limit = graph.threshold("model_fanout")
    out = []
    for model in graph.models:
        children = [c for c in graph.children(model.unique_id) if c.startswith("model.")]
        if len(children) > limit:
            out.append(
                finding(
                    "model_fanout",
                    "modeling",
                    model.unique_id,
                    "model",
                    f"{len(children)} direct model children (> {limit}) — "
                    "consider pushing logic into BI or consolidating.",
                )
            )
    return out


def multiple_sources_joined(graph: "ManifestGraph") -> "list[dict]":
    """Models referencing 2+ source nodes (staging should be 1:1 with a source)."""
    out = []
    for model in graph.models:
        sources = [p for p in graph.parents(model.unique_id) if p.startswith("source.")]
        if len(sources) > 1:
            out.append(
                finding(
                    "multiple_sources_joined",
                    "modeling",
                    model.unique_id,
                    "model",
                    f"Joins {len(sources)} sources — split into one staging model per source.",
                )
            )
    return out


def rejoining_of_upstream_concepts(graph: "ManifestGraph") -> "list[dict]":
    """A → B, A → C, B → C where B has C as its only child (a redundant DAG loop)."""
    out = []
    for b in graph.models:
        b_children = [c for c in graph.children(b.unique_id) if c.startswith("model.")]
        if len(b_children) != 1:
            continue
        c = b_children[0]
        b_parents = set(graph.parents(b.unique_id))
        c_parents = set(graph.parents(c))
        # A common parent feeding both B and C directly is the rejoin.
        if b_parents & c_parents:
            out.append(
                finding(
                    "rejoining_of_upstream_concepts",
                    "modeling",
                    b.unique_id,
                    "model",
                    "Its only child also depends on a shared upstream — a redundant DAG loop.",
                )
            )
    return out


def downstream_models_dependent_on_source(graph: "ManifestGraph") -> "list[dict]":
    """Non-staging models that ref a source directly (only staging should touch sources)."""
    out = []
    for model in graph.models:
        if graph.layer(model) == "staging":
            continue
        if any(p.startswith("source.") for p in graph.parents(model.unique_id)):
            out.append(
                finding(
                    "downstream_models_dependent_on_source",
                    "modeling",
                    model.unique_id,
                    "model",
                    "A non-staging model selects from a source — route it through a staging model.",
                )
            )
    return out


def _number_refs(raw_code: str) -> str:
    """Replace each ref()/source() jinja call with a uniquely numbered sentinel."""
    out = []
    last = 0
    for index, match in enumerate(_REF_OR_SOURCE.finditer(raw_code)):
        out.append(raw_code[last : match.start()])
        out.append(f"{_REF_SENTINEL_PREFIX}{index}__")
        last = match.end()
    out.append(raw_code[last:])
    return "".join(out)


def _hard_coded_relations(raw_code: str) -> "list[str]":
    """Real table names a model's raw SQL selects from outside ref()/source().

    dbt references are jinja (``{{ ref(...) }}`` / ``{{ source(...) }}``), so they
    are rewritten to uniquely numbered sentinel tables before parsing (so sqlglot's
    scope analysis doesn't choke on a repeated alias); any other real table its
    scope analysis finds is a hard-coded relation. CTEs are excluded by walking
    ``scope.selected_sources`` rather than every ``exp.Table``. Unparseable SQL
    yields nothing (fail-soft — one model never sinks the pass).
    """
    sql = _number_refs(raw_code)
    sql = _OTHER_JINJA.sub(" ", sql)
    if not sql.strip():
        return []
    try:
        # parse_one returns a node or raises for non-empty input (empty is guarded
        # above); build_scope returns None for a non-query statement (DDL/SET).
        root = build_scope(sqlglot.parse_one(sql))
        if root is None:
            return []
        relations = [
            source.sql()
            for scope in root.traverse()
            for _alias, (_node, source) in scope.selected_sources.items()
            if isinstance(source, exp.Table) and not source.name.startswith(_REF_SENTINEL_PREFIX)
        ]
    except SqlglotError:  # OptimizeError (e.g. duplicate alias) is a SqlglotError subclass.
        return []
    return relations


def hard_coded_references(graph: "ManifestGraph") -> "list[dict]":
    """Models whose SQL selects from a literal relation instead of ref()/source()."""
    out = []
    for model in graph.models:
        relations = _hard_coded_relations(str(getattr(model, "raw_code", "") or ""))
        if relations:
            shown = ", ".join(sorted(set(relations)))
            out.append(
                finding(
                    "hard_coded_references",
                    "modeling",
                    model.unique_id,
                    "model",
                    f"Hard-coded relation(s) {shown} — replace with ref()/source().",
                )
            )
    return out


def root_models(graph: "ManifestGraph") -> "list[dict]":
    """Models with zero parents (no ref/source) — untraceable lineage."""
    out = []
    for model in graph.models:
        if not graph.parents(model.unique_id):
            out.append(
                finding(
                    "root_models",
                    "modeling",
                    model.unique_id,
                    "model",
                    "No refs or sources — cannot be traced to a declared origin.",
                )
            )
    return out


def source_fanout(graph: "ManifestGraph") -> "list[dict]":
    """Sources referenced directly by more than one model."""
    out = []
    for src in graph.sources:
        children = [c for c in graph.children(src.unique_id) if c.startswith("model.")]
        if len(children) > 1:
            out.append(
                finding(
                    "source_fanout",
                    "modeling",
                    src.unique_id,
                    "source",
                    f"Referenced by {len(children)} models — route all but one through staging.",
                )
            )
    return out


def staging_dependent_on_staging(graph: "ManifestGraph") -> "list[dict]":
    """Staging models that depend on another staging *model* (not a source)."""
    out = []
    for model in graph.models:
        if graph.layer(model) != "staging":
            continue
        for parent in graph.parents(model.unique_id):
            if not parent.startswith("model."):
                continue  # sources live in a staging/ folder too — ignore them here
            pnode = graph.node(parent)
            if pnode is not None and graph.layer(pnode) == "staging":
                out.append(
                    finding(
                        "staging_dependent_on_staging",
                        "modeling",
                        model.unique_id,
                        "model",
                        "A staging model depends on another staging model.",
                    )
                )
                break
    return out


def staging_dependent_on_marts_or_intermediate(graph: "ManifestGraph") -> "list[dict]":
    """Staging models that depend on an intermediate or marts *model*."""
    out = []
    for model in graph.models:
        if graph.layer(model) != "staging":
            continue
        for parent in graph.parents(model.unique_id):
            if not parent.startswith("model."):
                continue
            pnode = graph.node(parent)
            if pnode is not None and graph.layer(pnode) in ("intermediate", "marts"):
                out.append(
                    finding(
                        "staging_dependent_on_marts_or_intermediate",
                        "modeling",
                        model.unique_id,
                        "model",
                        "A staging model depends on an intermediate/marts model.",
                    )
                )
                break
    return out


def unused_sources(graph: "ManifestGraph") -> "list[dict]":
    """Source definitions with zero children (orphaned YAML)."""
    out = []
    for src in graph.sources:
        if not graph.children(src.unique_id):
            out.append(
                finding(
                    "unused_sources",
                    "modeling",
                    src.unique_id,
                    "source",
                    "Declared but never referenced — remove the unused source.",
                )
            )
    return out


def too_many_joins(graph: "ManifestGraph") -> "list[dict]":
    """Models referencing the ``too_many_joins`` threshold+ of distinct upstream nodes."""
    limit = graph.threshold("too_many_joins")
    out = []
    for model in graph.models:
        parents = graph.parents(model.unique_id)
        if len(parents) >= limit:
            out.append(
                finding(
                    "too_many_joins",
                    "modeling",
                    model.unique_id,
                    "model",
                    f"{len(parents)} upstream dependencies (≥ {limit}) — "
                    "split into intermediate models.",
                )
            )
    return out
