"""
MODULE: test_bo_2300e_3
GOAL: RED-baseline behavioral tests for BO-2300e-3 -- "A pause-store read
    that could not run is reported as undetermined, never as 'no record'."

DIAGNOSED BUG (docs/known-issues/ac-driven-dev/open-blocker-ki-acd-20260928-
    pause-store-dispatched-to-worktree-agent.md, "second-order" finding):
    peekPausedGateId()'s peek-pause-record dispatch and resolveGate()'s
    read-pause-record dispatch (templates/workflows-js/plan-feature.js) both
    collapse THREE distinct outcomes -- a genuine empty read, a well-formed
    refusal, and a failed/unparseable dispatch -- onto the SAME "no pause
    record" result. BO-2300e-2 already fixed the ROUTING half (these
    dispatches now target command-step-runner, not worktree-agent); this AC
    fixes the PARSING half -- a refusal or failure on this path must never
    be read as "no pause record exists", while a GENUINE empty read must
    still be read that way (the boundary test below pins this second half).

TICKET: none (AC-driven; source_ac BO-2300e-3). Authored by test-writer
    ahead of the read-path classification fix. See
    unit_tests/workflows/_bo_2300e_3_fixtures.py for the shared two-hop
    scenario helpers and fixture shapes this file (and its two siblings,
    test_bo_2300e_3_i.py / test_bo_2300e_3_ii.py) all use.
AC: BO-2300e-3 (docs/acceptance-criteria/build-orchestration/
    BO-2300-interactive-pause-resume/BO-2300e-3.yaml)
"""

from __future__ import annotations

import unit_tests.workflows._bo_2300e_3_fixtures as fx

AUTHOR_LABEL = fx.AUTHOR_LABEL
GENUINE_EMPTY_READ = fx.GENUINE_EMPTY_READ
GENUINE_FOUND_READ = fx.GENUINE_FOUND_READ
HISTORICAL_REFUSAL_TEXT = fx.HISTORICAL_REFUSAL_TEXT
author_dispatch_count = fx.author_dispatch_count
classification_text = fx.classification_text
dispatched_labels = fx.dispatched_labels
paused_at_gate = fx.paused_at_gate
run_resume = fx.run_resume


def test_refusal_reply_reported_as_could_not_determine():
    # covers: BO-2300e-3
    # angle: criterion
    """Then: "the workflow reports that outcome as 'could not determine
    whether a pause record exists for this run' -- an outcome distinct from
    'no pause record exists'" -- for a well-formed refusal on the
    peek-pause-record dispatch.

    RED TODAY: peekPausedGateId() has no path that reaches a terminal
    "could not determine" classification at all -- a refusal is parsed with
    parseAgentJson(), which throws on free text, is caught, and collapses
    to `_peekParsed = null`, which is read as "not paused here" exactly like
    a genuine empty read. The run proceeds normally (re-dispatching the
    itpo author, per KI-ACD-20260928's own "sails past peek" description)
    instead of halting with a distinguishable classification.
    """
    run_id = "test-bo2300e3-peek-refusal"
    paused_at_gate(run_id)

    hop2 = run_resume(
        run_id, {"peek-pause-record": HISTORICAL_REFUSAL_TEXT}
    )
    assert hop2.error == "", f"Harness error on hop 2: {hop2.error}"

    text = classification_text(hop2).lower()
    assert "could not determine" in text, (
        "BO-2300e-3: a peek-pause-record refusal must be reported as "
        f"'could not determine...', never silently continued past. "
        f"Terminal payload: {hop2.result!r}"
    )
    status = (hop2.result or {}).get("status") if isinstance(hop2.result, dict) else None
    assert status != "nothing_to_resume", (
        "A refusal must not be reported with the same status as a genuine "
        f"empty read. Terminal payload: {hop2.result!r}"
    )


def test_read_pause_record_refusal_also_reported_as_could_not_determine():
    # covers: BO-2300e-3
    # angle: criterion
    """Then: the same "could not determine" classification applies to a
    refusal on resolveGate()'s read-pause-record dispatch -- independent
    proof the fix was not applied to peek-pause-record only (BO-2300e-3's
    own it_requirements: these are two separate, independently-maintained
    call sites).

    RED TODAY: resolveGate()'s resume-answer branch reads recCheck === null
    (refusal text fails parseAgentJson, caught, collapses to null) and
    returns `{status: "nothing_to_resume", ...}` directly -- the exact
    "genuinely-supplied resume answer... discarded as though there were
    nothing to resume" failure mode BO-2300e-3's it_requirements name.
    """
    run_id = "test-bo2300e3-read-refusal"
    paused_at_gate(run_id)

    hop2 = run_resume(
        run_id, {"read-pause-record": HISTORICAL_REFUSAL_TEXT}
    )
    assert hop2.error == "", f"Harness error on hop 2: {hop2.error}"

    text = classification_text(hop2).lower()
    assert "could not determine" in text, (
        "BO-2300e-3: a read-pause-record refusal must be reported as "
        f"'could not determine...'. Terminal payload: {hop2.result!r}"
    )
    status = (hop2.result or {}).get("status") if isinstance(hop2.result, dict) else None
    assert status != "nothing_to_resume", (
        "A genuinely-supplied resume answer must not be discarded as "
        f"'nothing_to_resume'. Terminal payload: {hop2.result!r}"
    )


