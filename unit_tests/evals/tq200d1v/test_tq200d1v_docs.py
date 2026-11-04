"""
MODULE: unit_tests/evals/tq200d1v/test_tq200d1v_docs.py
GOAL: RED doc-drift test for TQ-200d-1-v: the wrong_version_run entry and the evals README state the rule.
"""

from __future__ import annotations

import re

import unit_tests.evals._tq200d1_helpers as h
import unit_tests.evals.tq200d1v._helpers as v

REF = h.REPO_ROOT / "docs" / "reference"


def _entry() -> str:
    text = (REF / "produced-tests-eval-assertion-kinds-test-writer.md").read_text(encoding="utf-8")
    return text.split("### `wrong_version_run`", 1)[1].split("\n### ", 1)[0].split("\n## ", 1)[0]


def test_wrong_version_run_entry_states_the_one_catching_test_rule():
    # covers: TQ-200d-1-v
    # angle: real_artifact
    # Catches: entry still says a single test must catch with every tagged test blocking.
    entry = _entry()
    passes = re.search(r"\*\*Passes when:\*\*(.*?)\n\n", entry, re.S).group(1).lower()
    assert "at least one tagged test" in passes, passes
    assert "one catching test is enough" in passes, passes
    assert "every tagged test is blocking" not in entry.lower()
    assert "not blocking" in entry or "do not block" in entry
    assert "fixed version" in entry
    example = re.search(r"\*\*Passing example:\*\*(.*?)\n\n", entry, re.S).group(1)
    for name in v.RUN1_TESTS:
        assert name in example, f"passing example must name {name}"
    assert "tq200d-rerun/test-writer/refresh-gate/run1" in entry
    assert (v.RERUN / "run1" / v.RECORDED).is_file()
    wvr = (REF / "wrong-version-runs.md").read_text(encoding="utf-8")
    assert "| `survivor` | A blocking row is `survived`." in wvr
    readme = (h.REPO_ROOT / "scripts" / "evals" / "README.md").read_text(encoding="utf-8")
    assert "produced-tests-eval-assertion-kinds-test-writer.md#wrong_version_run" in readme
    bullet = next(line for line in readme.splitlines() if "**One catching test.**" in line)
    assert "one tagged test catches the wrong version" in bullet and "do not block" in bullet, bullet
