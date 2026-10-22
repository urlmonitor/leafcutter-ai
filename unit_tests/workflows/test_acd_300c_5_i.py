"""
MODULE: unit_tests/workflows/test_acd_300c_5_i.py
COVERS: ACD-300c-5-i
GOAL: Red-first specification that no /plan-feature rationale pointer comment says "Why why": each of the
    15 pointer lines reads "Why" once with the rest of its line unchanged, no line contains "why why" in
    any letter case, and the corrected workflow still loads and runs.
ARCHITECTURE: The lines are pinned with their full text as they stood at commit c73ebddc1 (indentation and
    rationale doc path included), at their line numbers after the origin/main merge that retired the
    worktree-setup path (BO-4300), which removed 3 of the 15 pointer lines; the 12 that remain are pinned and
    the file's line count is pinned to that merge's 3142.
    The run uses the real plan-feature.js under run_workflow_under_e2 (the harness of
    unit_tests/ac_driven_dev/test_design_stage/_design_stage_support.py).
RED STATE: all 15 pointer lines still read "// Why why".
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_STAGE_DIR = Path(__file__).resolve().parents[1] / "ac_driven_dev" / "test_design_stage"
sys.path.insert(0, str(_STAGE_DIR))

from _approval_step_support import BATCH, gate_record, names, prepass_for, resume, run, table  # noqa: E402
from _design_stage_support import PLAN_FEATURE_JS  # noqa: E402

_LINE_COUNT_AT_PIN = 3142
_PINNED = (
    (1642, '    // Why why shape-valid is not person-authored (ACD-2100c-4): docs/reference/plan-feature-workflow-rationale.md'),
    (1674, '    // Why why the pause record is cleared once the run moves past the gate (ACD-2100c-3 AC-4): docs/reference/plan-feature-workflow-rationale.md'),
    (1699, '        // Why why a failed pause-record clear is reported: docs/reference/plan-feature-workflow-rationale.md'),
    (1710, '  // Why why an unanswered gate pauses (ACD-2100c-1 / KI-ACD-005): docs/reference/plan-feature-workflow-rationale.md'),
    (1780, '  // Why why the pause payload carries the question (ACD-2100c-1): docs/reference/plan-feature-workflow-rationale.md'),
    (2188, '// Why why a missing pre-flight verdict fails closed: docs/reference/plan-feature-workflow-rationale.md'),
    (2233, '    // Why why the denied report names permits_shell (ACD-2100b-3): docs/reference/plan-feature-workflow-rationale-gates.md'),
    (2394, '  // Why why a missing covered-gate answer fails closed (KI-ACD-005): docs/reference/plan-feature-workflow-rationale-gates.md'),
    (2728, '    // Why why a skipped reconciliation is signalled (m6): docs/reference/plan-feature-workflow-rationale-gates.md'),
    (2773, '    // Why why the author is not re-dispatched on resume (ACD-2100c-3): docs/reference/plan-feature-workflow-rationale-gates.md'),
    (2895, '        // Why why a cancel is distinct from success (BO-2300a-2, ACD-2100c-5): docs/reference/plan-feature-workflow-rationale-gates.md'),
    (3004, '        // Why why all_acs is merged with de-duplication (H-2): docs/reference/plan-feature-workflow-rationale-gates.md'),
)
_WHY_WHY = re.compile(r"why\s+why", re.IGNORECASE)


def _lines() -> list[str]:
    return PLAN_FEATURE_JS.read_text(encoding="utf-8").splitlines()


def test_rationale_pointers_read_why_once():
    # covers: ACD-300c-5-i
    # angle: discrimination
    """Each of the 12 pinned pointer lines now equals its pinned text with "// Why why " replaced by
    "// Why ", character for character, and the file's line count is unchanged.

    Wrong versions caught: the doubled word removed by deleting "Why " (the comment reads "// why ...");
    a pointer line whose rationale doc path or ticket id changes while the word is fixed; a line added or
    removed, which shifts the pinned sites.
    """
    lines = _lines()
    assert len(lines) == _LINE_COUNT_AT_PIN, f"line count {len(lines)} != {_LINE_COUNT_AT_PIN}: a line was added or removed"
    wrong = {
        number: lines[number - 1]
        for number, pinned in _PINNED
        if lines[number - 1] != pinned.replace("// Why why ", "// Why ", 1)
    }
    assert wrong == {}, f"pointer lines not corrected exactly: {wrong}"


def test_workflow_source_has_no_why_why():
    # covers: ACD-300c-5-i
    # angle: discrimination
    """A case-insensitive scan of every line of plan-feature.js finds no "why why".

    Wrong versions caught: only the three lines named in the old criteria (L1660, L1694, L1721) fixed while
    the other twelve stay; a case-sensitive check, so "WHY why" or "why Why" survives.
    """
    hits = [(number, line.strip()) for number, line in enumerate(_lines(), start=1) if _WHY_WHY.search(line)]
    assert hits == [], hits


def test_corrected_workflow_still_runs_to_the_final_gate(tmp_path):
    # covers: ACD-300c-5-i
    # angle: reachability
    """Entry point: the real plan-feature.js under run_workflow_under_e2 runs to the final gate and through
    a cancel there, so the comment-only edit leaves the workflow loading and running; the source the harness
    loaded contains no "why why" in any letter case."""
    prepass = prepass_for(tmp_path, BATCH)
    paused = run(table(prepass, BATCH))
    assert gate_record(paused) is not None, f"the run never reached the final gate: {names(paused)}"

    cancelled = run(table(prepass, BATCH), resume("cancel"))
    assert (cancelled.result or {}).get("status") == "cancelled", cancelled.result

    loaded = PLAN_FEATURE_JS.read_text(encoding="utf-8")
    assert not _WHY_WHY.search(loaded), "the source the harness loaded still says 'why why'"