def test_could_not_determine_does_not_advance_past_gate():
    # covers: BO-2300e-3
    # angle: criterion
    """Then: "the workflow does not proceed past the gate as though no
    pause record exists, and does not resume, clear, re-establish, or
    otherwise act on the run as if the check had found a legitimate empty
    result."

    Uses a read-pause-record refusal (the cleanest single-gate observation
    point: resolveGate's resume-answer branch returns directly, before any
    clear/apply-approval dispatch could fire). Asserts BOTH that the
    classification is correct (RED today -- see the two tests above) AND
    that the run did not clear the pause record or apply the person's
    answer, so this test still means something once the classification
    half is fixed on its own.

    RED TODAY: same mechanism as the two tests above -- "nothing_to_resume"
    is reported, not "could not determine".
    """
    run_id = "test-bo2300e3-no-advance"
    paused_at_gate(run_id)

    hop2 = run_resume(
        run_id, {"read-pause-record": HISTORICAL_REFUSAL_TEXT}
    )
    assert hop2.error == "", f"Harness error on hop 2: {hop2.error}"

    text = classification_text(hop2).lower()
    assert "could not determine" in text, (
        "The run must report 'could not determine...', not silently treat "
        f"the refusal as an answerable empty state. Terminal payload: {hop2.result!r}"
    )

    labels = dispatched_labels(hop2)
    assert "clear-pause-record" not in labels, (
        "A run that could not determine whether a pause record exists must "
        f"not clear it. Dispatched labels: {labels}"
    )
    assert "apply-approval" not in labels, (
        "A run that could not determine whether a pause record exists must "
        f"not apply the person's answer. Dispatched labels: {labels}"
    )


def test_genuine_empty_read_still_reports_no_record():
    # covers: BO-2300e-3
    # angle: boundary
    """Then (boundary, NOT the failure branch): a genuine
    {exists: false, stale: false, record: null} reply -- an agent that
    actually queried the store and found nothing -- must still be reported
    as "no pause record exists", at EITHER call site. This is the guard
    against the fix overcorrecting into treating every empty read as
    undetermined (BO-2300e-3's own test_rationale).

    NOTE ON THIS TEST'S BASELINE STATUS (intentionally NOT red): this is a
    REGRESSION GUARD for behavior that is already correct today -- the
    read-pause-record sub-case already reports "nothing_to_resume" for a
    genuine empty reply, and is expected to PASS both before and after the
    fix (see this file's own module docstring and the ticket's own "THE
    BOUNDARY THAT MAKES THIS HARD" section: a suite that only asserts the
    failure direction would be satisfied by an implementation that treats
    every empty read as undetermined, breaking resume for every
    legitimately-unpaused run). See this test's own assertions for the
    peek-pause-record sub-case, which is a genuine behavioral check (the
    author must still be re-dispatched, i.e. NOT skipped, when peek
    legitimately finds nothing) rather than a literal terminal-status
    assertion, since peek's own outcome has no terminal-status field of its
    own to inspect.
    """
    run_id_read = "test-bo2300e3-genuine-empty-read"
    paused_at_gate(run_id_read)
    hop2_read = run_resume(run_id_read, {"read-pause-record": GENUINE_EMPTY_READ})
    assert hop2_read.error == "", f"Harness error on hop 2: {hop2_read.error}"
    assert isinstance(hop2_read.result, dict), (
        f"Expected a terminal payload dict. Got: {hop2_read.result!r}"
    )
    assert hop2_read.result.get("status") == "nothing_to_resume", (
        "A genuine empty read-pause-record reply must still report "
        f"'nothing_to_resume'. Terminal payload: {hop2_read.result!r}"
    )

    run_id_peek = "test-bo2300e3-genuine-empty-peek"
    paused_at_gate(run_id_peek)
    hop2_peek = run_resume(
        run_id_peek,
        {"peek-pause-record": GENUINE_EMPTY_READ, "read-pause-record": GENUINE_FOUND_READ},
    )
    assert hop2_peek.error == "", f"Harness error on hop 2: {hop2_peek.error}"
    assert "could not determine" not in classification_text(hop2_peek).lower(), (
        "A genuine empty peek-pause-record reply must never be classified "
        f"as 'could not determine'. Terminal payload: {hop2_peek.result!r}"
    )
    assert author_dispatch_count(hop2_peek, AUTHOR_LABEL) >= 1, (
        "When peek-pause-record genuinely finds no record, the run is not "
        f"paused HERE, so the author step must not be skipped. Dispatched "
        f"labels: {dispatched_labels(hop2_peek)}"
    )
