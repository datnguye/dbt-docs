"""Build the manifest-derived health *dimensions* (the DPE rule engine's host).

``ManifestGraph`` indexes the dbt manifest once — parents/children adjacency,
plus layer / materialization / access / contract helpers — and the rule functions
in :mod:`dbdocs.extract.health.rules` run against it. ``DimensionAnalyzer.analyze()``
runs every rule, groups findings by dimension, and returns the ``dimensions``
block of the health data dict:

    {
      "modeling":      {"issues": N, "checked": M, "findings": [...]},
      "documentation": {...}, "structure": {...}, "performance": {...},
      "governance":    {...},
    }

``checked`` is how many nodes the dimension's rules could apply to (models for
most, models+sources for some) — it gives the SPA a denominator for a score.
Everything is pure + DOM-free; a malformed/empty manifest yields empty dimensions
rather than raising (the caller, ``HealthCheckExtractor``, is fail-soft).
"""

from typing import Any

from dbdocs.core.log import logger
from dbdocs.extract.health.rules import (
    DEFAULT_THRESHOLDS,
    DIMENSION_RULES,
    NON_PHYSICAL,
    load_entry_point_rules,
    load_rules_module,
)


class ManifestGraph:
    """Adjacency + node metadata over a dbt manifest, for the health rules.

    Wraps the dbterd-parsed manifest: ``models``/``sources``/``exposures`` lists,
    a ``parents``/``children`` adjacency built from each node's ``depends_on``, and
    accessors that smooth over where dbt stores a field (``config.materialized``
    vs node, ``config.access`` vs node, ``schema_`` alias, …).
    """

    def __init__(self, manifest: "Any | None", thresholds: "dict | None" = None) -> None:
        nodes = getattr(manifest, "nodes", None)
        self._nodes: dict = nodes if isinstance(nodes, dict) else {}
        sources = getattr(manifest, "sources", None)
        self._sources: dict = sources if isinstance(sources, dict) else {}
        exposures = getattr(manifest, "exposures", None)
        self._exposures: dict = exposures if isinstance(exposures, dict) else {}

        self.models = [n for uid, n in self._nodes.items() if uid.startswith("model.")]
        self.sources = list(self._sources.values())
        self.exposures = list(self._exposures.values())
        # Singular tests are custom-SQL test nodes (no test_metadata); generic
        # tests (unique/not_null/…) carry test_metadata and are excluded.
        self.singular_tests = [
            n
            for uid, n in self._nodes.items()
            if uid.startswith("test.") and getattr(n, "test_metadata", None) is None
        ]

        # Rule thresholds: per-run overrides layered over the DPE defaults.
        self._thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

        self._parents: dict[str, list[str]] = {}
        self._children: dict[str, list[str]] = {}
        self._build_adjacency()

        self._tests_by_model: dict[str, set] = {}
        self._index_tests()

        # Memo for non_physical_chain_depth (O(nodes) across the whole pass).
        self._chain_cache: dict[str, int] = {}

    def threshold(self, name: str) -> "int | float":
        """The configured threshold for *name* (DPE default when unset)."""
        return self._thresholds[name]

    def _build_adjacency(self) -> None:
        """Index parent/child edges from every node + exposure ``depends_on.nodes``."""
        everything = list(self._nodes.values()) + self.exposures
        for node in everything:
            uid = str(getattr(node, "unique_id", "") or "")
            if not uid:
                continue
            depends_on = getattr(node, "depends_on", None)
            parents = list(getattr(depends_on, "nodes", None) or [])
            self._parents[uid] = parents
            for parent in parents:
                self._children.setdefault(parent, []).append(uid)

    def _index_tests(self) -> None:
        """Map each tested node to the set of test types attached to it."""
        for uid, node in self._nodes.items():
            if not uid.startswith("test."):
                continue
            attached = str(getattr(node, "attached_node", "") or "")
            if not attached:
                continue
            metadata = getattr(node, "test_metadata", None)
            test_type = str(getattr(metadata, "name", "") or "") if metadata else "singular"
            self._tests_by_model.setdefault(attached, set()).add(test_type)

    def tests_for(self, unique_id: str) -> set:
        """The set of test types attached to *unique_id* (empty if untested)."""
        return self._tests_by_model.get(unique_id, set())

    # -- adjacency -----------------------------------------------------------

    def parents(self, unique_id: str) -> "list[str]":
        return self._parents.get(unique_id, [])

    def children(self, unique_id: str) -> "list[str]":
        return self._children.get(unique_id, [])

    def node(self, unique_id: str) -> "Any | None":
        """The node object for *unique_id* (model/seed/snapshot or source)."""
        return self._nodes.get(unique_id) or self._sources.get(unique_id)

    # -- node metadata -------------------------------------------------------

    @staticmethod
    def layer(model: Any) -> str:
        """The model's layer (staging/intermediate/marts/other) from its ``fqn``.

        dbt's ``fqn`` is ``[package, ...folders, name]`` — the folder segments name
        the layer. We match the known layer folders anywhere in the fqn so a
        ``marts/finance/`` nesting still resolves to ``marts``.
        """
        fqn = [str(p).lower() for p in (getattr(model, "fqn", None) or [])]
        for layer in ("staging", "intermediate", "marts"):
            if layer in fqn:
                return layer
        # dbt also uses "stg"/"int"/"core"/"mart" folder spellings; map the common ones.
        if "stg" in fqn:
            return "staging"
        if "int" in fqn:
            return "intermediate"
        if "mart" in fqn or "marts" in fqn:
            return "marts"
        return "other"

    @staticmethod
    def materialization(node: Any) -> str:
        """The node's materialization (``config.materialized``), lowercased."""
        config = getattr(node, "config", None)
        materialized = getattr(config, "materialized", None) if config else None
        return str(materialized or "").lower()

    @staticmethod
    def access(model: Any) -> str:
        """The model's access level (``config.access`` or node ``access``)."""
        config = getattr(model, "config", None)
        access = getattr(config, "access", None) if config else None
        access = access or getattr(model, "access", None)
        return str(access or "protected").lower()

    @staticmethod
    def has_source_freshness(source: Any) -> bool:
        """Whether a source has a freshness check: a ``loaded_at_field`` plus a
        ``warn_after``/``error_after`` threshold count."""
        if not str(getattr(source, "loaded_at_field", "") or "").strip():
            return False
        freshness = getattr(source, "freshness", None)
        if freshness is None:
            return False
        for bound in ("warn_after", "error_after"):
            period = getattr(freshness, bound, None)
            if period is not None and getattr(period, "count", None) is not None:
                return True
        return False

    @staticmethod
    def contract_enforced(model: Any) -> bool:
        """Whether the model has an enforced contract (``contract.enforced``)."""
        contract = getattr(model, "contract", None)
        return bool(getattr(contract, "enforced", False)) if contract else False

    def non_physical_chain_depth(self, unique_id: str) -> int:
        """Longest chain of consecutive non-physical (view/ephemeral) ancestors + self.

        Counts this model plus the longest run of view/ephemeral models directly
        upstream; a table/source ancestor (or a model boundary) stops the chain.
        Mirrors DPE's ``chained_view_dependencies`` distance.

        Iterative + memoized: depth is computed once per node and cached on the
        graph (``_chain_cache``), so the whole pass is ``O(nodes)`` even on a
        3000-deep view chain — recursion here would blow Python's stack limit and
        be ``O(nodes²)``.
        """
        cache = self._chain_cache
        if unique_id in cache:
            return cache[unique_id]
        # Post-order DFS via an explicit stack: push a node, then its unresolved
        # non-physical parents; resolve a node once all its parents are cached.
        stack = [unique_id]
        on_stack = {unique_id}
        while stack:
            uid = stack[-1]
            node = self._nodes.get(uid)
            if node is None or self.materialization(node) not in NON_PHYSICAL:
                cache[uid] = 0
                stack.pop()
                on_stack.discard(uid)
                continue
            best = 0
            pending = None
            for parent in self.parents(uid):
                if parent in cache:
                    best = max(best, cache[parent])
                elif parent not in on_stack:  # unresolved, not already in progress
                    pending = parent
                    break
                # parent in on_stack ⇒ a cycle; treat as a stop (contributes 0)
            if pending is not None:
                stack.append(pending)
                on_stack.add(pending)
                continue
            cache[uid] = 1 + best
            stack.pop()
            on_stack.discard(uid)
        return cache[unique_id]


