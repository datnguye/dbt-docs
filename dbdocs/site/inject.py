"""Inject the report data dict into the bundled SPA shell.

The SPA reads ``window.dbdocsData``. We base64-encode the JSON and embed it in a
``<script>`` so the (large, quote-and-newline-laden) payload can never break out
of the string literal — the same self-contained hand-off dbt-colibri uses. The
shell carries a ``<!-- DBDOCS_DATA -->`` marker as the insertion point; if it's
absent we fall back to inserting before ``</head>``.
"""

import base64
import json

#: Marker the bundled shell contains at the data insertion point.
INJECT_MARKER = "<!-- DBDOCS_DATA -->"


def data_script(data: dict) -> str:
    """The ``<script>`` tag that sets ``window.dbdocsData`` from ``data``."""
    payload = base64.b64encode(
        json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).decode("ascii")
    return f'<script>window.dbdocsData = JSON.parse(atob("{payload}"));</script>'


def inject(html: str, data: dict) -> str:
    """Return ``html`` with the data script placed at the marker / before head."""
    script = data_script(data)
    if INJECT_MARKER in html:
        return html.replace(INJECT_MARKER, script)
    if "</head>" in html:
        return html.replace("</head>", f"{script}</head>", 1)
    return script + html
