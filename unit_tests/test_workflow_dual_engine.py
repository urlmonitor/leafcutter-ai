"""
MODULE: test_workflow_dual_engine
GOAL: Order-aware CI guard — asserts that every *.js in templates/workflows-js/
    dispatches agents in the expected sequence under a stub E2 engine, uses
    array-form parallel() (not spread form), and is valid ES module syntax.
BUSINESS CONTEXT: The live E2 workflow engine executes each script's top-level
    body with injected globals (agent, parallel, phase, log, args). Scripts that
    only define a `run()` function and never call agent() at the top level are
    silently inert under E2. This suite makes that failure CI-visible.

HARDENING (ticket 08) — three new guard layers added on top of ticket 02:

  1. Parallel contract (AC-1 / H-5): The hardened harness parallel() mock
     requires an ARRAY of thunks. Spread-form calls record a contract violation.
     build-epic.js currently uses spread-form parallel — test marked
     xfail(strict=True) as the explicit RED baseline (H-5).

  2. Ordered dispatch (AC-2 / M-1): For build-epic.js and plan-feature.js the
     guard now asserts the FULL ordered (agentType, label) sequence, not just
     dispatch_count >= 1. A missing or reordered dispatch fails the test.

  3. E1 ESM validity (AC-4 / H-6): A new parametrized test tries every script
     under node --check --input-type=module (ES-module parse mode, which rejects
     top-level `return`). Scripts in E2 canonical form (all non-create-ticket.js)
     fail this check and are marked xfail(strict=True) as the H-6 baseline.

ARCHITECTURE: Pure Python test — uses the _workflow_engine_harness module to
    run each script via a Node.js subprocess with no claude binary required.
    CI-safe: only Node.js (standard CI dependency) is needed.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from _workflow_engine_harness import (
    E1CheckResult,
    HarnessResult,
    run_e1_import_check,
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
# Scripts that are E2-form but use top-level `return` (invalid ES module syntax).
# These fail `node --check --input-type=module` (H-6 baseline).
# Marked xfail(strict=True) so an XPASS triggers an error when ticket 09 fixes
# the E1 emission or the scripts are migrated to valid ESM form.
# ---------------------------------------------------------------------------

_E1_INVALID_SCRIPTS = frozenset(
    [
        "build-epic.js",
        "build-ticket.js",
        "finalize-feature.js",
        "plan-feature.js",
        "quick-fix.js",
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


def _make_e1_params(scripts: list[Path]) -> list[pytest.param]:
    """Build a pytest.param list for E1 import validity tests.

    Scripts in ``_E1_INVALID_SCRIPTS`` are marked xfail(strict=True): they
    currently fail ``node --check --input-type=module`` because they contain
    top-level ``return`` statements (valid in E2 engine IIFE wrapping but not
    in ES module parsing). When ticket 09 fixes the E1 emission to wrap these
    properly, the XPASS becomes an error and the script is removed from the set.

    ``create-ticket.js`` is E1 form (valid ESM) and is expected to pass.

    Args:
        scripts: Sorted list of .js file paths to parametrize.

    Returns:
        List of ``pytest.param`` instances, one per script.
    """
    params = []
    for script_path in scripts:
        name = script_path.name
        if name in _E1_INVALID_SCRIPTS:
            params.append(
                pytest.param(
                    script_path,
                    marks=pytest.mark.xfail(
                        strict=True,
                        reason=(
                            f"{name} is E2-form with top-level `return` — invalid ESM "
                            "(node --check --input-type=module fails with SyntaxError: "
                            "Illegal return statement). H-6 baseline: will XPASS once "
                            "ticket 09 fixes the E1 emission or migrates to valid ESM form."
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
_ALL_E1_PARAMS = _make_e1_params(_ALL_SCRIPTS)

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


@pytest.mark.xfail(
    strict=True,
    reason=(
        "H-5 baseline: build-epic.js uses spread-form parallel "
        "(parallel(...chunk.map(...))) instead of array-form parallel([...]). "
        "The hardened harness records a contract violation; the assertion "
        "that no violations exist therefore FAILS. "
        "This XPASS will fire when ticket 10 fixes build-epic.js to use array-form "
        "parallel — at which point remove this xfail marker."
    ),
)
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
# AC-4 / H-6: E1 ESM validity — real import-mode check for all scripts
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not shutil.which("node"),
    reason="node binary not available — E1 import check requires Node.js",
)
@pytest.mark.parametrize("script_path", _ALL_E1_PARAMS, ids=_script_id)
def test_e1_import_validity(script_path: Path) -> None:
    """Every workflow script must be valid ES module syntax.

    Uses ``node --check --input-type=module`` to parse the script in ES-module
    mode. This is stricter than ``node --check`` (script mode, which tolerates
    top-level ``return``): ES-module mode rejects top-level ``return`` with
    SyntaxError — matching what the E1 engine sees when it ``import()``s the script.

    Scripts in ``_E1_INVALID_SCRIPTS`` are currently E2-form and contain top-level
    ``return`` statements (valid under the E2 IIFE wrapping, but invalid ESM).
    They are marked ``xfail(strict=True)`` as the H-6 RED baseline. They will
    XPASS — becoming test errors — once ticket 09 fixes the E1 emission to produce
    valid ESM (wrapping the E2 body inside ``export async function run()``).

    ``create-ticket.js`` is already E1-form (no top-level ``return``) and is
    expected to pass this check unconditionally.

    AC-4: covers every *.js in templates/workflows-js/, not just quick-fix.js.
    H-6: uses real module-mode parse rather than permissive script-mode ``--check``.

    Args:
        script_path: Parametrized path to the workflow script under test.
    """
    result: E1CheckResult = run_e1_import_check(script_path)

    if not result.valid:
        # Surface the exact error so developers know which SyntaxError to fix.
        error_detail = result.error[:500] if result.error else "(no error detail)"
        assert result.valid, (
            f"{script_path.name} fails ES-module syntax check (H-6).\n\n"
            f"node --check --input-type=module reported:\n  {error_detail}\n\n"
            f"This usually indicates a top-level `return` statement, which is "
            f"illegal in ES modules. The E1 engine imports scripts as ESM and "
            f"will fail with the same error at runtime.\n\n"
            f"Fix: either (a) wrap the top-level body in an IIFE before the "
            f"export async function run(), or (b) ensure the E1 emission shim "
            f"in build_phases._emit_workflow_variant moves top-level `return` "
            f"inside the exported run() function (ticket 09)."
        )
