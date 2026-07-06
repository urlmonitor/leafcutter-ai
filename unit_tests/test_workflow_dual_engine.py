"""
MODULE: test_workflow_dual_engine
GOAL: Order-aware CI guard — asserts that every *.js in templates/workflows-js/
    dispatches agents in the expected sequence under a stub E2 engine and uses
    array-form parallel() (not spread form).
BUSINESS CONTEXT: The live E2 workflow engine executes each script's top-level
    body with injected globals (agent, parallel, phase, log, args). Scripts that
    only define a `run()` function and never call agent() at the top level are
    silently inert under E2. This suite makes that failure CI-visible.

HARDENING (ticket 08) — two guard layers active (E1 ESM validity removed by
ticket 09 since the build is now E2-only):

  1. Parallel contract (AC-1 / H-5): The hardened harness parallel() mock
     requires an ARRAY of thunks. Spread-form calls record a contract violation.
     build-epic.js currently uses spread-form parallel — test marked
     xfail(strict=True) as the explicit RED baseline (H-5).

  2. Ordered dispatch (AC-2 / M-1): For build-epic.js and plan-feature.js the
     guard now asserts the FULL ordered (agentType, label) sequence, not just
     dispatch_count >= 1. A missing or reordered dispatch fails the test.

Note (ticket 09): The E1 ESM validity tests (test_e1_import_validity, H-6
    baseline) have been removed. They tested raw E2 scripts under
    --input-type=module, which always xfailed because E2 scripts use top-level
    `return` (valid in E2 IIFE, invalid as ESM). In an E2-only build world,
    these tests are permanently moot and were removed to reduce noise.

ARCHITECTURE: Pure Python test — uses the _workflow_engine_harness module to
    run each script via a Node.js subprocess with no claude binary required.
    CI-safe: only Node.js (standard CI dependency) is needed.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

import pytest

from _workflow_engine_harness import (
    HarnessResult,
    run_workflow_under_e2,
)

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOWS_DIR = _REPO_ROOT / "templates" / "workflows-js"

# ---------------------------------------------------------------------------
# Scripts known to be E1-only under E2 (dispatch 0 agents from top-level body).
# These are xfail(strict=True): expected to fail NOW; will become errors when
# tickets 05/06 port them to the E2 contract and they start passing.
# ---------------------------------------------------------------------------

_E1_ONLY_SCRIPTS = frozenset(
    [
        "create-ticket.js",
    ]
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_workflow_scripts() -> list[Path]:
    """Return all *.js files under templates/workflows-js/, sorted by name.

    Returns:
        Sorted list of .js file paths. Empty if the directory is absent.
    """
    if not _WORKFLOWS_DIR.exists():
        return []
    return sorted(_WORKFLOWS_DIR.glob("*.js"))


def _make_params(scripts: list[Path]) -> list[pytest.param]:
    """Build a pytest.param list, tagging E1-only scripts with xfail(strict=True).

    E1-only scripts are expected to fail (dispatch 0 agents) under the E2
    engine. Marking them with ``strict=True`` means an unexpected pass —
    produced when tickets 05/06 port the script to E2 — immediately becomes
    a test error, prompting the developer to remove the script from
    ``_E1_ONLY_SCRIPTS``.

    Args:
        scripts: Sorted list of .js file paths to parametrize.

    Returns:
        List of ``pytest.param`` instances, one per script.
    """
    params = []
    for script_path in scripts:
        name = script_path.name
        if name in _E1_ONLY_SCRIPTS:
            params.append(
                pytest.param(
                    script_path,
                    marks=pytest.mark.xfail(
                        strict=True,
                        reason=(
                            f"{name} uses the E1 contract (defines run() only). "
                            "It dispatches 0 agents under E2. "
                            "Port to E2 in EPIC-DualEngineWorkflowSupport tickets 05/06."
                        ),
                    ),
                )
            )
        else:
            params.append(pytest.param(script_path))
    return params


def _script_id(script_path: Path) -> str:
    """Return a short pytest ID for a workflow script path.

    Args:
        script_path: Path to the .js workflow script.

    Returns:
        Bare filename (e.g. ``"quick-fix.js"``).
    """
    return script_path.name


# ---------------------------------------------------------------------------
# AC-3: Guard covers the whole fleet
# ---------------------------------------------------------------------------


def test_workflows_dir_exists() -> None:
    """templates/workflows-js/ directory must exist and contain *.js files.

    Satisfies AC-3: guard covers the whole fleet — if the directory is absent
    or empty the entire suite would vacuously pass, hiding the problem.
    """
    assert _WORKFLOWS_DIR.exists(), (
        f"Workflow scripts directory not found: {_WORKFLOWS_DIR}\n"
        "The dual-engine guard requires templates/workflows-js/ to exist."
    )
    scripts = list(_WORKFLOWS_DIR.glob("*.js"))
    assert len(scripts) > 0, (
        f"No *.js files found in {_WORKFLOWS_DIR}.\n"
        "The dual-engine guard requires at least one workflow script."
    )


# ---------------------------------------------------------------------------
# AC-1 + AC-2 + AC-3: Per-script E2 dispatch assertion
# ---------------------------------------------------------------------------


def _make_e2_dispatch_test(script_path: Path) -> None:
    """Core assertion: a workflow script must dispatch >= 1 agent under E2.

    This function is called directly by each parametrized test case. It runs
    the script through the E2 stub harness and asserts dispatch_count >= 1.

    Args:
        script_path: Absolute path to the .js workflow script under test.
    """
    result: HarnessResult = run_workflow_under_e2(script_path)

    assert result.error == "", (
        f"{script_path.name}: harness error — {result.error}\n"
        f"stderr: {result.stderr[:500]}"
    )

    assert result.dispatch_count >= 1, (
        f"{script_path.name} dispatched 0 agents under the E2 engine.\n\n"
        f"This means the script only defines a run() function and never calls\n"
        f"agent() at the top-level body — it is silently inert under E2.\n\n"
        f"Fix: port the script to the E2 contract so top-level body code calls\n"
        f"agent() directly (see tickets 05/06 in EPIC-DualEngineWorkflowSupport).\n\n"
        f"Node stderr: {result.stderr[:300]}"
    )


# ---------------------------------------------------------------------------
# Parametrize: one test per *.js file
# ---------------------------------------------------------------------------

_ALL_SCRIPTS = _collect_workflow_scripts()
_ALL_PARAMS = _make_params(_ALL_SCRIPTS)

# Emit a clear collection-time warning if the fleet is empty so CI does not
# silently pass with no tests.
if not _ALL_SCRIPTS:
    import warnings

    warnings.warn(
        "No *.js workflow scripts found in templates/workflows-js/. "
        "The dual-engine guard suite will run zero tests.",
        stacklevel=1,
    )


@pytest.mark.parametrize("script_path", _ALL_PARAMS, ids=_script_id)
def test_e2_dispatch_count(script_path: Path) -> None:
    """Every workflow script must dispatch >= 1 agent under the E2 engine.

    E1-only scripts (those that only define a ``run()`` function without
    top-level agent calls) are marked ``xfail(strict=True)`` at parametrize
    time via ``pytest.param(..., marks=...)``. When tickets 05/06 port an
    E1-only script to the E2 contract, pytest will report an XPASS and — due
    to ``strict=True`` — that XPASS becomes an error, prompting the developer
    to remove the script from ``_E1_ONLY_SCRIPTS``.

    AC-1: harness captures agent() calls from top-level body execution.
    AC-2: zero-dispatch is a failure — the test fails naming the script.
    AC-3: every *.js in templates/workflows-js/ is asserted.

    Args:
        script_path: Parametrized path to the workflow script under test.
    """
    _make_e2_dispatch_test(script_path)


# ---------------------------------------------------------------------------
# AC-1: Explicit harness smoke test (not parametrized)
# ---------------------------------------------------------------------------


def test_harness_captures_agent_calls_from_e2_script() -> None:
    """Harness correctly captures agent() calls from an E2-form script.

    Uses quick-fix.js as the canonical E2 example: it has top-level body code
    that calls agent() directly. The harness must capture >= 1 call.

    Satisfies AC-1: harness executes a workflow under the E2 contract and
    records every agent() call with its (prompt, opts) tuple.
    """
    quick_fix = _WORKFLOWS_DIR / "quick-fix.js"
    if not quick_fix.exists():
        pytest.skip(f"quick-fix.js not found at {quick_fix}")

    result = run_workflow_under_e2(quick_fix)

    assert result.error == "", (
        f"Harness error while running quick-fix.js: {result.error}"
    )
    assert result.dispatch_count >= 1, (
        f"quick-fix.js dispatched 0 agents under E2 — harness may be broken.\n"
        f"stderr: {result.stderr[:300]}"
    )

    # Verify at least the first captured call has a non-empty prompt.
    first_call = result.agent_calls[0]
    assert first_call.prompt is not None, (
        "First captured agent() call has a None prompt — harness capture broken."
    )


# ---------------------------------------------------------------------------
# AC-2: Explicit zero-dispatch failure test (not parametrized)
# ---------------------------------------------------------------------------


def test_zero_dispatch_script_fails_guard() -> None:
    """A script whose top-level body dispatches no agents FAILS the guard.

    Uses create-ticket.js as the canonical E1-only example: it defines
    ``async function run({agent})`` but has no top-level agent() calls.
    The assertion must fail (zero dispatches), confirming AC-2.

    This test asserts the failure itself — it is the meta-test that proves the
    guard is not vacuously passing for inert scripts.

    Note: build-epic.js, build-ticket.js, plan-feature.js, and
    finalize-feature.js have all been ported to E2 (tickets 05/06) and now
    dispatch >= 1 agent from their top-level bodies. create-ticket.js remains
    E1-only and serves as the zero-dispatch reference for this test.
    """
    create_ticket = _WORKFLOWS_DIR / "create-ticket.js"
    if not create_ticket.exists():
        pytest.skip(f"create-ticket.js not found at {create_ticket}")

    result = run_workflow_under_e2(create_ticket)

    assert result.error == "", (
        f"Harness error while running create-ticket.js: {result.error}"
    )
    # This is the key assertion for AC-2: create-ticket.js dispatches 0 agents.
    # If this fails (dispatch_count > 0), create-ticket.js has been ported to E2
    # and the xfail marker in test_e2_dispatch_count should be removed.
    assert result.dispatch_count == 0, (
        f"create-ticket.js unexpectedly dispatched {result.dispatch_count} agents "
        f"under E2. It may have been ported to the E2 contract. "
        f"Remove it from _E1_ONLY_SCRIPTS and update this test."
    )


# ---------------------------------------------------------------------------
# AC-1 (hardening): parallel() contract — array form required (H-5)
# ---------------------------------------------------------------------------


def test_parallel_contract_violation_recorded_for_spread_form() -> None:
    """Hardened parallel() mock records a contract violation for spread-form calls.

    Creates a minimal synthetic script that calls parallel() with spread args
    (the H-5 pattern) and asserts that the hardened harness records a contract
    violation rather than silently executing the thunks.

    This test is always expected to PASS (it directly validates the harness
    hardening mechanism itself). It is NOT marked xfail — the violation
    detection is the correct behaviour.

    AC-1 (hardening): spread-form parallel() records a violation.
    """
    # Minimal synthetic E2 script that uses the H-5 spread form.
    # This mirrors the pattern in build-epic.js:
    #   parallel(...chunk.map((ticket) => async () => agent(...)))
    spread_form_script = (
        "// Synthetic script: spread-form parallel (H-5 pattern)\n"
        "const thunks = ['a', 'b'].map((x) => async () => {\n"
        "  return await agent('test ' + x, {agentType: 'ticket-supervisor', label: 'test-' + x});\n"
        "});\n"
        "const results = await parallel(...thunks);\n"
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".js", prefix="harness_test_", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(spread_form_script)
        tmp_path = Path(tmp.name)

    try:
        result = run_workflow_under_e2(tmp_path)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass

    assert result.error == "", (
        f"Harness error during spread-form parallel test: {result.error}"
    )
    assert len(result.contract_violations) > 0, (
        "Hardened parallel() mock must record a contract violation when called "
        "with spread args (parallel(...thunks) rather than parallel(thunks)).\n"
        "This is the H-5 defect pattern. No violation was recorded — the harness "
        "hardening may not be active."
    )

    # Verify the violation has the expected structure.
    violation = result.contract_violations[0]
    assert violation.get("type") == "parallel-non-array", (
        f"Expected violation type 'parallel-non-array', got: {violation.get('type')!r}\n"
        f"Full violation: {violation}"
    )
    assert "detail" in violation, (
        "Contract violation must include a 'detail' field explaining the issue."
    )


def test_parallel_array_form_runs_thunks() -> None:
    """Correct array-form parallel() executes all thunks without recording violations.

    Creates a minimal synthetic script that calls parallel([thunkA, thunkB])
    (the correct E2 form) and verifies that the hardened harness:
      - Records no contract violations.
      - Captures agent() calls from all thunks.

    AC-1 (hardening): array-form parallel() runs correctly.
    """
    array_form_script = (
        "// Synthetic script: correct array-form parallel (E2 contract)\n"
        "const results = await parallel([\n"
        "  async () => agent('prompt-a', {agentType: 'ticket-supervisor', label: 'thunk-a'}),\n"
        "  async () => agent('prompt-b', {agentType: 'ticket-supervisor', label: 'thunk-b'}),\n"
        "]);\n"
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".js", prefix="harness_test_", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(array_form_script)
        tmp_path = Path(tmp.name)

    try:
        result = run_workflow_under_e2(tmp_path)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass

    assert result.error == "", (
        f"Harness error during array-form parallel test: {result.error}"
    )
    assert len(result.contract_violations) == 0, (
        "Correct array-form parallel() must NOT record any contract violations.\n"
        f"Violations recorded: {result.contract_violations}"
    )
    assert result.dispatch_count == 2, (
        f"Array-form parallel() with 2 thunks must dispatch exactly 2 agents; "
        f"got {result.dispatch_count}.\n"
        f"Calls: {[(c.agent_type, c.label) for c in result.agent_calls]}"
    )


# ---------------------------------------------------------------------------
# AC-1 / H-5: build-epic.js parallel regression baseline (RED — xfail)
# ---------------------------------------------------------------------------


def test_build_epic_parallel_contract_baseline() -> None:
    """RED baseline: build-epic.js uses spread-form parallel (H-5 defect).

    Runs build-epic.js under the hardened harness with fake planner output
    that returns a non-empty batch (necessary to reach the parallel() call —
    the default stub planner returns no batches and the script exits early).

    The hardened parallel() mock records a violation when parallel() receives
    a function (not an array) as its first argument. The test asserts no
    violations exist — which FAILS because build-epic uses spread form.

    This xfail(strict=True) is the RED baseline for H-5. It will XPASS (and
    become a test error) once ticket 10 fixes build-epic.js to use array-form
    parallel. At that point, remove this test's xfail marker.
    """
    build_epic = _WORKFLOWS_DIR / "build-epic.js"
    if not build_epic.exists():
        pytest.skip(f"build-epic.js not found at {build_epic}")

    # Provide fake planner output so the script reaches the parallel() dispatch.
    # Without this, the planner returns the default stub (no `batches` field)
    # and the script exits at the "no batches" guard before calling parallel().
    fake_planner_response = {
        "epic_path": "test-epic",
        "title": "Test Epic",
        "batches": [
            {
                "batch_number": 1,
                "tickets": [
                    {"path": "01_test.md", "status": "todo"},
                    {"path": "02_test.md", "status": "todo"},
                ],
            }
        ],
    }

    result = run_workflow_under_e2(
        build_epic,
        label_responses={"epic-planner": fake_planner_response},
    )

    assert result.error == "", (
        f"build-epic.js: harness error — {result.error}\n"
        f"stderr: {result.stderr[:300]}"
    )

    # This assertion FAILS against the current build-epic.js because
    # parallel(...chunk.map(...)) triggers a contract violation.
    # Expected outcome: xfail (FAIL is the correct red baseline).
    assert len(result.contract_violations) == 0, (
        f"build-epic.js parallel() contract violation detected (H-5 baseline):\n"
        f"{result.contract_violations}\n\n"
        f"build-epic.js uses spread-form parallel(...chunk.map(...)) instead of "
        f"array-form parallel(chunk.map(...)). Fix in ticket 10."
    )


# ---------------------------------------------------------------------------
# AC-2 / M-1: Ordered dispatch sequence assertions
# ---------------------------------------------------------------------------


def test_dispatch_order_build_epic() -> None:
    """build-epic.js dispatches agents in the expected order (Phase 0 + Phase 1).

    With default stub args (no `epic_path` in args, `userInput` = 'stub user input',
    no `batches` from the planner) build-epic.js:

      Phase 0 (Worktree Guard):
        1. status-checker  label='worktree-check'  — git context check

      Phase 1 (Planner):
        2. status-checker  label='epic-planner'    — reads Master_Plan.md

      → Exits early (planner stub returns no batches)

    A reordered or missing dispatch FAILS this test (AC-2 / M-1 fix).

    Args:
        None (uses the fixed workflow script path from module scope).
    """
    build_epic = _WORKFLOWS_DIR / "build-epic.js"
    if not build_epic.exists():
        pytest.skip(f"build-epic.js not found at {build_epic}")

    result = run_workflow_under_e2(build_epic)

    assert result.error == "", (
        f"build-epic.js harness error: {result.error}\nstderr: {result.stderr[:300]}"
    )

    # build-epic.js must dispatch at least 2 agents (worktree-check + epic-planner)
    # before the no-batches early exit.
    assert result.dispatch_count >= 2, (
        f"build-epic.js must dispatch >= 2 agents with default args "
        f"(worktree-check + epic-planner before no-batches early exit). "
        f"Got {result.dispatch_count}.\n"
        f"Calls: {[(c.agent_type, c.label) for c in result.agent_calls]}"
    )

    # Assert the exact ordered sequence (agentType, label) for the first two calls.
    expected_sequence = [
        ("status-checker", "worktree-check"),
        ("status-checker", "epic-planner"),
    ]
    actual_sequence = [
        (c.agent_type, c.label) for c in result.agent_calls[:2]
    ]

    assert actual_sequence == expected_sequence, (
        f"build-epic.js dispatch order wrong (AC-2 / M-1).\n"
        f"Expected: {expected_sequence}\n"
        f"Actual:   {actual_sequence}\n"
        f"Full sequence: {[(c.agent_type, c.label) for c in result.agent_calls]}"
    )


def test_dispatch_order_plan_feature() -> None:
    """plan-feature.js dispatches agents in the expected full sequence.

    With default stub args (userInput='stub user input', no run_id):

      Pre-Stage-0:
        1. status-checker  label='detect-current-branch'
        2. status-checker  label='worktree-setup'

      Orphan scan (scanOrphanedAcDrafts):
        3. status-checker  label='scan-orphans-git-status'

      Stage detection (scanCommittedStages):
        4. status-checker  label='scan-committed-stages'

      Stage 0:
        5. ac-triage       label='stage-0-triage'

      Authoring (it-po, technical route — ac-triage stub returns no 'route'):
        6. it-po           label='stage-itpo-author'

      Final gate (stub returns action=defer):
        7. status-checker  label='final-gate'

    A dropped, reordered, or mis-typed agent type FAILS this test (AC-2 / M-1).
    """
    plan_feature = _WORKFLOWS_DIR / "plan-feature.js"
    if not plan_feature.exists():
        pytest.skip(f"plan-feature.js not found at {plan_feature}")

    result = run_workflow_under_e2(plan_feature)

    assert result.error == "", (
        f"plan-feature.js harness error: {result.error}\nstderr: {result.stderr[:300]}"
    )

    expected_sequence = [
        ("status-checker", "detect-current-branch"),
        ("status-checker", "worktree-setup"),
        ("status-checker", "scan-orphans-git-status"),
        ("status-checker", "scan-committed-stages"),
        ("ac-triage", "stage-0-triage"),
        ("it-po", "stage-itpo-author"),
        ("status-checker", "final-gate"),
    ]

    actual_count = result.dispatch_count
    assert actual_count >= len(expected_sequence), (
        f"plan-feature.js must dispatch >= {len(expected_sequence)} agents. "
        f"Got {actual_count}.\n"
        f"Calls: {[(c.agent_type, c.label) for c in result.agent_calls]}"
    )

    actual_sequence = [
        (c.agent_type, c.label)
        for c in result.agent_calls[: len(expected_sequence)]
    ]

    assert actual_sequence == expected_sequence, (
        f"plan-feature.js dispatch order wrong (AC-2 / M-1).\n"
        f"Expected:\n  {expected_sequence}\n"
        f"Actual:\n  {actual_sequence}\n"
        f"Full sequence ({actual_count} calls):\n"
        f"  {[(c.agent_type, c.label) for c in result.agent_calls]}"
    )

    # Also verify no contract violations from plan-feature.js.
    assert len(result.contract_violations) == 0, (
        f"plan-feature.js recorded parallel() contract violations (unexpected):\n"
        f"{result.contract_violations}"
    )


# ---------------------------------------------------------------------------
# M-2: no-commit-to-main guard must be fail-CLOSED (RED baseline — ticket 10)
# ---------------------------------------------------------------------------


def test_plan_feature_commit_guard_fail_closed_when_worktree_unparseable() -> None:
    """plan-feature.js no-commit-to-main guard must be fail-CLOSED (M-2).

    When the worktree setup returns an unparseable payload (null/malformed), the
    commit guard must REFUSE to commit rather than proceeding on an unconfirmable
    branch. This is a safety control — fail-closed is mandatory.

    RED baseline (ticket 10): the current implementation skips the branch check
    entirely when authoringWorktreePath is null, allowing a commit on unknown branch.
    The test asserts the script refuses; the current code violates this — test is RED.
    After ticket 10 fixes the guard, this test should turn GREEN.
    """
    plan_feature = _WORKFLOWS_DIR / "plan-feature.js"
    if not plan_feature.exists():
        pytest.skip(f"plan-feature.js not found at {plan_feature}")

    # Inject a worktree-setup response that returns unparseable output (exit_code 0
    # but output is empty/unparseable JSON) — simulates a broken worktree payload.
    # The branch-check agent should then refuse to commit (fail-closed).
    # Note: we also need to inject the detect-current-branch response so the script
    # doesn't short-circuit before reaching commitStageOutput.
    label_responses = {
        "worktree-setup": {
            "exit_code": 0,
            "output": "",  # unparseable — wtPayload will be null
            "stderr": "",
        },
        # The scan-orphans step needs a git status response.
        "scan-orphans-git-status": {"exit_code": 0, "output": ""},
        # The scan-committed-stages step needs a git log response.
        "scan-committed-stages": {"exit_code": 0, "output": ""},
        # The final-gate: return 'approve' so the script reaches the commit path.
        "final-gate": {"action": "approve", "priority": "medium"},
        # The apply-approval step: return ok.
        "apply-approval": {"status": "ok", "updated": []},
        # The commit-stage-output agent (label: 'commit-stage-output'):
        # We want to see that the branch check fires BEFORE the commit agent.
        # If the guard is fail-closed, it should return error before calling commit.
        # Leave as default (status: ok) — the test asserts the GUARD fires, not the commit.
    }

    result = run_workflow_under_e2(plan_feature, label_responses=label_responses)

    assert result.error == "", (
        f"Harness error: {result.error}\nstderr: {result.stderr[:300]}"
    )

    # Verify the script dispatched at least the expected early agents.
    assert result.dispatch_count >= 1, (
        f"plan-feature.js must dispatch at least 1 agent. Got {result.dispatch_count}."
    )

    # The commit should NOT have been dispatched when worktree is unparseable.
    # A fail-closed guard returns error before calling the commit agent.
    commit_calls = [
        c for c in result.agent_calls
        if c.label == "commit-stage-output"
    ]
    assert len(commit_calls) == 0, (
        f"M-2: no-commit-to-main guard is fail-OPEN. "
        f"plan-feature.js dispatched 'commit-stage-output' ({len(commit_calls)} time(s)) "
        f"even though the worktree payload was unparseable (authoringWorktreePath=null). "
        f"The guard must be fail-CLOSED: refuse to commit when branch cannot be confirmed.\n"
        f"All calls: {[(c.agent_type, c.label) for c in result.agent_calls]}"
    )


# ---------------------------------------------------------------------------
# AC-1/AC-2/AC-3: meta-pure-literal guard
#
# The Claude Code Workflow engine statically parses `export const meta` and
# rejects any non-literal node type (BinaryExpression, Identifier,
# CallExpression, TemplateLiteral with substitutions). A script whose meta
# contains string concatenation (`"a" + "b"`) will FAIL TO LOAD under the
# real engine, silently passing the stub-harness dispatch tests.
#
# This guard catches that class of failure statically in CI.
# ---------------------------------------------------------------------------


def _extract_meta_block(source: str) -> str | None:
    """Extract the text of the `export const meta = { ... }` block.

    Uses a character-level state machine to handle nested braces and string
    literals correctly. Returns None if no meta block is found.

    Args:
        source: JavaScript source text to search.

    Returns:
        The meta block text (from the opening ``{`` through the closing ``}``),
        or None if no ``export const meta`` declaration is found.
    """
    match = re.search(r"\bexport\s+const\s+meta\s*=\s*\{", source)
    if not match:
        return None

    brace_start = source.index("{", match.start())
    depth = 0
    in_str = False
    str_char: str | None = None
    i = brace_start
    while i < len(source):
        c = source[i]
        if in_str:
            # Escape sequences: skip the next character (not inside template literals).
            if c == "\\" and str_char != "`":
                i += 2
                continue
            if c == str_char:
                in_str = False
        else:
            if c in ('"', "'", "`"):
                in_str = True
                str_char = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return source[brace_start : i + 1]
        i += 1
    return None  # Unbalanced braces


def _check_meta_pure_literal_violations(script_path: Path) -> list[str]:
    """Return violations if ``meta.description`` is not a pure string literal.

    Statically analyses the ``export const meta`` block to detect:
    - BinaryExpression concatenation: ``+`` operator between string literals.
    - Template literal substitutions: ``${...}`` inside a backtick string.
    - Non-literal identifiers or call expressions (bare names after stripping
      string literal contents).

    This mirrors the Claude Code Workflow engine rule that rejects any
    non-literal node type in ``meta`` at script-load time.

    Args:
        script_path: Path to the ``.js`` workflow script.

    Returns:
        A list of human-readable violation strings. An empty list means
        ``meta.description`` is a pure literal (no violations detected).
    """
    try:
        source = script_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"Could not read {script_path.name}: {exc}"]

    meta_text = _extract_meta_block(source)
    if meta_text is None:
        return []  # No meta block — nothing to check.

    # Find the description: property inside the meta block.
    desc_match = re.search(r"\bdescription\s*:\s*", meta_text)
    if not desc_match:
        return []  # No description property — nothing to check.

    value_start = desc_match.end()

    # Extract the raw description value using a state machine.
    # The value ends at the first ``},`` or ``}`` at depth 0 (outside strings).
    in_str2 = False
    str_char2: str | None = None
    depth2 = 0
    value_chars: list[str] = []
    i = value_start
    while i < len(meta_text):
        c = meta_text[i]
        if in_str2:
            if c == "\\" and str_char2 != "`":
                # Escape: include both characters.
                value_chars.append(c)
                if i + 1 < len(meta_text):
                    value_chars.append(meta_text[i + 1])
                i += 2
                continue
            if c == str_char2:
                in_str2 = False
            value_chars.append(c)
        else:
            if c in ('"', "'"):
                in_str2 = True
                str_char2 = c
                value_chars.append(c)
            elif c == "`":
                in_str2 = True
                str_char2 = c
                value_chars.append(c)
            elif c == "{":
                depth2 += 1
                value_chars.append(c)
            elif c == "}":
                if depth2 == 0:
                    break  # End of meta block reached before a terminating comma.
                depth2 -= 1
                value_chars.append(c)
            elif c == "," and depth2 == 0:
                break  # End of this property value.
            else:
                value_chars.append(c)
        i += 1

    value_text = "".join(value_chars)

    # Build a "stripped" version with string literal CONTENTS removed.
    # This exposes operators, identifiers, and call expressions that would
    # make the value a non-literal (rejected by the Workflow engine).
    stripped_chars: list[str] = []
    in_str3 = False
    str_char3: str | None = None
    j = 0
    while j < len(value_text):
        c = value_text[j]
        if in_str3:
            if c == "\\" and str_char3 != "`":
                j += 2
                continue
            if c == str_char3:
                in_str3 = False
        else:
            if c in ('"', "'"):
                in_str3 = True
                str_char3 = c
            elif c == "`":
                in_str3 = True
                str_char3 = c
            else:
                stripped_chars.append(c)
        j += 1

    stripped = "".join(stripped_chars)
    violations: list[str] = []

    # AC-2 check 1: BinaryExpression — `+` concatenation operator outside strings.
    if "+" in stripped:
        violations.append(
            f"{script_path.name}: meta.description is a BinaryExpression — "
            "contains '+' concatenation operator. "
            "The Workflow engine statically parses meta and rejects BinaryExpression nodes. "
            f"Value preview: {value_text.strip()[:80]!r}"
        )

    # AC-2 check 2: TemplateLiteral with substitution — ${...} in raw value.
    if "${" in value_text:
        violations.append(
            f"{script_path.name}: meta.description contains a template literal "
            "substitution (${{...}}). The Workflow engine requires a pure literal "
            "with no substitutions. "
            f"Value preview: {value_text.strip()[:80]!r}"
        )

    # AC-2 check 3: Identifier or CallExpression — non-whitespace, non-operator
    # content after stripping strings.  ``+`` is already caught above; after
    # removing it and all whitespace/punctuation, any remaining word characters
    # indicate an identifier or call (both disallowed in meta).
    stripped_clean = re.sub(r"[\s+\-*/()[\]{},;]", "", stripped)
    if stripped_clean:
        violations.append(
            f"{script_path.name}: meta.description contains a non-literal "
            "identifier or call expression. "
            f"Non-string, non-operator content: {stripped_clean[:40]!r}. "
            "The Workflow engine requires a pure literal (single quoted string)."
        )

    return violations


# ---------------------------------------------------------------------------
# AC-3: Parametrized guard across the whole fleet
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "script_path",
    _collect_workflow_scripts(),
    ids=_script_id,
)
def test_meta_description_is_pure_literal(script_path: Path) -> None:
    """Every workflow script's meta.description must be a pure string literal.

    The Claude Code Workflow engine statically parses ``export const meta``
    and rejects any non-literal node type (BinaryExpression, Identifier,
    CallExpression, TemplateLiteral with substitutions). A script whose
    meta.description uses string concatenation (``"a" + "b"``) fails to load
    under the real engine, silently passing stub-harness dispatch tests.

    This guard catches that class of failure deterministically in CI.

    AC-1: pure-literal description is accepted (no violations).
    AC-2: non-literal description is rejected (violations listed, test fails).
    AC-3: every *.js in templates/workflows-js/ is checked.

    Args:
        script_path: Parametrized path to the workflow script under test.
    """
    violations = _check_meta_pure_literal_violations(script_path)
    assert violations == [], (
        f"{script_path.name}: meta.description is not a pure literal.\n\n"
        "The Workflow engine statically parses export const meta and rejects\n"
        "any non-literal node type (BinaryExpression, Identifier, CallExpression,\n"
        "TemplateLiteral with substitutions).\n\n"
        "Violations detected:\n"
        + "\n".join(f"  - {v}" for v in violations)
        + "\n\nFix: collapse the description into a single quoted string literal."
    )


# ---------------------------------------------------------------------------
# AC-2: Standalone negative test — guard rejects concatenated description
# ---------------------------------------------------------------------------


def test_meta_guard_rejects_concatenated_description() -> None:
    """meta-pure-literal guard FAILS for a script with concatenated meta.description.

    Creates a synthetic workflow script whose ``export const meta`` uses
    string concatenation (``'first part ' + 'second part'``) and asserts the
    guard returns at least one violation. This is the AC-2 "guard rejects
    non-literal meta" meta-test that proves the guard is not vacuously passing.

    AC-2: the guard must name the script and describe the BinaryExpression
    violation when concatenation is present.
    """
    # Synthetic E2 workflow script with a concatenated meta.description.
    synthetic_source = (
        "export const meta = {\n"
        "  name: 'test-workflow',\n"
        "  description: 'first part of the description ' +\n"
        "    'second part of the description',\n"
        "  phases: [],\n"
        "};\n"
        "\n"
        "// top-level body: dispatch at least one agent\n"
        "const result = await agent('stub prompt', {agentType: 'status-checker', label: 'stub'});\n"
    )

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".js",
        prefix="meta_guard_test_",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(synthetic_source)
        tmp_path = Path(tmp.name)

    try:
        violations = _check_meta_pure_literal_violations(tmp_path)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass

    assert len(violations) > 0, (
        "meta-pure-literal guard must detect concatenation in meta.description. "
        "A description with 'first part ' + 'second part' must be flagged as "
        "a BinaryExpression (non-pure literal)."
    )

    # The violation message must describe the problem clearly.
    violation_text = " ".join(violations)
    assert any(
        kw in violation_text
        for kw in ("BinaryExpression", "concatenat", "+")
    ), (
        f"Violation message must mention BinaryExpression, concatenation, or '+'. "
        f"Got: {violations!r}"
    )

