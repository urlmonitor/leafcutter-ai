"""
MODULE: unit_tests/evals/tq200d1vi/test_tq200d1vi_docs.py
COVERS: TQ-200d-1-vi
GOAL: RED tests: the report_mentions reference entry, the evals README and the known issue state the widening.
Target: docs/reference/produced-tests-eval-assertion-kinds-test-writer.md, scripts/evals/README.md, the known issue
"""

from __future__ import annotations

import re

import unit_tests.evals._tq200d1_helpers as h
from unit_tests.evals.tq200d1vi import _helpers as s

ENTRY_DOC = h.REPO_ROOT / "docs" / "reference" / "produced-tests-eval-assertion-kinds-test-writer.md"
README = h.EVALS_DIR / "README.md"
ISSUE = h.REPO_ROOT / "docs" / "known-issues" / "testing-quality" / "open-low-ki-tq-20261102-test-writer-rows-check-unrequested-report-wording.md"


def _entry() -> str:
    text = ENTRY_DOC.read_text(encoding="utf-8")
    start = text.index("### `report_mentions`")
    end = text.index("\n### ", start + 1)
    return text[start:end]


def _field(entry: str, label: str) -> str:
    match = re.search(rf"\*\*{label}:\*\*(.*?)(?=\n\*\*|\Z)", entry, re.DOTALL)
    assert match, f"entry has no {label} line"
    return match.group(1)


def test_report_mentions_entry_states_equivalent_wordings(tmp_path):
    # covers: TQ-200d-1-vi
    # angle: real_artifact
    # must_catch: entry still describes a single term only
    """The entry names also_accepts and both rows; its passing and failing examples score as stated on the real row."""
    entry = _entry()
    assert "also_accepts" in _field(entry, "Reads"), "Reads must list the also_accepts spec key"
    assert "also_accepts" in _field(entry, "Passes when")
    assert "empty-window" in entry and "presence-is-not-correctness" in entry
    passing, failing = _field(entry, "Passing example"), _field(entry, "Failing example")
    assert "exact non-None count" in passing, passing
    assert "returns None when the feed is empty" in failing, failing
    assert s.score_report("exact non-None count", tmp_path / "p", s.EMPTY)["passed"] is True
    assert s.score_report("returns None when the feed is empty", tmp_path / "f", s.EMPTY)["passed"] is False
    assert "**Template sentence:** none" in entry


def test_readme_bullet_links_the_report_mentions_entry():
    # covers: TQ-200d-1-vi
    # angle: real_artifact
    # must_catch: README rule bullet missing
    """The produced-tests section carries one bullet naming also_accepts and linking #report_mentions."""
    text = README.read_text(encoding="utf-8")
    section = text[text.index("## Produced-tests mode"):]
    bullets = [b for b in section.splitlines() if b.startswith("- ") and "also_accepts" in b]
    assert len(bullets) == 1, f"exactly one bullet must name also_accepts, got {len(bullets)}"
    assert "#report_mentions" in bullets[0] and "produced-tests-eval-assertion-kinds-test-writer.md" in bullets[0]


def test_known_issue_parts_one_and_two_are_struck_naming_this_ac():
    # covers: TQ-200d-1-vi
    # angle: real_artifact
    # must_catch: known issue parts 1 and 2 not struck
    """Mechanism parts 1 and 2 are struck with ~~...~~ and a note; the Status line names the AC."""
    path = ISSUE if ISSUE.is_file() else next(ISSUE.parent.glob("**/resolved-low-ki-tq-20261102-test-writer-rows-*.md"), ISSUE)
    text = path.read_text(encoding="utf-8")
    mechanism = text[text.index("## Mechanism"):text.index("## Evidence")]
    parts = re.split(r"\n(?=\d\. )", mechanism)
    one, two = (next(p for p in parts if p.startswith(f"{n}. ")) for n in (1, 2))
    for part in (one, two):
        assert "~~" in part and "TQ-200d-1-vi" in part and "also_accepts" in part, part[:200]
    assert "unit_tests/evals/tq200d1vi/" in mechanism
    assert "TQ-200d-1-vi" in text[text.index("- **Status:**"):text.index("- **Occurrences:**")]
