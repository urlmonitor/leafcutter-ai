"""
MODULE: _bo_2300e_3_fixtures
GOAL: Shared fixtures/helpers for the BO-2300e-3 / -3-i / -3-ii RED-baseline
    test family -- "a pause-store READ that could not run is reported as
    undetermined, never as 'no record'."

BUSINESS CONTEXT: docs/known-issues/ac-driven-dev/open-blocker-ki-acd-
    20260928-pause-store-dispatched-to-worktree-agent.md's "second-order"
    finding: peekPausedGateId()'s peek-pause-record dispatch and
    resolveGate()'s read-pause-record dispatch both collapse THREE distinct
    outcomes -- a genuine empty read, a well-formed refusal, and a failed/
    unparseable dispatch -- onto the SAME "no pause record" result. This
    module holds the ONE set of fixtures/helpers three sibling test files
    (test_bo_2300e_3.py, test_bo_2300e_3_i.py, test_bo_2300e_3_ii.py) all
    need, rather than each growing its own near-identical copy (the same
    de-duplication rationale unit_tests/_plan_feature_gate_harness.py's own
    docstring gives for its six-file precedent).

    All three files drive the REAL, on-disk templates/workflows-js/
    plan-feature.js via the real Node E2 engine harness
    (unit_tests/_workflow_engine_harness.py) and assert on the CAPTURED
    dispatch data and the script's own terminal payload -- never on the
    source text -- per this repo's "verify behaviorally, not by grep"
    convention for gate/workflow ACs (CLAUDE.md).

SCENARIO SHAPE: every test in this family uses the SAME two-hop scenario --
    hop 1 is a headless run that genuinely pauses at "final-gate" (the only
    gate in the default "technical" route's single-step pipeline, matching
    unit_tests/workflows/test_bo_2300e_2.py's own scenario shape); hop 2
    resumes with a person-attributed `approve` answer for that same gate,
    with ONE of {peek-pause-record, read-pause-record} deliberately stubbed
    to the failure shape under test while the OTHER stays genuine (a
    well-formed, found-and-matching record) so its own path introduces no
    noise into what is being isolated.

TICKET: none (AC-driven; source_ac BO-2300e-3 / -3-i / -3-ii). Authored by
    test-writer ahead of the read-path classification fix -- the tests in
    the three sibling files are expected to be RED (with one deliberate,
    documented exception -- see test_bo_2300e_3.py's boundary test) until
    templates/workflows-js/plan-feature.js is changed.
"""

from __future__ import annotations

import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2  # noqa: E402
from _plan_feature_gate_harness import granted_workspace_setup_permission  # noqa: E402

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
PLAN_FEATURE_JS = WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"

TIMEOUT = 30  # seconds; all agent() calls are synchronous mocks.

# The default ("technical") route's single-step pipeline (see
# templates/workflows-js/plan-feature.js's pipeline-selection block) has one
# gate: "final-gate". Every scenario in this family resumes at that gate --
# matching test_bo_2300e_2.py's own choice, for the same reason (it is the
# gate reachable with NO route-specific label stubbing).
GATE_ID = "final-gate"
AUTHOR_LABEL = "stage-itpo-author"

PERMIT_OK = granted_workspace_setup_permission()

# ---------------------------------------------------------------------------
# Reply fixtures
# ---------------------------------------------------------------------------

# A genuine, well-formed, SUCCESSFUL persist-verify reply -- required for hop
# 1 to actually reach "paused_awaiting_input" rather than
# "pause_persist_failed". Real command-step-runner shape is
# {command, workspace, exit_status, stdout, stderr} with the payload inside
# `stdout`, but pauseAtGate()'s own parse tolerates a bare dict directly
# (see its ternary: a non-string reply with no `.stdout` string is used
# as-is) -- the same tolerant shape test_bo_2300e_2.py's own
# _ROUND_TRIP_LABEL_RESPONSES uses for this exact label.
GENUINE_PERSIST_VERIFY = {"exists": True, "stale": False}

# A genuine, well-formed reply reporting the run IS paused, right here, with
# a record a consumer can act on -- the "found" case for BOTH
# peek-pause-record (needs `.record.gate_id`) and read-pause-record (reads
# `.record.context`, optionally). One shape satisfies both consumers.
GENUINE_FOUND_READ = {
    "exists": True,
    "stale": False,
    "record": {"gate_id": GATE_ID, "context": {}},
}

# A genuine, well-formed reply reporting NO pause record exists at all -- the
# actually-empty case this whole AC family exists to keep distinguishable
# from a refusal or a failure. Verbatim shape from BO-2300e-3's own
# it_requirements.
GENUINE_EMPTY_READ = {"exists": False, "stale": False, "record": None}

# The verbatim historical refusal text from the known issue this AC family
# fixes (docs/known-issues/.../open-blocker-ki-acd-20260928-...md, quoting
# the real run journal for wf_51a32979-97e). BO-2300e-3-i's own TEST
# STRATEGY it_requirement names this exact text. A free-text (non-JSON)
# refusal is returned as a plain string -- the same shape the pre-existing
# worktree-setup refusal precedent uses (~L2509-2532 of plan-feature.js: a
# STRING reply with no parseable JSON is wrapped as {message: rawText} and
# passed to isAgentRefusal()).
HISTORICAL_REFUSAL_TEXT = (
    "I'm the worktree lifecycle agent, scoped to two actions: create and remove."
)

