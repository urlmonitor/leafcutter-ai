"""
MODULE: _route_start_regression_check
GOAL: ACD-2100d-3's own before/after route-start regression check -- a
    relation between two recorded observations of the SAME project (one
    taken before the installer runs, one after), never an after-state-only
    check and never a comparison of the files the installer copied.
BUSINESS CONTEXT: The consumer-install-simulation CI job
    (scripts/ci/check_consumer_install.py, .github/workflows/ci.yml:552-557)
    already runs a real install against a real target project. This module
    is that already-gated entry point's extension: it probes the target's
    currently-deployed ``plan-feature.js`` (if any) before the installer
    runs, probes the SAME target again afterward, and classifies the pair
    into a verdict distinguishing precondition-not-met (the Given did not
    hold), a route-start regression (the install introduced a startup check
    the project did not halt at before), and a pass (both readings reach the
    first question). Kept as a sibling module -- not inlined into
    check_consumer_install.py -- to stay within that file's own line-size
    budget (see check_file_size.py), the same pattern already used for
    _use_install_step.py.
ARCHITECTURE: Reuses ACD-2100d-1's shared ``unit_tests/_installed_route_probe.py``
    harness as-is (this ticket's own Implementation Notes forbid a second
    probe or a second harness): ``probe_route_before_install()`` imports it
    by inserting ``<package_dir>/unit_tests`` onto ``sys.path`` (the test
    tree, never deployed to a consumer -- package-development tooling only)
    and probes ``target_dir``'s pre-existing deployed route, returning the
    already-imported module so ``verdict_after_install()`` can reuse it for
    the second (after) probe without re-resolving ``sys.path``. The literal
    relative path this module checks for existence
    (``INSTALLED_PLAN_FEATURE_RELATIVE_PATH``) matches the shared probe's
    own hardcoded assumption of a fixed ``.leafcutter`` layout, not
    check_consumer_install.py's configurable ``_resolve_output_root()`` --
    this check must agree with what the probe itself will actually read.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

INSTALLED_PLAN_FEATURE_RELATIVE_PATH = Path(".leafcutter") / "workflows" / "plan-feature.js"
ROUTE_START_PROBE_TIMEOUT_SECONDS = 60

EXIT_PRECONDITION_NOT_MET = 3
MARKER_PRECONDITION_NOT_MET = "PRECONDITION NOT MET"
MARKER_ROUTE_START_REGRESSION = "route-start regression"


def _import_installed_route_probe(package_dir: Path) -> ModuleType:
    """Import the shared installed-route probe (ACD-2100d-1's own principal
    deliverable, ``unit_tests/_installed_route_probe.py``), reused as-is.

    Neither the CI check directory nor the test tree is deployed into a
    target install -- both are package-development tooling read only from
    this package's own source checkout, never from a consumer's deployed
    tree.

    Args:
        package_dir: Absolute path to this package's own source checkout
            (the directory containing ``unit_tests/``).

    Returns:
        The imported ``unit_tests._installed_route_probe`` module.

    Raises:
        ImportError: if the shared probe module cannot be imported (e.g.
            ``package_dir`` does not carry a ``unit_tests/`` directory).
    """
    unit_tests_dir = str(package_dir / "unit_tests")
    if unit_tests_dir not in sys.path:
        sys.path.insert(0, unit_tests_dir)
    import _installed_route_probe as probe_module

    return probe_module


def probe_route_before_install(
    package_dir: Path, target_dir: Path
) -> tuple[str | None, ModuleType | None]:
    """Probe ``target_dir``'s currently-deployed ``plan-feature.js`` (if
    any) for its stopping point, BEFORE the installer runs.

    Args:
        package_dir: Absolute path to this package's own source checkout.
        target_dir: Absolute path to the scratch consumer-install project
            being checked.

    Returns:
        A ``(stopping_point, probe_module)`` pair. Both are ``None`` when
        nothing is deployed at ``target_dir`` yet -- a genuinely fresh
        scratch install, for which ACD-2100d-3's Given precondition does
        not apply and the whole before/after check must be skipped rather
        than failed (the existing empty-scratch-directory CI usage stays
        green). ``probe_module`` is the already-imported shared probe,
        returned so ``verdict_after_install()`` can reuse it without
        re-resolving ``sys.path``.

    Raises:
        ImportError: if the shared probe module cannot be imported.
    """
    deployed_script = target_dir / INSTALLED_PLAN_FEATURE_RELATIVE_PATH
    if not deployed_script.is_file():
        return None, None
    probe_module = _import_installed_route_probe(package_dir)
    result = probe_module.probe_installed_route(target_dir, timeout=ROUTE_START_PROBE_TIMEOUT_SECONDS)
    return result.stopping_point, probe_module


def _classify(before: str, after: str, first_question: str) -> tuple[str, int]:
    """Classify a before/after route-start reading pair into a verdict
    message and exit code -- ACD-2100d-3's own observable contract.

    Pure function: no I/O, no external calls (repository error-handling
    policy Rule 4 -- no try/except belongs here).

    Args:
        before: The stopping-point reading taken before the install.
        after: The stopping-point reading taken after the install.
        first_question: The stable "reached the first question" sentinel
            (``probe_module.STOPPING_POINT_FIRST_QUESTION``) both readings
            are compared against.

    Returns:
        A ``(message, exit_code)`` pair: ``EXIT_PRECONDITION_NOT_MET`` (3)
        when ``before`` never reached the first question (the Given
        precondition was not met -- never reported as a pass, regardless of
        ``after``); 1 when ``before`` did but ``after`` no longer does (a
        route-start regression the install introduced); 0 when both
        readings reach the first question.
    """
    if before != first_question:
        return (
            f"CONSUMER INSTALL SIMULATION {MARKER_PRECONDITION_NOT_MET}: the "
            f"project did not reach the first question BEFORE the installer "
            f"ran (before={before!r}) -- ACD-2100d-3's Given precondition was "
            f"not met, so no before/after comparison can be made.",
            EXIT_PRECONDITION_NOT_MET,
        )
    if after != first_question:
        return (
            f"CONSUMER INSTALL SIMULATION FAILED: {MARKER_ROUTE_START_REGRESSION} "
            f"-- the project reached the first question before the install "
            f"(before={before!r}) but a startup check now stops it "
            f"(after={after!r}).",
            1,
        )
    return (
        f"CONSUMER INSTALL SIMULATION OK: route start unaffected by the "
        f"install (before={before!r}, after={after!r}).",
        0,
    )


def verdict_after_install(
    before_stopping_point: str, probe_module: ModuleType, target_dir: Path
) -> tuple[str, int]:
    """Probe ``target_dir`` again AFTER the installer has run and the
    deployed tree has been verified, and classify the before/after pair.

    Only called when ``probe_route_before_install()`` returned a non-``None``
    ``before_stopping_point`` -- the caller is responsible for skipping this
    entirely when nothing was deployed before the install.

    Args:
        before_stopping_point: The reading ``probe_route_before_install()``
            returned.
        probe_module: The already-imported shared probe module
            ``probe_route_before_install()`` returned, reused here so the
            after-reading never re-resolves ``sys.path``.
        target_dir: The same project probed before the install.

    Returns:
        A ``(message, exit_code)`` pair -- see ``_classify()``.

    Raises:
        FileNotFoundError: if the installer did not leave a
            ``plan-feature.js`` deployed at ``target_dir`` at all.
        ValueError: if the deployed path is not a ``.js`` file.
    """
    after_result = probe_module.probe_installed_route(
        target_dir, timeout=ROUTE_START_PROBE_TIMEOUT_SECONDS
    )
    return _classify(
        before_stopping_point,
        after_result.stopping_point,
        probe_module.STOPPING_POINT_FIRST_QUESTION,
    )


# DECISION HISTORY
# ================================================================================
# - 2026-09-08 [python-coder/EPIC-StartingNewWorkTheProperWayAlways/22]: Split
#   out of scripts/ci/check_consumer_install.py to stay within that file's
#   own line-size budget (check_file_size.py), mirroring the existing
#   _use_install_step.py sibling-module split. Reuses ACD-2100d-1's shared
#   unit_tests/_installed_route_probe.py harness as-is -- never a second
#   probe -- per this ticket's own "wire into the gate that already runs,
#   reuse the existing probe" Implementation Notes.
#   (#EPIC-StartingNewWorkTheProperWayAlways/22)
# ================================================================================
