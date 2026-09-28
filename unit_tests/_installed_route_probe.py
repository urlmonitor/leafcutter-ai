"""
MODULE: _installed_route_probe
GOAL: Run the REAL installed copy of ``plan-feature.js`` (deployed by the
    real ``scripts/build.py``) and the REAL source copy under
    ``templates/workflows-js/`` through ``_workflow_engine_harness``, and
    report each run's own recorded stopping point -- never a comparison of
    the two files' contents.
BUSINESS CONTEXT: ACD-2100d-1 requires evidence that a consumer's INSTALLED
    project reaches the same first user-facing question as this repository's
    own source checkout does, and that the finding comes from RUNNING both
    copies rather than diffing them. This module is that record's own
    principal deliverable (its doc_links entry names it "creates ... DOES
    NOT EXIST YET"), assigned to python-coder, and is reused as-is by
    ACD-2100d-3 to compare two of its own results against each other -- so
    ``STOPPING_POINT_FIRST_QUESTION``'s shape must stay stable across
    callers.
ARCHITECTURE: ``install_route_into_temp_target()`` shells out to the real
    ``scripts/build.py --target-dir <target>`` (never a hand-authored
    fixture tree) so the installed copy under test is exactly what a real
    consumer's own install produces. ``probe_installed_route()`` /
    ``probe_source_route()`` each drive ``plan-feature.js`` through
    ``_workflow_engine_harness.run_workflow_under_e2()`` with a deterministic
    ``stage-0-triage`` label response (``{"route": "covered", ...}``) so both
    runs are forced down the SAME branch (the "covered" route's user-facing
    confirmation gate) rather than depending on what a live triage agent
    would answer -- mirroring how test-writer's own ad-hoc verification (see
    unit_tests/portability/test_acd_2100d_1.py's module docstring) grounded
    this contract before this module existed. Neither probe function ever
    reads or diffs the script files themselves; the finding is entirely the
    harness's own recorded terminal payload from an actual run.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2

# ---------------------------------------------------------------------------
# Stable stopping-point vocabulary
# ---------------------------------------------------------------------------

# The sentinel value ``.stopping_point`` takes when a run reaches the first
# question the route puts to the user. ACD-2100d-3 reuses this same probe and
# compares two of its own results against each other, so this value must not
# change shape between callers.
STOPPING_POINT_FIRST_QUESTION = "first_question:covered-route-gate"

# The gate id ``templates/workflows-js/plan-feature.js`` assigns to the
# "covered" route's first user-facing confirmation question (see that
# script's own ``pauseAtGate("covered-route-gate", ...)`` call). Reaching a
# terminal payload carrying this ``gate_id`` -- regardless of whether the
# pause record's own persistence-verification step separately succeeds or
# fails, which is a fact about the harness's stub agent responses, not about
# which copy of the route is running -- is what this module treats as
# "reached the first question".
_COVERED_ROUTE_GATE_ID = "covered-route-gate"

_PLAN_FEATURE_SOURCE_RELATIVE_PATH = Path("templates") / "workflows-js" / "plan-feature.js"
_PLAN_FEATURE_INSTALLED_RELATIVE_PATH = Path(".leafcutter") / "workflows" / "plan-feature.js"
_BUILD_SCRIPT_RELATIVE_PATH = Path("scripts") / "build.py"

_DEFAULT_INSTALL_TIMEOUT_SECONDS = 120
_DEFAULT_PROBE_TIMEOUT_SECONDS = 60

# Forces both runs down the "covered" route's user-facing confirmation gate
# (see module docstring) instead of depending on a live triage agent's
# answer. This is the ONLY label override either probe supplies; every other
# agent() dispatch on the path to that gate uses the harness's own default
# stub, identically for both copies.
_STAGE_0_TRIAGE_LABEL_RESPONSES: dict[str, Any] = {
    "stage-0-triage": {
        "route": "covered",
        "existing_acs": ["ACD-2100d-1-PROBE"],
        "parent_l1_id": None,
        "rationale": "route probe: forced deterministic to the covered-route-gate for parity comparison.",
    },
}


@dataclass
class RouteProbeResult:
    """The outcome of probing one copy of the route.

    Attributes:
        stopping_point: A value from the stable vocabulary above --
            ``STOPPING_POINT_FIRST_QUESTION`` when the run reached the first
            question, or a distinct, run-specific ``"halted:<status>"``
            string naming the startup check that halted it otherwise. This
            is the field every assertion must read; ``harness_result`` is for
            introspection only (see module docstring on why its own
            ``returncode`` cannot distinguish a halt from success).
        harness_result: The underlying
            ``_workflow_engine_harness.HarnessResult`` for the run.
    """

    stopping_point: str
    harness_result: HarnessResult


def _stopping_point_from_result(result: Any) -> str:
    """Classify a workflow run's own top-level terminal payload into the
    stable stopping-point vocabulary.

    Pure function: no I/O, no external calls (repository error-handling
    policy Rule 4 -- no try/except belongs here).
    """
    if isinstance(result, dict) and result.get("gate_id") == _COVERED_ROUTE_GATE_ID:
        return STOPPING_POINT_FIRST_QUESTION
    if isinstance(result, dict):
        status = result.get("status", "unknown")
        return f"halted:{status}"
    return "halted:no_terminal_payload"


def install_route_into_temp_target(package_root: Path, target_dir: Path) -> subprocess.CompletedProcess:
    """Run the REAL installer (``scripts/build.py --target-dir target_dir``)
    from ``package_root`` as a real subprocess.

    Never installs into a developer's own project -- ``target_dir`` is
    expected to be a temporary directory the caller owns and removes, so the
    check is repeatable and leaves nothing behind (ACD-2100d-1 implementation
    notes).

    Args:
        package_root: Absolute path to this package's own source checkout
            (the directory containing ``scripts/build.py``).
        target_dir: Absolute path to the (already git-initialized) temporary
            target project to install into.

    Returns:
        The installer subprocess's own ``subprocess.CompletedProcess``
        (``returncode``, ``stdout``, ``stderr``) -- never raises on a
        non-zero exit; the caller asserts on ``returncode`` itself.

    Raises:
        OSError: If the ``python`` subprocess itself cannot be started.
        subprocess.SubprocessError: If the installer subprocess times out or
            otherwise fails at the process-management level.
    """
    build_script = package_root / _BUILD_SCRIPT_RELATIVE_PATH
    try:
        return subprocess.run(
            [sys.executable, str(build_script), "--target-dir", str(target_dir)],
            capture_output=True,
            text=True,
            check=False,
            timeout=_DEFAULT_INSTALL_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise type(exc)(
            f"install_route_into_temp_target: failed to run {build_script} "
            f"--target-dir {target_dir}: {exc}"
        ) from exc


def probe_installed_route(target_dir: Path, *, timeout: int = _DEFAULT_PROBE_TIMEOUT_SECONDS) -> RouteProbeResult:
    """Start a run, in a fresh process, against the copy of
    ``plan-feature.js`` the installer deployed under
    ``target_dir/.leafcutter/workflows/plan-feature.js`` -- the entry point a
    consumer's own installed project actually uses.

    Never installs; call ``install_route_into_temp_target()`` first.

    Args:
        target_dir: Absolute path to a project the installer has already
            deployed into.
        timeout: Seconds to wait for the underlying Node.js subprocess.

    Returns:
        A ``RouteProbeResult`` describing how far this run got.

    Raises:
        FileNotFoundError: If the installer did not deploy
            ``plan-feature.js`` into ``target_dir`` at all.
    """
    script_path = target_dir / _PLAN_FEATURE_INSTALLED_RELATIVE_PATH
    harness_result = run_workflow_under_e2(
        script_path,
        timeout=timeout,
        label_responses=_STAGE_0_TRIAGE_LABEL_RESPONSES,
    )
    return RouteProbeResult(
        stopping_point=_stopping_point_from_result(harness_result.result),
        harness_result=harness_result,
    )


def probe_source_route(package_root: Path, *, timeout: int = _DEFAULT_PROBE_TIMEOUT_SECONDS) -> RouteProbeResult:
    """The same measurement as ``probe_installed_route()``, but against
    ``package_root/templates/workflows-js/plan-feature.js`` -- the copy the
    source checkout runs.

    Args:
        package_root: Absolute path to this package's own source checkout.
        timeout: Seconds to wait for the underlying Node.js subprocess.

    Returns:
        A ``RouteProbeResult`` describing how far this run got.

    Raises:
        FileNotFoundError: If ``package_root`` has no
            ``templates/workflows-js/plan-feature.js``.
    """
    script_path = package_root / _PLAN_FEATURE_SOURCE_RELATIVE_PATH
    harness_result = run_workflow_under_e2(
        script_path,
        timeout=timeout,
        label_responses=_STAGE_0_TRIAGE_LABEL_RESPONSES,
    )
    return RouteProbeResult(
        stopping_point=_stopping_point_from_result(harness_result.result),
        harness_result=harness_result,
    )


# DECISION HISTORY
# ================================================================================
# - 2026-09-08 15:30 [python-coder]: Created this module -- ACD-2100d-1's own
#   principal deliverable. Chose "reached a terminal payload whose gate_id is
#   covered-route-gate" as STOPPING_POINT_FIRST_QUESTION's condition (rather
#   than requiring status=="paused_awaiting_input" specifically) because
#   direct execution against both the source and a real installed copy (after
#   the accompanying _workflow_engine_harness.py fix) showed both copies
#   reaching status="pause_persist_failed" at that SAME gate_id -- a fact
#   about the harness's default agent() stub not returning a persistable
#   {"exists": true} record, identically for both copies, not a difference
#   between the two copies under test. Requiring the narrower status would
#   have made this probe fail identically (and uninformatively) for every
#   caller unless it also stubbed "pause-persist-verify", which is a harness
#   plumbing detail unrelated to what this AC measures.
#   (#EPIC-StartingNewWorkTheProperWayAlways/19)
