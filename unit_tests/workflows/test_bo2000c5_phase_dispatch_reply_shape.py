"""
MODULE: test_bo2000c5_phase_dispatch_reply_shape
GOAL: Regression test for BO-2000c-5 — the phase-dispatch prompts in
    templates/workflows-js/build-feature.js (and its declared twin
    templates/workflows-js/build-ticket.js) must instruct the dispatched
    agent to fill the reply tool's fields directly, never to "return a JSON
    result" as text.

BUG BEING REGRESSION-TESTED
    (docs/acceptance-criteria/build-orchestration/BO-2000-correct-prompts-by-construction/BO-2000c-5.yaml):

    Both the per-phase dispatch prompt (build-feature.js ~line 1893) and the
    handoff re-dispatch prompt (build-feature.js ~line 2082, and the mirrored
    lines in build-ticket.js) currently read:

        Return a JSON result with at minimum { "status": "ok" | "blocker" | "failed" }.

    The driver enforces the reply against PHASE_RESULT_SCHEMA through the
    reply TOOL, whose properties are the schema's fields — but the prompt
    describes the reply as JSON *text*. An agent that takes "return a JSON
    result" literally serialises its whole answer and passes it as a single
    string (observed: documentation-expert did this on all five retries in
    run wf_e1f3e873-096 on 2026-09-25; ac-fulfillment-gate once in
    wf_ee4e9d81-680). The schema rejected every attempt, the five-retry cap
    was hit, and the drive halted with the ticket's work already done. The
    prompt also never names `handoff` as a legal status or `handoff_target`
    as the field the driver routes re-dispatch on.

    Fix: reword both dispatch prompts (in both files) to tell the agent to
    fill the reply tool's fields directly -- `status` (ok | blocker | failed
    | handoff), `message`, and `handoff_target` -- and to never pass the
    reply as a JSON string or inside an `input` field.

WHY THIS TEST DRIVES THE REAL DRIVER RATHER THAN GREPPING THE SOURCE:

    Per the project's "Verify Behaviorally, Not by Grep" convention (see
    unit_tests/workflows/test_bo_3000_handoff_routing.py for the established
    pattern this file follows), the assertions below run the REAL
    build-feature.js / build-ticket.js scripts through the Node.js-backed E2
    stub harness (unit_tests/_workflow_engine_harness.py) and capture the
    literal `prompt` STRING the driver actually constructs and hands to
    agent() for a live phase dispatch and for a live handoff re-dispatch.
    A source-grep test would pass on a rewritten sentence sitting in dead
    code that no dispatch call site ever reaches; capturing the prompt the
    driver actually built and sent proves the fix is wired, not just present
    in the file.

    Each test also asserts a SANITY / negative-control fact about the same
    captured prompt (that it is non-empty and contains the ticket path the
    fixture supplied) — this is expected to PASS even before the fix. It
    proves the harness genuinely captured live dispatch content (ruling out
    an empty-fixture or harness-load-failure false pass/fail) so the
    bug-specific assertions below it are tied to the fix, not to a broken
    harness.

TICKET: BO-2000c-5
AC: docs/acceptance-criteria/build-orchestration/BO-2000-correct-prompts-by-construction/BO-2000c-5.yaml
"""

from __future__ import annotations

import sys
from pathlib import Path

# unit_tests/ must be on sys.path so _workflow_engine_harness is importable
# from this sub-package (unit_tests/workflows/).
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_BUILD_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "build-feature.js"
_BUILD_TICKET_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "build-ticket.js"

_TIMEOUT = 30  # seconds; all agent() calls are synchronous mocks

_TICKET_ABS_PATH = "/tmp/bo2000c5-worktree/tickets/01_todo/07_ticket.md"
_WORKTREE_ABS_PATH = "/tmp/bo2000c5-worktree"
# BO-4000: build-feature.js checks resolve-target's own worktree_path via a
# repo-facts call before reusing it; this reports it reusable so the run
# reuses _WORKTREE_ABS_PATH exactly as before that check existed.
_WORKTREE_FACTS_RESOLVED = {
    "output": (
        '{"exists": true, "is_git_toplevel": true, "is_linked_worktree": true, '
        '"is_main_checkout": false, "same_repository": true, "branch": "fixture"}'
    ),
    "exit_code": 0,
}

