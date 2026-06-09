from dbdocs.site.inject import INJECT_MARKER, strip_marker


def test_strip_marker_removes_marker():
    html = f"<head>{INJECT_MARKER}</head><body></body>"
    out = strip_marker(html)
    assert INJECT_MARKER not in out
    assert out == "<head></head><body></body>"


def test_strip_marker_without_marker_returns_html_unchanged():
    html = "<head><title>t</title></head><body></body>"
    assert strip_marker(html) == html
