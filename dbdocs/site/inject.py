"""Prepare the bundled SPA shell's data insertion point.

The SPA loads its data dict at runtime by fetching the external
``dbdocs-data.json.gz`` (decompressed in-browser via ``DecompressionStream``;
see the SPA's ``data.js`` loader). The shell carries a ``<!-- DBDOCS_DATA -->``
marker where an inlined payload used to go; :func:`strip_marker` removes it so
the served HTML stays clean.
"""

#: Marker the bundled shell contains at the (now external) data insertion point.
INJECT_MARKER = "<!-- DBDOCS_DATA -->"


def strip_marker(html: str) -> str:
    """Return ``html`` with the data marker removed (data is loaded externally)."""
    return html.replace(INJECT_MARKER, "")