# A reply that is not valid JSON at all (parseAgentJson has nothing to find a
# balanced {...}/[...] span in, so it throws "no parseable JSON"). Realistic
# shape for a command that crashed and printed a traceback to stdout instead
# of the expected JSON.
MALFORMED_REPLY_TEXT = (
    "Traceback (most recent call last):\n"
    '  File "pause_store.py", line 42, in <module>\n'
    "    raise OSError('lock file busy')\n"
    "OSError: lock file busy\n"
)

# "No reply at all" -- a JSON null value. Every reply-reading site's ternary
# falls through to using the raw value directly when it is not a string and
# has no `.stdout` string, so `null` reaches classification as a literal
# absence of any reply content, never a thrown parse error.
NO_REPLY = None


def transport_error_response(message: str) -> dict:
    """A label_responses value that makes the mocked agent() REJECT instead
    of resolving -- see unit_tests/_workflow_engine_harness.py's
    `__harness_agent_throws__` sentinel (added by this same AC's test-writer
    pass; DECISION HISTORY entry there explains why no pre-existing shape
    could represent this).
    """
    return {"__harness_agent_throws__": message}


# ---------------------------------------------------------------------------
# Hop drivers
# ---------------------------------------------------------------------------


def run_headless(run_id: str, label_responses: dict | None = None) -> HarnessResult:
    """Hop 1: a headless run that genuinely pauses at GATE_ID.

    Only "pause-persist-verify" needs a real, well-formed default -- every
    other pause-store label on this hop ("pause-persist" itself,
    "resolve-worktree-setup-script-path", "worktree-setup") already has a
    real default supplied by run_workflow_under_e2()'s own script-specific
    merge (see _plan_feature_harness_defaults.py).
    """
    merged = {"pause-persist-verify": GENUINE_PERSIST_VERIFY}
    merged.update(label_responses or {})
    return run_workflow_under_e2(
        PLAN_FEATURE_JS,
        timeout=TIMEOUT,
        label_responses=merged,
        args={
            "userInput": "Add a widget",
            "workspace_setup_permission": PERMIT_OK,
            "run_id": run_id,
        },
    )


def run_resume(
    run_id: str,
    label_responses: dict | None = None,
    *,
    gate_id: str = GATE_ID,
    isolate_other_label: bool = True,
) -> HarnessResult:
    """Hop 2: resume with a person-attributed `approve` answer for `gate_id`.

    When `isolate_other_label` is True (the default), BOTH peek-pause-record
    and read-pause-record are pre-seeded with GENUINE_FOUND_READ so a test
    stubbing only ONE of the two labels (via `label_responses`) is isolating
    that label's effect -- the caller's own override (merged on top) always
    wins for the label it names.
    """
    merged: dict = {}
    if isolate_other_label:
        merged["peek-pause-record"] = GENUINE_FOUND_READ
        merged["read-pause-record"] = GENUINE_FOUND_READ
    merged.update(label_responses or {})
    approve_answer = {
        "gate_id": gate_id,
        "type": "single_choice",
        "action": "approve",
        "channel": "person",
    }
    return run_workflow_under_e2(
        PLAN_FEATURE_JS,
        timeout=TIMEOUT,
        label_responses=merged,
        args={
            "userInput": "Add a widget",
            "workspace_setup_permission": PERMIT_OK,
            "run_id": run_id,
            "resume_answer": approve_answer,
        },
    )


def paused_at_gate(run_id: str, label_responses: dict | None = None) -> HarnessResult:
    """Run hop 1 and assert it genuinely reached "paused_awaiting_input" at
    GATE_ID, returning that hop's HarnessResult. Every test in this family
    calls this first -- a failure here means the SCENARIO setup is broken,
    not the fix under test, so it is asserted eagerly with a clear message.
    """
    hop1 = run_headless(run_id, label_responses)
    assert hop1.error == "", f"Harness error on hop 1: {hop1.error}"
    assert isinstance(hop1.result, dict), (
        f"Expected hop 1 to return a terminal payload dict. Got: {hop1.result!r}"
    )
    assert hop1.result.get("status") == "paused_awaiting_input", (
        "Scenario setup failed: hop 1 must genuinely pause at "
        f"'{GATE_ID}' for hop 2 to have anything to resume. "
        f"Got terminal payload: {hop1.result!r}"
    )
    assert hop1.result.get("gate_id") == GATE_ID, (
        f"Expected hop 1 to pause at '{GATE_ID}'. Got: {hop1.result!r}"
    )
    return hop1


# ---------------------------------------------------------------------------
# Observation helpers
# ---------------------------------------------------------------------------


def classification_text(result: HarnessResult) -> str:
    """Concatenate every string field of a terminal payload dict (or "" for
    a non-dict/None payload) so a test can substring-search across whichever
    field the eventual fix chooses to carry the "could not determine..."
    wording in -- this AC's own TEST STRATEGY deliberately does not pin one
    exact field or one exact status token (see BO-2300e-3's it_requirements:
    "assert the workflow's resulting classification ... Do not grep the
    source for a status string" -- the same latitude applies to which
    payload FIELD carries the text, not just to the source file).
    """
    payload = result.result
    if not isinstance(payload, dict):
        return ""
    parts = [str(v) for v in payload.values() if isinstance(v, str)]
    return " | ".join(parts)


def dispatched_labels(result: HarnessResult) -> list[str]:
    return [c.label for c in result.agent_calls if c.label]


def author_dispatch_count(result: HarnessResult, label: str = AUTHOR_LABEL) -> int:
    return dispatched_labels(result).count(label)
