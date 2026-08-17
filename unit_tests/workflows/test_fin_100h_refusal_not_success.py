"""
MODULE: test_fin_100h_refusal_not_success
GOAL: Red-baseline regression tests for FIN-100h — a step whose agent legitimately
      refuses (or returns any status the workflow does not recognise) must never be
      routed onto that step's SUCCESS path, and load-bearing steps (the pre-merge
      test baseline, the origin/main integration merge) must HALT on refusal rather
      than degrade silently.

    Nature: bug-fix regression tests, written before the fix per the TDD-order
    rule (test-writer runs before python-coder). The bug is fully described in
    docs/acceptance-criteria/build_pipeline/FIN-100-pre-merge-safety-gate/FIN-100h.yaml
    and reproduced live: Step 2's agent returned
    {"status": "refused", "reason": "out_of_scope_for_status-checker",
    "merge_strategy": null} and finalize-feature.js recorded a clean merge that
    never happened (completedSteps.push(2) + the 'Merged origin/main cleanly'
    outcome), because Step 2 branches:
        if (mergeStatus === "conflict")           -> halt
        if (mergeStatus === "already_up_to_date") -> skip
        else                                      -> SUCCESS (bug: catch-all)
    Step 0 has the analogous defect: run_failed/worktree_failed/parse_failed/
    unknown/refused are all folded into one degrade-to-null-baseline branch,
    with no distinct halt for a refusal.

    Per the project's "Gate / Workflow ACs — Verify Behaviorally, Not by Grep"
    convention (root CLAUDE.md), these are NOT bare string-presence greps: each
    assertion is anchored to control-flow position (which branch a literal is
    found inside, and in what order relative to other branches/returns), not
    merely "the string appears somewhere in the file."

    These tests read the JS source as text (as finalize-feature.js is a
    workflow script the pytest layer cannot execute), following the existing
    convention in test_finalize_pre_merge_safety_gate.py.

    AC: FIN-100h
    (docs/acceptance-criteria/build_pipeline/FIN-100-pre-merge-safety-gate/FIN-100h.yaml)

TICKET: bug fix — dispatched directly to test-writer, no ticket_path.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths — resolved from this file's own location, no hardcoded home dir.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "finalize-feature.js"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _js_text() -> str:
    """Return the full text of finalize-feature.js."""
    return _JS_PATH.read_text(encoding="utf-8")


def _get_step_block(js: str, step_label: str, next_step_label: str) -> str:
    """Extract the source between two phase() markers.

    Returns text from phase('<step_label>') up to (but not including)
    phase('<next_step_label>'). Returns an empty string when the start marker
    is absent, and the tail of the file when only the end marker is absent.
    """
    start_marker = f"phase('{step_label}')"
    end_marker = f"phase('{next_step_label}')"
    start = js.find(start_marker)
    if start == -1:
        return ""
    end = js.find(end_marker, start)
    if end == -1:
        return js[start:]
    return js[start:end]


def _get_dispatch_options(js: str, label: str) -> str:
    """Return the options-object literal `{ agentType: ..., label: "<label>", ... }`
    for the specific agent(...) call carrying this label.

    This locates the exact dispatch by its label and reads the agentType from
    that same call's options object — it does NOT just count agentType
    occurrences file-wide, which would conflate this dispatch with any other
    dispatch that happens to share an agentType.

    Every agent(...) options object in this file is written as a single-line
    object literal `{ agentType: "...", label: "...", ... }`, so the nearest
    unescaped '{' before the label marker and the nearest '}' after it bound
    exactly that object.
    """
    label_marker = f'label: "{label}"'
    label_idx = js.find(label_marker)
    if label_idx == -1:
        return ""
    obj_start = js.rfind("{", 0, label_idx)
    obj_end = js.find("}", label_idx)
    if obj_start == -1 or obj_end == -1:
        return ""
    return js[obj_start:obj_end + 1]


# ---------------------------------------------------------------------------
# Test 1 — Step 2: unrecognised status must not reach the success path.
# ---------------------------------------------------------------------------

class TestFin100hStep2SuccessPathGuarded:
    """FIN-100h: Step 2's success path must be reached only via an explicit
    positive status match, never via a terminal catch-all `else`.
    """

    def test_ac_fin100h_step2_success_path_not_reached_via_bare_else(self):
        # covers: FIN-100h
        """AC FIN-100h: the step-2 success path (completedSteps.push(2) + the
        'Merged origin/main cleanly' outcome) must be guarded by an explicit
        positive status match (e.g. `if (mergeStatus === "merged")`), not
        reached through a terminal `} else {` that fires for ANY status the
        preceding `if` checks did not match — including an unrecognised or
        refused status such as
        {"status": "refused", "reason": "out_of_scope_for_status-checker"}.
        """
        step2 = _get_step_block(_js_text(), "Step 2", "Step 3")
        assert step2, "phase('Step 2') block must exist in finalize-feature.js"

        success_idx = step2.find("Merged origin/main cleanly")
        assert success_idx != -1, (
            "Step 2 must contain the 'Merged origin/main cleanly' success outcome."
        )
        push_idx = step2.rfind("completedSteps.push(2)", 0, success_idx)
        assert push_idx != -1, (
            "completedSteps.push(2) must precede the 'Merged origin/main cleanly' "
            "outcome on the success path."
        )

        # Walk backward from the success push to find which branch guards it:
        # it must be an explicit positive `if (mergeStatus === "merged")` match
        # (or equivalent named-success-status check), not a bare catch-all else.
        preceding = step2[:push_idx]
        last_else_idx = preceding.rfind("} else {")
        last_positive_if_idx = preceding.rfind('if (mergeStatus === "merged"')

        assert last_positive_if_idx != -1 and (
            last_else_idx == -1 or last_positive_if_idx > last_else_idx
        ), (
            "The step-2 success path (completedSteps.push(2) + 'Merged origin/main "
            "cleanly') must be guarded by an explicit `if (mergeStatus === "
            '"merged")` (or equivalent positive match against the known success '
            "status), not reached through a bare `} else {` catch-all. A catch-all "
            "else routes ANY unrecognised status — including a refusal like "
            '{"status": "refused", ...} — onto the success path. This is the '
            "FIN-100h bug: step 2 reported 'Merged origin/main cleanly' and pushed "
            "2 onto completed_steps when the agent in fact refused and no merge "
            "occurred."
        )


# ---------------------------------------------------------------------------
# Test 2 — Step 2: a refusal must halt (load-bearing merge step).
# ---------------------------------------------------------------------------

class TestFin100hStep2RefusalHalts:
    """FIN-100h: Step 2 is load-bearing for the merge decision, so a refusal
    must halt with a reason naming step 2 — not silently fall through to
    success.
    """

    def test_ac_fin100h_step2_refusal_halts_and_does_not_record_success(self):
        # covers: FIN-100h
        """AC FIN-100h: a refusal status at step 2 must halt the run — with a
        reason naming step 2 — and must NOT push to completedSteps or emit the
        success outcome.
        """
        step2 = _get_step_block(_js_text(), "Step 2", "Step 3")
        assert step2, "phase('Step 2') block must exist in finalize-feature.js"

        # There must be an explicit branch recognising a refusal / unrecognised
        # status, distinct from the known "conflict" and "already_up_to_date"
        # statuses that are already handled.
        has_refusal_branch = (
            'mergeStatus === "refused"' in step2
            or 'mergeStatus.startsWith("refused")' in step2
            or "mergeStatus.startsWith('refused')" in step2
            or "isRefusalStatus(mergeStatus)" in step2
            or "isRefusal(mergeStatus)" in step2
        )
        assert has_refusal_branch, (
            "Step 2 must contain an explicit branch that recognises a refusal / "
            'unrecognised status (e.g. `mergeStatus === "refused"` or a shared '
            "isRefusalStatus() helper), distinct from the known 'conflict' and "
            "'already_up_to_date' statuses. Without this, any unrecognised "
            "status (including a refusal) falls through to the success `else`. "
            "Required by FIN-100h."
        )

        # Anchor on the GUARD CALL, not on the substring "refus" — the latter
        # also matches explanatory comments, which would point the window at
        # prose instead of the branch and fail a correct implementation.
        refusal_idx = -1
        for anchor in (
            "isRefusalStatus(mergeStatus)",
            "isRefusal(mergeStatus)",
            'mergeStatus === "refused"',
        ):
            refusal_idx = step2.find(anchor)
            if refusal_idx != -1:
                break
        assert refusal_idx != -1

        # The refusal branch itself must halt naming step 2, and must NOT also
        # record success for step 2.
        tail = step2[refusal_idx:refusal_idx + 800]
        assert 'status: "halted"' in tail or "status: 'halted'" in tail, (
            "Step 2's refusal branch must return status: 'halted' rather than "
            "silently falling through to the merged_main success path. "
            "Required by FIN-100h."
        )
        assert "halted_at_step: 2" in tail, (
            "Step 2's refusal halt must name step 2 via halted_at_step: 2. "
            "Required by FIN-100h."
        )
        assert "completedSteps.push(2)" not in tail, (
            "Step 2's refusal branch must NOT push step 2 onto completedSteps — "
            "a refused step did not run and must not be recorded as having "
            "succeeded. Required by FIN-100h."
        )
        assert "Merged origin/main cleanly" not in tail, (
            "Step 2's refusal branch must NOT emit the 'Merged origin/main "
            "cleanly' success outcome. Required by FIN-100h."
        )


# ---------------------------------------------------------------------------
# Test 3 — Step 0: a refusal must be distinguishable from a run failure.
# ---------------------------------------------------------------------------

class TestFin100hStep0RefusalDistinctFromFailure:
    """FIN-100h: Step 0's baseline is load-bearing for the merge decision, so a
    refusal (the step never ran) must be handled distinctly from
    run_failed/parse_failed/worktree_failed (the step ran and produced a bad
    result) — and must halt rather than only degrade to a null baseline.
    """

    def test_ac_fin100h_step0_refusal_distinct_from_run_failed_and_halts(self):
        # covers: FIN-100h
        """AC FIN-100h: step 0 must recognise a refusal status distinctly from
        run_failed/parse_failed, and a refusal must halt rather than only
        degrade silently to a null baseline.
        """
        step0 = _get_step_block(_js_text(), "Step 0", "Step 1")
        assert step0, "phase('Step 0') block must exist in finalize-feature.js"

        has_refusal_recognition = (
            'baselineStatus === "refused"' in step0
            or "isRefusalStatus(baselineStatus)" in step0
            or "isRefusal(baselineStatus)" in step0
        )
        assert has_refusal_recognition, (
            "Step 0 must explicitly recognise a refusal status (e.g. "
            '`baselineStatus === "refused"` or a shared isRefusalStatus() '
            "helper), distinct from 'run_failed' / 'parse_failed' / "
            "'worktree_failed'. A refused step never ran; a failed step ran "
            "and produced a (bad) result — the current code folds both into "
            "one degrade-to-null-baseline branch with no distinction. "
            "Required by FIN-100h."
        )

        # Anchor on the GUARD CALL, not on the substring "refus" — see the
        # equivalent note in the step-2 test.
        refusal_idx = -1
        for anchor in (
            "isRefusalStatus(baselineStatus)",
            "isRefusal(baselineStatus)",
            'baselineStatus === "refused"',
        ):
            refusal_idx = step0.find(anchor)
            if refusal_idx != -1:
                break
        assert refusal_idx != -1

        tail = step0[refusal_idx:refusal_idx + 800]
        assert 'status: "halted"' in tail or "status: 'halted'" in tail, (
            "Step 0's refusal branch must HALT (status: 'halted') naming step 0 "
            "and the refusing agent — the baseline is load-bearing for the "
            "merge/regression decision, so a refusal must not silently degrade "
            "to a null baseline the way a genuine run_failed does. Required by "
            "FIN-100h."
        )
        assert "halted_at_step: 0" in tail, (
            "Step 0's refusal halt must name step 0 via halted_at_step: 0. "
            "Required by FIN-100h."
        )


# ---------------------------------------------------------------------------
# Test 4 — Agent routing: step 0 and step 2 must not dispatch to status-checker.
# ---------------------------------------------------------------------------

class TestFin100hCapabilityStepsNotRoutedToStatusChecker:
    """FIN-100h: step 0 (git worktree provisioning, build.py, pytest) and step 2
    (git fetch/merge/merge --abort) are capability-requiring steps whose work
    falls outside status-checker's ticket-state-verification contract — they
    must not be dispatched with agentType "status-checker".
    """

    def test_ac_fin100h_step0_baseline_not_dispatched_to_status_checker(self):
        # covers: FIN-100h
        """AC FIN-100h: the step-0-baseline dispatch must not use agentType
        'status-checker'.
        """
        options = _get_dispatch_options(_js_text(), "step-0-baseline")
        assert options, (
            "Could not locate the agent(...) dispatch labeled 'step-0-baseline' "
            "in finalize-feature.js."
        )
        assert 'agentType: "status-checker"' not in options, (
            "The step-0-baseline dispatch (git worktree add, build.py, pytest) "
            "must not use agentType 'status-checker'. status-checker's contract "
            "is ticket-state verification; it correctly refuses this work "
            "('Recommend the orchestrator re-dispatch this baseline-capture "
            "task to the correct specialist agent.'). Required by FIN-100h."
        )

    def test_ac_fin100h_step2_merge_main_not_dispatched_to_status_checker(self):
        # covers: FIN-100h
        """AC FIN-100h: the step-2-merge-main dispatch must not use agentType
        'status-checker'.
        """
        options = _get_dispatch_options(_js_text(), "step-2-merge-main")
        assert options, (
            "Could not locate the agent(...) dispatch labeled 'step-2-merge-main' "
            "in finalize-feature.js."
        )
        assert 'agentType: "status-checker"' not in options, (
            "The step-2-merge-main dispatch (git fetch, git merge, git merge "
            "--abort) must not use agentType 'status-checker'. status-checker's "
            "contract is ticket-state verification, not git merge mechanics — "
            "it correctly refuses this work. Required by FIN-100h."
        )


# ---------------------------------------------------------------------------
# Test 5 — Guard: legitimate ticket-state dispatches must keep status-checker.
# ---------------------------------------------------------------------------

class TestFin100hLegitimateStatusCheckerDispatchesUnaffected:
    """Guard so the FIN-100h fix cannot over-correct: dispatches that ARE
    genuinely ticket-state / gh-state verification work must keep using
    agentType 'status-checker'. This test must PASS both before and after the
    fix — it is not part of the red baseline.
    """

    def test_ac_fin100h_ticket_state_dispatches_still_use_status_checker(self):
        # covers: FIN-100h
        """Guard: 'pre-flight' (branch/worktree detection via git commands
        status-checker already covers) and 'step-1-pr-probe' (gh pr list, a
        read-only ticket/PR-state query) must remain on agentType
        'status-checker'. The FIN-100h fix must be scoped to the two
        capability-requiring dispatches (step-0-baseline, step-2-merge-main),
        not a blanket removal of status-checker from the workflow.
        """
        js = _js_text()
        for label in ("pre-flight", "step-1-pr-probe"):
            options = _get_dispatch_options(js, label)
            assert options, (
                f"Could not locate the agent(...) dispatch labeled '{label}' "
                "in finalize-feature.js."
            )
            assert 'agentType: "status-checker"' in options, (
                f"The '{label}' dispatch is genuinely ticket-state/gh-state "
                "verification work and must keep using agentType "
                "'status-checker'. FIN-100h's fix must re-route only the "
                "capability-requiring steps (step-0-baseline, "
                "step-2-merge-main), not remove status-checker wholesale."
            )
