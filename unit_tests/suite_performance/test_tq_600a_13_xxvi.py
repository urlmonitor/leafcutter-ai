"""TQ-600a-13-xxvi: the testing guide and the suite-performance guide say which tests each run executes.

A documentation criterion, so the proof is the guides' own text: each must name the post-merge live-database lane,
what it runs and against which databases, how its endings read, and where else the live tests run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTING_GUIDE = REPO_ROOT / "docs" / "testing" / "README.md"
# The testing guide keeps a summary and links here for the lane details (doc-length limit).
GUIDES = (REPO_ROOT / "docs" / "testing" / "post-merge-lanes.md", REPO_ROOT / "scripts" / "suite_performance" / "README.md")
LANE_FACTS = (
    "live_run",
    "live_retry",
    "tests/knowledge_live/",
    "neo4j:5.26-community",
    "17687",
    "18087",
    "18088",
    "did-not-complete",
    "done-proof",
)


@pytest.mark.parametrize("guide", GUIDES, ids=lambda path: path.parent.name)
def test_tq_600a_13_xxvi_each_guide_names_the_live_lane_and_where_live_tests_run(guide):
    # covers: TQ-600a-13-xxvi
    # angle: criterion
    """Both guides name the live lane's jobs, folder, databases and endings, and the PR Proof-of-done run."""
    text = guide.read_text(encoding="utf-8")
    missing = [fact for fact in LANE_FACTS if fact not in text]
    assert not missing, f"{guide.relative_to(REPO_ROOT)} does not mention {missing}"
    assert "never" in text and "skip" in text, "the guide must say a skip is never a pass"


def test_tq_600a_13_xxvi_the_testing_guide_links_the_post_merge_lanes_page():
    # covers: TQ-600a-13-xxvi
    # angle: reachability
    """A reader of the testing guide reaches the lane details: it links post-merge-lanes.md and names the live lane."""
    text = TESTING_GUIDE.read_text(encoding="utf-8")
    assert "post-merge-lanes.md" in text
    assert "live" in text.lower()


def test_tq_600a_13_xxvi_the_suite_performance_guide_no_longer_says_manual_tests_run_nowhere():
    # covers: TQ-600a-13-xxvi
    # angle: discrimination
    """The old claim that `_MANUAL` tests run nowhere in CI is gone; the guide names the post-merge correctness lane."""
    text = GUIDES[1].read_text(encoding="utf-8")
    assert "run nowhere" not in text.lower()
    assert "manual and not timing_ratio" in text
