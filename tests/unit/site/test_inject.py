import base64
import json

from dbdocs.site.inject import INJECT_MARKER, data_script, inject


def _decode(script: str) -> dict:
    payload = script.split('atob("')[1].split('")')[0]
    return json.loads(base64.b64decode(payload).decode("utf-8"))


def test_data_script_round_trips():
    data = {"nodes": {"a": 1}, "x": 'quotes " and <html>'}
    assert _decode(data_script(data)) == data


def test_inject_replaces_marker():
    html = f"<head>{INJECT_MARKER}</head><body></body>"
    out = inject(html, {"k": "v"})
    assert INJECT_MARKER not in out
    assert _decode(out) == {"k": "v"}


def test_inject_falls_back_to_head_close():
    html = "<head><title>t</title></head><body></body>"
    out = inject(html, {"k": "v"})
    assert "window.dbdocsData" in out
    assert out.index("window.dbdocsData") < out.index("</head>")


def test_inject_prepends_when_no_head():
    out = inject("<body>only</body>", {"k": "v"})
    assert out.startswith("<script>")
    assert _decode(out) == {"k": "v"}
