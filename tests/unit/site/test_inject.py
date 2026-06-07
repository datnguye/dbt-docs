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


def test_data_script_keys_are_sorted():
    # Two dicts with keys in reversed order must produce the same payload.
    data_a = {"z": 1, "a": 2}
    data_b = {"a": 2, "z": 1}
    assert data_script(data_a) == data_script(data_b)


def test_data_script_output_is_deterministic():
    # Calling data_script twice with the same input must produce identical bytes.
    data = {"nodes": {"b": 2, "a": 1}, "meta": "x"}
    assert data_script(data) == data_script(data)