# The exact regressing sentence named in the AC. Its presence in a live
# dispatch prompt is the bug; its absence (replaced by reply-tool-field
# instructions) is the fix.
_REGRESSING_PHRASE = "Return a JSON result"

# Phrases the AC requires the FIXED prompt to carry: an instruction to fill
# the reply tool's fields directly, the full status enum including
# `handoff`, and an explicit prohibition on serialising the reply as a JSON
# string or nesting it under an `input` field.
_REQUIRED_FIX_PHRASES = (
    "fill the reply tool",
    "handoff_target",
    "json string",
    "input",
)


def _calls_with_label(result: HarnessResult, label: str) -> list:
    return [c for c in result.agent_calls if c.label == label]


def _dispatched_labels(result: HarnessResult) -> list:
    return [c.label for c in result.agent_calls]


def _assert_prompt_is_live_capture(prompt: str, ticket_path: str, context: str) -> None:
    """Negative control: prove the harness captured a real, non-empty prompt
    string that actually mentions the ticket this run dispatched for. This
    assertion is expected to PASS both before and after the fix -- it exists
    to rule out an empty fixture or a harness load failure producing a
    false result on the bug-specific assertions that follow it.
    """
    assert isinstance(prompt, str) and prompt.strip() != "", (
        f"{context}: expected a live, non-empty prompt string captured from "
        f"the real agent() dispatch, got: {prompt!r}"
    )
    assert ticket_path in prompt, (
        f"{context}: expected the captured prompt to reference the ticket "
        f"path {ticket_path!r} the fixture dispatched for (proves this is "
        f"the real dispatch prompt, not stray content). Prompt was:\n{prompt}"
    )


# ---------------------------------------------------------------------------
# Test 1 — build-feature.js: the MAIN per-phase dispatch prompt (the one at
# ~line 1891-1894) must not describe the reply as "a JSON result" and must
# instruct the agent to fill the reply tool's fields directly.
# ---------------------------------------------------------------------------


def test_build_feature_main_dispatch_prompt_directs_reply_tool_fields_not_json_string():
    # covers: BO-2000c-5
    # angle: reachability
    """AC BO-2000c-5: driving the REAL build-feature.js phase dispatch for a
    single needed phase (python-coder) must produce a prompt that instructs
    the agent to fill the reply tool's `status` / `message` /
    `handoff_target` fields directly, names `handoff` as a legal status, and
    never tells the agent to "return a JSON result" or serialise its reply
    as a JSON string / `input` field.

    RED (current, unmodified code): the driver builds the prompt
    `... Return a JSON result with at minimum { "status": "ok" | "blocker" |
    "failed" }.` -- it contains the regressing phrase, omits `handoff` /
    `handoff_target`, and never mentions the reply tool. Every fix-phrase
    assertion below fails against the unmodified driver.
    """
    label_responses = {
        "resolve-target": {
            "target_type": "ticket",
            "ticket_path": _TICKET_ABS_PATH,
            "worktree_path": _WORKTREE_ABS_PATH,
        },
        "worktree-facts-resolved": _WORKTREE_FACTS_RESOLVED,
        "worktree-setup": {
            "worktree_path": _WORKTREE_ABS_PATH,
            "status": "reused",
        },
        "ticket-planner": {
            "ticket_path": _TICKET_ABS_PATH,
            "title": "BO-2000c-5 regression fixture ticket",
            "files_touched": ["some/module.py"],
            "has_test_requirements": True,
            "existing_test_files": ["unit_tests/some_module/test_thing.py"],
            "ordered_phases": [
                {"agent": "python-coder", "status": "needed"},
            ],
        },
        "python-coder": {"status": "ok"},
    }

    result = run_workflow_under_e2(
        _BUILD_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=label_responses,
        args={"target": _TICKET_ABS_PATH},
    )
    assert result.error == "", f"Harness error: {result.error}"

    python_coder_calls = _calls_with_label(result, "python-coder")
    assert len(python_coder_calls) >= 1, (
        "Expected python-coder to be dispatched at least once via the real "
        f"phase-dispatch loop. Dispatched labels: {_dispatched_labels(result)}"
    )
    prompt = python_coder_calls[0].prompt

    _assert_prompt_is_live_capture(
        prompt, _TICKET_ABS_PATH, "build-feature.js main phase dispatch"
    )

    assert _REGRESSING_PHRASE not in prompt, (
        "The live build-feature.js phase-dispatch prompt still contains the "
        f"regressing phrase {_REGRESSING_PHRASE!r}, which tells the agent to "
        "serialise its reply as JSON text instead of filling the reply "
        "tool's fields. This is the exact defect BO-2000c-5 fixes (observed: "
        "documentation-expert returned its whole result as a single `input` "
        "string on all five retries in run wf_e1f3e873-096). Captured "
        f"prompt:\n{prompt}"
    )

    lowered = prompt.lower()
    for phrase in _REQUIRED_FIX_PHRASES:
        assert phrase in lowered, (
            f"The live build-feature.js phase-dispatch prompt is missing the "
            f"required fixed-wording fragment {phrase!r} (case-insensitive). "
            "The AC requires the prompt to instruct the agent to fill the "
            "reply tool's status/message/handoff_target fields directly and "
            "to forbid a JSON-string or `input`-wrapped reply. Captured "
            f"prompt:\n{prompt}"
        )

    assert "handoff" in lowered, (
        "The live build-feature.js phase-dispatch prompt does not name "
        "'handoff' as a legal status value, so an agent reading only the "
        f"prompt has no way to learn it may hand off. Captured prompt:\n{prompt}"
    )


