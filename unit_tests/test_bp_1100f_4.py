"""
MODULE: test_bp_1100f_4
GOAL: Test stubs for AC BP-1100f-4 — The workflow test harness raises a
      contract violation on an instruction-less agent() dispatch.

These tests are expected to be RED before the python-coder phase because the
harness does not yet detect instruction-less first arguments.  The python-coder
must extend unit_tests/_workflow_engine_harness.py so the JS shim's agent()
mock pushes an entry with type='instruction_less_dispatch' into
__contractViolations__ whenever the first argument is not a non-empty string.

TICKET: TICKET-20260721-BP-1100f-4
ACs: BP-1100f-4, BP-1100f-4-i
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# _workflow_engine_harness lives in the same unit_tests/ directory as this file.
# Adding the directory to sys.path makes the import reliable regardless of
# which directory pytest is invoked from (mirrors the pattern in
# unit_tests/workflows/test_bo_2300_pause_resume.py).
_UNIT_TESTS_DIR = Path(__file__).resolve().parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_js(source: str, label_responses: dict | None = None) -> HarnessResult:
    """Write *source* to a temp .js file and execute it under the E2 harness.

    The temporary file is always deleted in the finally block — including when
    the harness raises an unexpected error — so no temp files accumulate across
    the test run.
    """
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".js",
        delete=False,
        encoding="utf-8",
    ) as fh:
        fh.write(source)
        tmp = Path(fh.name)
    try:
        return run_workflow_under_e2(tmp, label_responses=label_responses or {})
    finally:
        tmp.unlink(missing_ok=True)


def _instruction_less_violations(result: HarnessResult) -> list[dict]:
    """Return all contract_violations with type == 'instruction_less_dispatch'."""
    return [
        v for v in result.contract_violations
        if v.get("type") == "instruction_less_dispatch"
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_harness_raises_contract_violation_on_object_first_arg() -> None:
    # covers: BP-1100f-4
    """
    When a workflow dispatches agent() with a bare object as its first argument,
    the harness must record a contract_violation with
    type == 'instruction_less_dispatch'.

    RED before implementation: the harness does not yet check the first-arg type,
    so contract_violations will be empty and the assertion fails.

    To make this test green the python-coder must extend the JS shim's agent()
    mock to detect when promptOrOpts is not a non-empty string (i.e.
    typeof promptOrOpts !== 'string' || promptOrOpts.trim() === '') and push
    {type: 'instruction_less_dispatch', ...} into __contractViolations__.
    """
    js_source = "await agent({instruction: 'foo'}, {label: 'test-object-first-arg'});"
    result = _run_js(js_source)

    assert result.error == "", f"Harness error: {result.error}"
    violations = _instruction_less_violations(result)
    assert len(violations) > 0, (
        "Expected at least one contract_violation with "
        "type='instruction_less_dispatch' when agent() is called with a bare "
        "object as the first argument. "
        f"Got contract_violations: {result.contract_violations!r}. "
        "Implement the instruction-less dispatch check in the harness's agent() mock."
    )


def test_harness_raises_on_empty_first_arg() -> None:
    # covers: BP-1100f-4
    """
    When a workflow dispatches agent() with an empty string ('') or a
    whitespace-only string ('   ') as the first argument, the harness must
    record a contract_violation with type == 'instruction_less_dispatch'.

    RED before implementation: the harness treats any string as a valid
    instruction, so the violation is never raised.

    To make this test green the python-coder must extend the harness to treat
    empty-or-whitespace strings as instruction-less (in addition to non-strings).
    """
    # Case 1: empty string
    js_empty = "await agent('', {label: 'test-empty-string'});"
    result_empty = _run_js(js_empty)
    assert result_empty.error == "", (
        f"Harness error on empty-string case: {result_empty.error}"
    )
    violations_empty = _instruction_less_violations(result_empty)
    assert len(violations_empty) > 0, (
        "Expected an instruction_less_dispatch violation when agent() is called "
        "with an empty string ('') as the first argument. "
        f"Got contract_violations: {result_empty.contract_violations!r}."
    )

    # Case 2: whitespace-only string
    js_whitespace = "await agent('   ', {label: 'test-whitespace-string'});"
    result_ws = _run_js(js_whitespace)
    assert result_ws.error == "", (
        f"Harness error on whitespace-only case: {result_ws.error}"
    )
    violations_ws = _instruction_less_violations(result_ws)
    assert len(violations_ws) > 0, (
        "Expected an instruction_less_dispatch violation when agent() is called "
        "with a whitespace-only string ('   ') as the first argument. "
        f"Got contract_violations: {result_ws.contract_violations!r}."
    )


def test_harness_passes_nonempty_instruction_string() -> None:
    # covers: BP-1100f-4
    """
    When a workflow dispatches agent() with a non-empty instruction string, the
    harness must NOT raise an instruction_less_dispatch contract_violation and
    the agent call must be captured normally.

    NOTE — this test trivially passes before implementation (negative assertion):
    the harness currently raises NO instruction_less_dispatch violations, so the
    assertion that there are none is trivially satisfied.  The test is included
    to guarantee the feature does not regress valid dispatches once the
    instruction-less check is added.  The python-coder must ensure this test
    STAYS GREEN after implementing the check for the other three tests.

    This test is flagged in the red_baseline with
    'passes immediately — may be under-specified' per the test-writer protocol.
    """
    js_source = "await agent('Do some work', {label: 'test-valid-instruction'});"
    result = _run_js(js_source)

    assert result.error == "", f"Harness error: {result.error}"
    assert result.dispatch_count >= 1, (
        "Expected at least one agent() call to be captured for a valid instruction. "
        f"Got dispatch_count={result.dispatch_count}."
    )
    violations = _instruction_less_violations(result)
    assert len(violations) == 0, (
        "A non-empty instruction string must NOT trigger an "
        "instruction_less_dispatch violation. "
        f"Got unexpected violations: {violations!r}."
    )


def test_success_stub_does_not_suppress_instruction_less_violation() -> None:
    # covers: BP-1100f-4
    # covers: BP-1100f-4-i
    """
    When a workflow dispatches agent() with a bare object as the first argument
    AND the agent call's label is configured with a success stub in
    label_responses, the harness must STILL record an instruction_less_dispatch
    contract_violation.

    A success stub controls the RETURN VALUE of the agent() mock only.  It must
    not suppress the CONTRACT check.  The violation must fire unconditionally —
    before or independent of the __labelResponses__ lookup.

    RED before implementation: the harness agent() mock currently applies the
    label_responses lookup before any contract check (no check exists), so the
    stub is applied and no violation is raised.

    To make this test green the python-coder must ensure the instruction-less
    check fires BEFORE (or independently of) the __labelResponses__ lookup,
    so a success stub cannot mask an instruction-less dispatch.
    """
    js_source = "await agent({instruction: 'foo'}, {label: 'stubbed-call'});"
    label_responses = {"stubbed-call": {"status": "ok", "output": "stub-response"}}
    result = _run_js(js_source, label_responses=label_responses)

    assert result.error == "", f"Harness error: {result.error}"
    violations = _instruction_less_violations(result)
    assert len(violations) > 0, (
        "Expected an instruction_less_dispatch contract_violation even when the "
        "agent() call's label is configured with a success stub in label_responses. "
        "The success stub controls the return value, not the dispatch contract. "
        f"Got contract_violations: {result.contract_violations!r}. "
        "Ensure the instruction-less check fires before the __labelResponses__ lookup."
    )
