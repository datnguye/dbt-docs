"""Compare the published dbt-project-evaluator rule set against dbdocs's rules.

Scrapes each DPE rules category page for its rule heading anchors, derives the
anchors dbdocs already implements from the live ``DIMENSION_RULES`` registry (via
the same ``docs_url`` builder the findings use), and prints any DPE rule dbdocs
hasn't implemented yet. The watcher workflow turns a non-empty result into a
``feat:`` issue.

Output (stdout) is GitHub-Actions friendly: a ``missing<<EOF`` heredoc block
written to ``$GITHUB_OUTPUT`` when set, else a plain report. Exit code is always
0 — "nothing missing" is a normal, healthy result, not a failure.
"""

import os
import re
import sys
import urllib.request

from dbdocs.extract.health.rules.base import docs_url
from dbdocs.extract.health.rules.registry import DIMENSION_RULES

# The six DPE rules category pages, each diffed against the rules dbdocs registers
# for that dimension. Rule headings are the page's ``<h2>`` anchors (see below).
DPE_CATEGORIES = ("modeling", "testing", "documentation", "structure", "performance", "governance")
_BASE = "https://dbt-labs.github.io/dbt-project-evaluator/latest/rules"

# mkdocs-material renders each rule as an ``<h2 id="<slug>">`` heading (the page
# title is the ``<h1>``, any sub-detail is ``<h3>+``); matching only ``<h2>`` keeps
# non-rule headings out, so a new section heading can't masquerade as a rule.
_RULE_HEADING_ID = re.compile(r'<h2[^>]*\bid="([^"]+)"', re.IGNORECASE)

# A handful of ``<h2>`` slugs that aren't a rule (page-structure headings).
_NON_RULE_ANCHORS = set(DPE_CATEGORIES) | {
    "rules",
    "overview",
    "exceptions",
    "customization",
}


def _fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "dbdocs-dpe-watcher"})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed HTTPS host
        return response.read().decode("utf-8", "replace")


def published_anchors(category: str) -> "set[str]":
    """The rule heading anchors published on a DPE category page.

    Raises ``ValueError`` if the page yields no rule headings — a structural change
    upstream — so the run fails loudly rather than reporting every rule as missing.
    """
    html = _fetch(f"{_BASE}/{category}/")
    anchors = {a for a in _RULE_HEADING_ID.findall(html) if a not in _NON_RULE_ANCHORS}
    if not anchors:
        raise ValueError(
            f"No rule headings found on the DPE {category} page — page structure changed?"
        )
    return anchors


def implemented_anchors(category: str) -> "set[str]":
    """The DPE anchors dbdocs implements for *category* (via the rules' docs_url)."""
    out = set()
    for rule in DIMENSION_RULES.get(category, []):
        url = docs_url(category, rule.__name__)
        out.add(url.rsplit("#", 1)[-1])
    return out


def find_missing() -> "dict[str, list[str]]":
    """Map each category to the DPE rule anchors dbdocs hasn't implemented yet."""
    missing = {}
    for category in DPE_CATEGORIES:
        gap = sorted(published_anchors(category) - implemented_anchors(category))
        if gap:
            missing[category] = gap
    return missing


def render(missing: "dict[str, list[str]]") -> str:
    lines = []
    for category in DPE_CATEGORIES:
        for anchor in missing.get(category, []):
            url = f"{_BASE}/{category}/#{anchor}"
            lines.append(f"- **{category}** — `{anchor}` ([docs]({url}))")
    return "\n".join(lines)


def main() -> int:
    missing = find_missing()
    report = render(missing)
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as handle:
            handle.write(f"has_missing={'true' if missing else 'false'}\n")
            handle.write(f"missing<<DPE_EOF\n{report}\nDPE_EOF\n")
    if missing:
        print("DPE rules not yet implemented in dbdocs:\n" + report)
    else:
        print("dbdocs implements every published dbt-project-evaluator rule.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
