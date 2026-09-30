"""
MODULE: test_bo_2300e_3_i
GOAL: RED-baseline behavioral tests for BO-2300e-3-i -- "A well-formed
    refusal is not parsed as an empty pause-record result."

Narrower sibling of BO-2300e-3 (test_bo_2300e_3.py): that AC's tests prove
the overall three-way classification exists at all; this file proves
specifically that a REFUSAL (as opposed to a malformed/absent reply --
BO-2300e-3-ii's concern) is distinguishable from a genuine empty read, using
the VERBATIM historical refusal text named in this AC's own TEST STRATEGY
it_requirement, at BOTH the peek-pause-record and read-pause-record call
sites independently.

See unit_tests/workflows/_bo_2300e_3_fixtures.py for the shared two-hop
scenario helpers and fixture shapes.

AC: BO-2300e-3-i (docs/acceptance-criteria/build-orchestration/
    BO-2300-interactive-pause-resume/BO-2300e-3-i.yaml)
"""

from __future__ import annotations

import pytest

import unit_tests.workflows._bo_2300e_3_fixtures as fx

GENUINE_EMPTY_READ = fx.GENUINE_EMPTY_READ
GENUINE_FOUND_READ = fx.GENUINE_FOUND_READ
HISTORICAL_REFUSAL_TEXT = fx.HISTORICAL_REFUSAL_TEXT
classification_text = fx.classification_text
paused_at_gate = fx.paused_at_gate
run_resume = fx.run_resume


def test_worktree_agent_style_refusal_not_read_as_empty():
    # covers: BO-2300e-3-i
    # angle: criterion
    """Then: a peek-pause-record dispatch reply carrying the verbatim
    historical refusal text is classified as "could not determine", not
    "no pause record".

    RED TODAY: the refusal text fails parseAgentJson() (no parseable JSON
    in free text), the throw is caught, and _peekParsed collapses to null --
    identical to a genuine empty read. peekPausedGateId() reports nothing
    distinguishable; the run proceeds as though not paused here.
    """
    run_id = "test-bo2300e3i-peek-refusal"
    paused_at_gate(run_id)

    hop2 = run_resume(run_id, {"peek-pause-record": HISTORICAL_REFUSAL_TEXT})
    assert hop2.error == "", f"Harness error on hop 2: {hop2.error}"

    assert "could not determine" in classification_text(hop2).lower(), (
        "BO-2300e-3-i: the historical worktree-agent-style refusal on "
        f"peek-pause-record must be classified as 'could not determine'. "
        f"Terminal payload: {hop2.result!r}"
    )


def test_read_pause_record_refusal_not_read_as_empty():
    # covers: BO-2300e-3-i
    # angle: criterion
    """Then: a read-pause-record dispatch reply (resolveGate's resume-check
    dispatch) carrying the same verbatim historical refusal text is
    classified as "could not determine", not "no pause record" -- proving
    the fix at the second, independent call site.

    RED TODAY: recCheck collapses to null the same way, and resolveGate()
    returns {status: "nothing_to_resume", ...} directly.
    """
    run_id = "test-bo2300e3i-read-refusal"
    paused_at_gate(run_id)

    hop2 = run_resume(run_id, {"read-pause-record": HISTORICAL_REFUSAL_TEXT})
    assert hop2.error == "", f"Harness error on hop 2: {hop2.error}"

    assert "could not determine" in classification_text(hop2).lower(), (
        "BO-2300e-3-i: the historical worktree-agent-style refusal on "
        f"read-pause-record must be classified as 'could not determine'. "
        f"Terminal payload: {hop2.result!r}"
    )
    status = hop2.result.get("status") if isinstance(hop2.result, dict) else None
    assert status != "nothing_to_resume", (
        f"Must not collapse to the genuine-empty status. Terminal payload: {hop2.result!r}"
    )


@pytest.mark.parametrize("label", ["peek-pause-record", "read-pause-record"])
def test_refusal_and_genuine_empty_read_are_distinguishable(label):
    # covers: BO-2300e-3-i
    # angle: boundary
    """Then: a refusal reply and a genuine {exists: false, record: null}
    reply produce two different, distinguishable classifications from the
    workflow, checked for both the peek-pause-record and read-pause-record
    labels.

    RED TODAY: both replies collapse to the exact same code path (parse
    throws or exists!==true -> treated as "not paused here" / "nothing to
    resume"), so the two terminal payloads are classification-IDENTICAL --
    the precise defect this AC family exists to fix (KI-ACD-20260928's
    "indistinguishable from the legitimate no-record case").
    """
    other_label = "read-pause-record" if label == "peek-pause-record" else "peek-pause-record"

    run_id_refused = f"test-bo2300e3i-distinguish-refused-{label}"
    paused_at_gate(run_id_refused)
    refused_hop2 = run_resume(
        run_id_refused,
        {label: HISTORICAL_REFUSAL_TEXT, other_label: GENUINE_FOUND_READ},
    )
    assert refused_hop2.error == "", f"Harness error: {refused_hop2.error}"

    run_id_empty = f"test-bo2300e3i-distinguish-empty-{label}"
    paused_at_gate(run_id_empty)
    empty_hop2 = run_resume(
        run_id_empty,
        {label: GENUINE_EMPTY_READ, other_label: GENUINE_FOUND_READ},
    )
    assert empty_hop2.error == "", f"Harness error: {empty_hop2.error}"

    refused_text = classification_text(refused_hop2).lower()
    empty_text = classification_text(empty_hop2).lower()

    assert "could not determine" in refused_text, (
        f"[{label}] refusal must be classified as 'could not determine'. "
        f"Terminal payload: {refused_hop2.result!r}"
    )
    assert "could not determine" not in empty_text, (
        f"[{label}] a genuine empty read must NOT be classified as 'could "
        f"not determine'. Terminal payload: {empty_hop2.result!r}"
    )
    assert refused_hop2.result != empty_hop2.result, (
        f"[{label}] a refusal and a genuine empty read must produce "
        f"DIFFERENT terminal payloads. Refused: {refused_hop2.result!r} "
        f"Empty: {empty_hop2.result!r}"
    )