class DimensionAnalyzer:
    """Run every manifest-derived health rule and group findings by dimension.

    *config* is the optional ``health`` block from ``dbdocs.yml``:
    ``thresholds`` (per-rule overrides), ``disable`` (rule names to skip),
    ``disable_dimensions`` (whole dimensions to skip), and ``rules_module`` (a
    dotted path whose ``register_rule`` calls add custom rules). Entry-point
    plugins under ``dbdocs.health_rules`` are always discovered.
    """

    def __init__(self, manifest: "Any | None", config: "dict | None" = None) -> None:
        config = config or {}
        thresholds = config.get("thresholds") if isinstance(config.get("thresholds"), dict) else {}
        self._graph = ManifestGraph(manifest, thresholds=thresholds)
        self._disabled_rules = set(config.get("disable") or [])
        self._disabled_dimensions = set(config.get("disable_dimensions") or [])

        # Plugin loading: entry points always; an explicit rules_module on request.
        load_entry_point_rules()
        rules_module = config.get("rules_module")
        if rules_module:
            load_rules_module(str(rules_module))

    def analyze(self) -> dict:
        """Return the ``dimensions`` block: one entry per (enabled) dimension."""
        graph = self._graph
        model_count = len(graph.models)
        source_count = len(graph.sources)
        dimensions: dict = {}
        for dimension, rules in DIMENSION_RULES.items():
            if dimension in self._disabled_dimensions:
                continue
            findings: list = []
            for rule in rules:
                if getattr(rule, "__name__", "") in self._disabled_rules:
                    continue
                try:
                    findings.extend(rule(graph))
                except (AttributeError, TypeError, ValueError, KeyError, RecursionError) as exc:
                    # A single malformed node / bad plugin must never sink the report.
                    logger.warning(
                        "Health dimension %s: rule %s failed: %s — skipping.",
                        dimension,
                        getattr(rule, "__name__", rule),
                        exc,
                    )
            dimensions[dimension] = {
                "issues": len(findings),
                "checked": self._checked(dimension, model_count, source_count),
                "findings": findings,
            }
        return dimensions

    @staticmethod
    def _checked(dimension: str, model_count: int, source_count: int) -> int:
        """How many nodes a dimension's rules could apply to (the score denominator)."""
        # Modeling/documentation/structure span models + sources; performance and
        # governance are model/exposure-centric — count models as the denominator.
        if dimension in ("modeling", "documentation", "structure"):
            return model_count + source_count
        return model_count
