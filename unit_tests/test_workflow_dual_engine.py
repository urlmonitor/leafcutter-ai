"""
MODULE: test_workflow_dual_engine
GOAL: Zero-dispatch CI guard — asserts that every *.js in templates/workflows-js/
    dispatches at least one agent under a stub E2 engine.
BUSINESS CONTEXT: The live E2 workflow engine executes each script's top-level
    body with injected globals (agent, parallel, phase, log, args). Scripts that
    only define a `run()` function and never call agent() at the top level are
    silently inert under E2. This suite makes that failure CI-visible by running
    every workflow script through the recording-mock harness and asserting
    dispatch_count >= 1. The five E1-only scripts are marked xfail(strict=True)
    so they are expected-red now and will flip to errors once tickets 05/06 port
    them to the E2 contract.
ARCHITECTURE: Pure Python test — uses the _workflow_engine_harness module to
    run each script via a Node.js subprocess with no claude binary required.
    CI-safe: only Node.js (standard CI dependency) is needed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2

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