# ---------------------------------------------------------------------------
# Test 2 — build-feature.js: the HANDOFF RE-DISPATCH prompt (the one at
# ~line 2082-2083, reached only when a phase returns status: "handoff")
# carries the identical regressing sentence split across two string lines
# and must receive the identical fix.
# ---------------------------------------------------------------------------


def test_build_feature_redispatch_prompt_directs_reply_tool_fields_not_json_string():
    # covers: BO-2000c-5
    # angle: reachability
    """AC BO-2000c-5: driving the REAL build-feature.js handoff re-dispatch
    path (python-coder hands off to test-writer) must produce a
    RE-DISPATCH prompt with the same reply-tool-field instruction as the
    main dispatch prompt -- this is a second, independently-composed prompt
    string in the same file and must not be missed by the fix.

    RED (current, unmodified code): the re-dispatch prompt ends with
    `... Return a JSON result with at minimum { "status": "ok" | "blocker" |
    "failed" }.` (built across two template-literal lines), so it fails the
    same fix-phrase assertions as the main dispatch prompt.
    """
    label_responses = {
        "resolve-target": {
            "target_type": "ticket",
            "ticket_path": _TICKET_ABS_PATH,
            "worktree_path": _WORKTREE_ABS_PATH,
        },
        "worktree-facts-resolved": _WORKTREE_FACTS_RESOLVED,
        "worktree-setup": {
            "worktree_path": _WORKTREE_ABS_PATH,
            "status": "reused",
        },
        "ticket-planner": {
            "ticket_path": _TICKET_ABS_PATH,
            "title": "BO-2000c-5 handoff-redispatch fixture ticket",
            "files_touched": ["some/module.py"],
            "has_test_requirements": True,
            "existing_test_files": ["unit_tests/some_module/test_thing.py"],
            "ordered_phases": [
                {"agent": "test-writer", "status": "needed"},
                {"agent": "python-coder", "status": "needed"},
            ],
        },
        "test-writer": {
            "status": "ok",
            "tests_written": ["unit_tests/some_module/test_thing.py"],
            "red_baseline_verified": True,
        },
        "python-coder": {
            "status": "handoff",
            "handoff_target": "test-writer",
            "message": "test-writer must update one stale assertion first.",
        },
    }

    result = run_workflow_under_e2(
        _BUILD_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=label_responses,
        args={"target": _TICKET_ABS_PATH},
    )
    assert result.error == "", f"Harness error: {result.error}"

    test_writer_calls = _calls_with_label(result, "test-writer")
    assert len(test_writer_calls) >= 2, (
        "Expected test-writer to be dispatched twice: once for its normal "
        "phase turn, and once more as the handoff RE-DISPATCH that carries "
        f"the second regressing prompt. Dispatched labels: "
        f"{_dispatched_labels(result)}"
    )
    # The re-dispatch call is the LAST test-writer call (the first is the
    # ordinary phase turn earlier in phaseOrder).
    prompt = test_writer_calls[-1].prompt

    _assert_prompt_is_live_capture(
        prompt, _TICKET_ABS_PATH, "build-feature.js handoff re-dispatch"
    )

    assert _REGRESSING_PHRASE not in prompt, (
        "The live build-feature.js handoff RE-DISPATCH prompt still "
        f"contains the regressing phrase {_REGRESSING_PHRASE!r}. This is a "
        "second, independently-built prompt string in the same file (the "
        "one guarding the handoff re-dispatch, ~line 2082-2083) and the AC "
        f"requires it to receive the identical fix. Captured prompt:\n{prompt}"
    )

    lowered = prompt.lower()
    for phrase in _REQUIRED_FIX_PHRASES:
        assert phrase in lowered, (
            f"The live build-feature.js handoff re-dispatch prompt is "
            f"missing the required fixed-wording fragment {phrase!r} "
            f"(case-insensitive). Captured prompt:\n{prompt}"
        )


