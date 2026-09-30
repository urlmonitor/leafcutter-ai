"""
MODULE: test_bo_2300e_3_ii
GOAL: RED-baseline behavioral tests for BO-2300e-3-ii -- "An unparseable
    reply or a failed dispatch is not parsed as an empty pause-record
    result."

Sibling of BO-2300e-3-i (test_bo_2300e_3_i.py): that AC covers a well-formed
REFUSAL being misread as empty; this one covers the remaining ways a read
can fail to produce a usable result without being a refusal at all -- no
reply, a transport/execution error from the agent() call itself, and a
reply that is not valid JSON / lacks the expected shape. All three are
checked at BOTH the peek-pause-record and read-pause-record call sites via
parametrize.

See unit_tests/workflows/_bo_2300e_3_fixtures.py for the shared two-hop
scenario helpers and fixture shapes, including the `transport_error_response()`
helper and the `__harness_agent_throws__` sentinel it relies on (added to
unit_tests/_workflow_engine_harness.py by this same test-writer pass -- see
that file's own DECISION HISTORY entry for why no pre-existing
label_responses shape could represent a genuine dispatch failure).

AC: BO-2300e-3-ii (docs/acceptance-criteria/build-orchestration/
    BO-2300-interactive-pause-resume/BO-2300e-3-ii.yaml)
"""

from __future__ import annotations

import pytest

import unit_tests.workflows._bo_2300e_3_fixtures as fx

MALFORMED_REPLY_TEXT = fx.MALFORMED_REPLY_TEXT
NO_REPLY = fx.NO_REPLY
classification_text = fx.classification_text
paused_at_gate = fx.paused_at_gate
run_resume = fx.run_resume
transport_error_response = fx.transport_error_response

_LABELS = ["peek-pause-record", "read-pause-record"]


@pytest.mark.parametrize("label", _LABELS)
def test_no_reply_reported_as_could_not_determine(label):
    # covers: BO-2300e-3-ii
    # angle: failure
    """Then: a dispatch that returns no reply at all is classified as
    "could not determine" (checked for both labels).

    RED TODAY: a `null` reply is used directly with no exception raised --
    both peekPausedGateId() and resolveGate()'s resume-check treat it
    exactly like a genuine `{exists: false}` read (`!_peekParsed` /
    `recCheck.exists !== true` are both true for `null`), so the run
    proceeds/reports as though there were nothing to resume.
    """
    run_id = f"test-bo2300e3ii-no-reply-{label}"
    paused_at_gate(run_id)

    hop2 = run_resume(run_id, {label: NO_REPLY})
    assert hop2.error == "", f"Harness error on hop 2: {hop2.error}"

    assert "could not determine" in classification_text(hop2).lower(), (
        f"BO-2300e-3-ii: a no-reply outcome on {label} must be classified "
        f"as 'could not determine'. Terminal payload: {hop2.result!r}"
    )


@pytest.mark.parametrize("label", _LABELS)
def test_transport_error_reported_as_could_not_determine(label):
    # covers: BO-2300e-3-ii
    # angle: failure
    """Then: a dispatch that raises a transport/execution error from the
    agent() call itself (not just from parsing its reply) is classified as
    "could not determine", with the error handled per the project
    error-handling policy rather than propagating uncaught or being
    silently swallowed (checked for both labels).

    RED TODAY: `await agent(...)` for both peek-pause-record and
    read-pause-record sits OUTSIDE the existing try/catch (only the
    subsequent parseAgentJson() call is wrapped), so a genuine dispatch
    rejection propagates UNCAUGHT out of the whole script -- the harness
    observes this as the script's top-level promise rejecting, captured as
    a `None` terminal payload (see unit_tests/_workflow_engine_harness.py's
    outer `.catch` handler), never a classified, structured result.
    """
    run_id = f"test-bo2300e3ii-transport-error-{label}"
    paused_at_gate(run_id)

    hop2 = run_resume(
        run_id, {label: transport_error_response("simulated transport failure")}
    )
    # The harness ITSELF must not fail -- node runs fine; it is the SCRIPT
    # that must not crash uncaught. See the module docstring above.
    assert hop2.error == "", f"Harness error on hop 2: {hop2.error}"

    assert isinstance(hop2.result, dict), (
        f"BO-2300e-3-ii: a transport/execution error on {label} must be "
        "caught and turned into a structured terminal payload, not left to "
        f"propagate uncaught (observed as a None terminal payload). Got: {hop2.result!r}"
    )
    assert "could not determine" in classification_text(hop2).lower(), (
        f"BO-2300e-3-ii: a transport/execution error on {label} must be "
        f"classified as 'could not determine'. Terminal payload: {hop2.result!r}"
    )


@pytest.mark.parametrize("label", _LABELS)
def test_malformed_reply_reported_as_could_not_determine(label):
    # covers: BO-2300e-3-ii
    # angle: failure
    """Then: a dispatch reply that is not valid JSON or lacks the expected
    exists/record shape is classified as "could not determine" (checked
    for both labels).

    RED TODAY: parseAgentJson() throws ("no parseable JSON" -- there is no
    balanced {...}/[...] span in a plain traceback), the throw is caught,
    and the result collapses to null -- identical to a genuine empty read.
    """
    run_id = f"test-bo2300e3ii-malformed-{label}"
    paused_at_gate(run_id)

    hop2 = run_resume(run_id, {label: MALFORMED_REPLY_TEXT})
    assert hop2.error == "", f"Harness error on hop 2: {hop2.error}"

    assert "could not determine" in classification_text(hop2).lower(), (
        f"BO-2300e-3-ii: a malformed reply on {label} must be classified "
        f"as 'could not determine'. Terminal payload: {hop2.result!r}"
    )
