"""
MODULE: unit_tests/reference/test_bo4500b_4_i_shared_block_howto.py
GOAL: BO-4500b-4-i - keep docs/how-to/add-a-shared-workflow-block.md linked to real install-failure
    anchors and stating the stale-declaration rule.
BUSINESS CONTEXT: A how-to whose failure links dangle, or that omits the rule for removing an
    awaiting-adoption entry, sends a reader into an install refusal with no fix.
ARCHITECTURE: Pure checker over page text; the tests read the real how-to and reference page and
    use damaged copies of the text to prove the checker discriminates.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HOWTO_PATH = _REPO_ROOT / "docs" / "how-to" / "add-a-shared-workflow-block.md"
FAILURES_PATH = _REPO_ROOT / "docs" / "reference" / "shared-block-install-failures.md"

_LINK_RE = re.compile(r"shared-block-install-failures\.md#([A-Za-z0-9_-]+)")
_ANCHOR_RE = re.compile(r'<a id="([^"]+)">')
REQUIRED_ANCHORS = (
    "unknown-block-name",
    "unused-source",
    "stale-awaiting-adoption-declaration",
)
_STALE_RULE = "delete the whole `COMMIT-ANSWER` key"


def check_howto(howto_text: str, failures_text: str) -> list[str]:
    """Return the problems found in the how-to's links and stale-declaration statement."""
    anchors = set(_ANCHOR_RE.findall(failures_text))
    for heading in re.findall(r"^#+\s+(.+?)\s*$", failures_text, re.MULTILINE):
        anchors.add(re.sub(r"[^a-z0-9 -]", "", heading.lower()).replace(" ", "-"))  # heading slug
    linked = set(_LINK_RE.findall(howto_text))
    problems = [f"{a}: linked but no such anchor on the reference page" for a in sorted(linked - anchors)]
    problems += [f"{a}: required anchor not linked from the how-to" for a in REQUIRED_ANCHORS if a not in linked]
    if _STALE_RULE not in howto_text:
        problems.append("stale-declaration rule (whole awaiting-adoption entry removed) not stated")
    return problems


def _real() -> tuple[str, str]:
    return HOWTO_PATH.read_text(encoding="utf-8"), FAILURES_PATH.read_text(encoding="utf-8")


def test_howto_links_resolve_and_state_the_stale_declaration_rule():
    # covers: BO-4500b-4-i
    # angle: discrimination
    """Wrong versions caught: a link to an anchor the reference page does not carry (renamed or
    typo'd); a how-to that drops the unknown-name, unused-source or stale-declaration link; a
    how-to that omits the rule that the whole awaiting-adoption entry goes in the adopting change."""
    howto, failures = _real()
    assert check_howto(howto, failures) == []
    assert set(_LINK_RE.findall(howto)) >= set(REQUIRED_ANCHORS)  # the real page was inspected

    broken = howto.replace("#unused-source", "#unused-sourse")
    assert any("unused-sourse" in p for p in check_howto(broken, failures))

    missing_link = howto.replace("#stale-awaiting-adoption-declaration", "#text-between-markers")
    assert any("stale-awaiting-adoption-declaration" in p for p in check_howto(missing_link, failures))

    no_rule = howto.replace(_STALE_RULE, "delete the last adopter's record")
    assert any("stale-declaration rule" in p for p in check_howto(no_rule, failures))