# ---------------------------------------------------------------------------
# Test 3 — build-ticket.js: the declared twin carries the identical
# regressing sentence in its own main phase-dispatch prompt and must receive
# the identical fix (the AC names this twin explicitly, and its edit is
# "expected and approved as part of this fix").
# ---------------------------------------------------------------------------


def test_build_ticket_main_dispatch_prompt_directs_reply_tool_fields_not_json_string():
    # covers: BO-2000c-5
    # angle: reachability
    """AC BO-2000c-5: the declared twin driver templates/workflows-js/build-ticket.js
    carries the identical 'Return a JSON result with at minimum { "status":
    ... }' sentence in its own phase-dispatch prompt and must be fixed the
    same way, so the two drivers cannot diverge.

    `args.worktree_path` is supplied so the ambient worktree-check agent()
    call is skipped (build-ticket.js Phase 0 trusts a caller-supplied path),
    isolating the assertion to the dispatch-prompt wording itself -- the
    same isolation unit_tests/workflows/test_bo_3000_handoff_routing.py uses
    for build-ticket.js.

    RED (current, unmodified code): identical failure mode to Test 1, in
    the sibling file.
    """
    label_responses = {
        "ticket-planner": {
            "ticket_path": _TICKET_ABS_PATH,
            "title": "BO-2000c-5 regression fixture ticket (build-ticket.js)",
            "files_touched": ["some/module.py"],
            "has_test_requirements": True,
            "existing_test_files": ["unit_tests/some_module/test_thing.py"],
            "ordered_phases": [
                {"agent": "python-coder", "status": "needed"},
            ],
        },
        "python-coder": {"status": "ok"},
    }

    result = run_workflow_under_e2(
        _BUILD_TICKET_JS,
        timeout=_TIMEOUT,
        label_responses=label_responses,
        args={
            "ticket_path": _TICKET_ABS_PATH,
            "worktree_path": _WORKTREE_ABS_PATH,
        },
    )
    assert result.error == "", f"Harness error: {result.error}"

    python_coder_calls = _calls_with_label(result, "python-coder")
    assert len(python_coder_calls) >= 1, (
        "Expected python-coder to be dispatched at least once via the real "
        f"phase-dispatch loop. Dispatched labels: {_dispatched_labels(result)}"
    )
    prompt = python_coder_calls[0].prompt

    _assert_prompt_is_live_capture(
        prompt, _TICKET_ABS_PATH, "build-ticket.js main phase dispatch"
    )

    assert _REGRESSING_PHRASE not in prompt, (
        "The live build-ticket.js phase-dispatch prompt still contains the "
        f"regressing phrase {_REGRESSING_PHRASE!r}. build-ticket.js is the "
        "declared twin of build-feature.js and carries the identical "
        f"defect. Captured prompt:\n{prompt}"
    )

    lowered = prompt.lower()
    for phrase in _REQUIRED_FIX_PHRASES:
        assert phrase in lowered, (
            f"The live build-ticket.js phase-dispatch prompt is missing the "
            f"required fixed-wording fragment {phrase!r} (case-insensitive). "
            f"Captured prompt:\n{prompt}"
        )
