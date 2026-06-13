"""Tests for the DPE-rules watcher script (.github/scripts/check_dpe_rules.py).

The script lives outside the ``dbdocs`` package (so it's not in the coverage
gate), but its diff logic decides whether the watcher workflow files a feature
issue — worth locking down. The network fetch is monkeypatched; only the
comparison + rendering is exercised.
"""

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "check_dpe_rules.py"


@pytest.fixture
def watcher():
    spec = importlib.util.spec_from_file_location("check_dpe_rules", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_implemented_anchors_reads_the_registry(watcher):
    anchors = watcher.implemented_anchors("testing")
    # The override map (and the rules) must resolve to real DPE anchors.
    assert "missing-source-freshness" in anchors
    assert "test-coverage" in anchors


def test_find_missing_flags_an_unimplemented_rule(watcher, monkeypatch):
    # Pretend DPE published a brand-new modeling rule dbdocs doesn't carry.
    extra = {"modeling": {"a-shiny-new-rule"}}
    monkeypatch.setattr(
        watcher,
        "published_anchors",
        lambda category: watcher.implemented_anchors(category) | extra.get(category, set()),
    )
    assert watcher.find_missing() == {"modeling": ["a-shiny-new-rule"]}


def test_find_missing_empty_at_parity(watcher, monkeypatch):
    monkeypatch.setattr(watcher, "published_anchors", watcher.implemented_anchors)
    assert watcher.find_missing() == {}


def test_render_lists_each_missing_rule_with_a_docs_link(watcher):
    out = watcher.render({"modeling": ["a-shiny-new-rule"]})
    assert "a-shiny-new-rule" in out
    assert "rules/modeling/#a-shiny-new-rule" in out


def test_published_anchors_parses_h2_rule_headings(watcher, monkeypatch):
    # Only <h2> rule headings count: the <h1> page title and <h3> sub-detail are
    # ignored, and the page-structure "rules" anchor is filtered out.
    html = (
        '<h1 id="modeling">Modeling</h1>'
        '<h2 id="root-models">Root models</h2>'
        '<h2 id="rules">Rules</h2>'
        '<h3 id="sub-detail">Detail</h3>'
    )
    monkeypatch.setattr(watcher, "_fetch", lambda url: html)
    assert watcher.published_anchors("modeling") == {"root-models"}


def test_published_anchors_raises_when_page_structure_changes(watcher, monkeypatch):
    # A page with no rule headings means the upstream structure changed — fail loud
    # rather than report every rule as missing.
    monkeypatch.setattr(watcher, "_fetch", lambda url: "<h1 id='modeling'>Modeling</h1>")
    with pytest.raises(ValueError, match="page structure changed"):
        watcher.published_anchors("modeling")
