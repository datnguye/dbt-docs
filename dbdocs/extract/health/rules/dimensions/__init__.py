"""The per-dimension health-rule modules (one module per DPE dimension).

Each module defines pure ``(graph) -> list[dict]`` rule functions for its
dimension. :mod:`dbdocs.extract.health.rules.registry` imports them and assembles
the ``DIMENSION_RULES`` mapping; the rules read shared helpers from
:mod:`dbdocs.extract.health.rules.base`.
"""
