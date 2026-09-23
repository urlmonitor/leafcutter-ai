"""
MODULE: test_acd_2100d_1
GOAL: RED-baseline behavioral tests for ACD-2100d-1 -- "The installed copy of
    the route reaches the first user question exactly as the source copy
    does."

WHAT THIS RECORD REQUIRES (verbatim from its own criteria): install the route
    into a temporary target project via the REAL installer, start a run there
    against the INSTALLED copy and a second run in the source checkout
    against the SOURCE copy, under the same starting directory conditions,
    and confirm both reach the same point -- the first question the route
    puts to the user -- with neither halting at an earlier startup check.
    The finding must come from RUNNING both copies, never from diffing them.

THE MODULE UNDER TEST DOES NOT EXIST YET.
    ``unit_tests/_installed_route_probe.py`` is this AC's own principal
    deliverable (its doc_links entry is explicitly "creates ... DOES NOT
    EXIST YET"), assigned to python-coder. Every test below imports it, so
    every test in this file is expected to fail at COLLECTION with
    ``ModuleNotFoundError`` until that module is authored -- the correct RED
    state for a test-writer phase that runs before any coder phase.

    The contract this file expects that module to provide (test-writer's own
    specification, per this repo's TDD convention that test-writer defines
    the shape coders must satisfy):

        install_route_into_temp_target(package_root, target_dir)
            Runs the REAL ``scripts/build.py --target-dir target_dir`` from
            *package_root* as a real subprocess. Returns the
            ``subprocess.CompletedProcess``.

        probe_installed_route(target_dir, *, timeout=...) -> RouteProbeResult
            Starts a run, in a fresh process, against the copy of
            ``plan-feature.js`` the installer deployed under
            ``target_dir/.leafcutter/workflows/plan-feature.js`` -- the
            entry point a consumer's own installed project actually uses --
            and reports that run's own recorded stopping point. Never
            installs; call ``install_route_into_temp_target`` first.

        probe_source_route(package_root, *, timeout=...) -> RouteProbeResult
            The same, but against ``package_root/templates/workflows-js/
            plan-feature.js`` -- the copy the source checkout runs.

        RouteProbeResult
            A dataclass exposing at least ``.stopping_point`` (a string from
            a stable vocabulary: ``STOPPING_POINT_FIRST_QUESTION`` when the
            run reached the first question the route puts to the user, or
            some other, run-specific value naming the startup check that
            halted it) and ``.harness_result`` (the underlying
            ``_workflow_engine_harness.HarnessResult``, for introspection --
            never for the actual assertion, which must be made against
            ``.stopping_point``, not against ``.harness_result.returncode``;
            see the "verified" note below for why the two can disagree).

        STOPPING_POINT_FIRST_QUESTION
            The stable sentinel ``.stopping_point`` takes when a run reaches
            the first question. ACD-2100d-3 reuses this same probe and
            compares two of its results against each other, so this value
            must not change shape between callers.

WHY THE PROBE MUST GIT-INIT ITS OWN TEMPORARY TARGET (verified empirically,
    this session, against this worktree's current HEAD, 2026-09-08, via
    ad-hoc ``run_workflow_under_e2`` calls against both a bare ``mkdir``
    target and a real ``git init`` target): the Pre-Stage-0 workspace-setup
    permission gate's real pre-flight script
    (``scripts/worktree/check_workspace_setup_permission.py``) resolves "the
    repository" via git ancestry from its own working directory. Against a
    bare, non-git temporary directory it reports "No repository could be
    resolved from the current directory" and the run halts with
    ``result.status == "error"`` BEFORE the first question is ever asked --
    for BOTH the installed and the source copy, since neither is the actual
    defect this AC is about. Against a real ``git init``-ed temporary target
    (mirroring ``unit_tests/workflows/test_acd_2100a_5.py``'s own
    ``_init_git_project`` fixture, and how a real consumer's own project
    already is), both copies advance identically through the same eight
    stub-harness dispatches (``detect-current-branch``,
    ``resolve-worktree-setup-script-path``, ``worktree-setup``,
    ``scan-orphans-git-status``, ``scan-committed-stages``,
    ``stage-0-triage``, ``pause-persist``, ``pause-persist-verify``) to the
    SAME terminal ``gate_id`` -- confirming this test's fixture shape is
    correct and that any future asymmetry it catches is a real regression,
    not a fixture artifact. This file's own ``_make_git_project`` helper is a
    deliberately minimal, self-contained copy of that same construction (a
    real git repository is the only precondition this AC's Given needs; it
    does not need test_acd_2100a_5.py's worktree-setup-stub or
    pause_store.py-copying machinery, because this AC's subject is
    installed-vs-source parity, not cwd-relative path resolution).

    RETURNCODE ALONE CANNOT DISTINGUISH A HALT FROM SUCCESS (also verified
    empirically): the Node subprocess wrapping either copy exits 0 whether
    the script's OWN terminal payload is a halt (``status: "error"``) or a
    reached gate (``gate_id: "covered-route-gate"``) -- the wrapper's outer
    ``.then()``/``.catch()`` always resolves cleanly because the workflow
    body itself never throws on this path, it only returns a different
    shaped object. This is exactly why every assertion below reads
    ``RouteProbeResult.stopping_point`` and never
    ``RouteProbeResult.harness_result.returncode`` -- per this AC's own
    second Then clause ("the finding rests on what the two runs did") and
    per its second test_spec descriptor's own language ("against each run's
    own recorded outcome rather than against its exit code alone").

    THE FIRST QUESTION IS FORCED DETERMINISTIC the same way
    test_acd_2100a_5.py forces it: both probe calls are expected to supply a
    ``stage-0-triage`` label response of ``{"route": "covered", ...}`` so
    both runs are driven to the SAME named gate
    (``covered-route-gate``) rather than depending on what a live triage
    agent would answer -- this file does not touch that machinery directly
    (it is the probe module's job to pass it through), it only relies on the
    probe's own stable ``STOPPING_POINT_FIRST_QUESTION`` vocabulary for the
    outcome.

NOT COMPARING FILES: no test in this module ever calls ``.read_text()`` or
    ``.read_bytes()`` on either copy of ``plan-feature.js``, or on any file
    the installer produced, and no test diffs the installed tree against the
    source tree. Every finding here comes from STARTING a run against each
    copy in a fresh process and reading back that run's own recorded
    outcome -- per this AC's own explicit prohibition on file-diff evidence,
    and per its third test_spec descriptor's own language ("a deployed
    artifact that is byte-identical and still cannot run fails this test").

TICKET: 19_TICKET-20260826-ACD-2100d-1.md
AC: ACD-2100d-1
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

# unit_tests/ must be on sys.path so the root-level shared probe module is
# importable from this sub-package (unit_tests/portability/), mirroring every
# other test file in this repository that imports a root-level shared
# harness (e.g. unit_tests/workflows/test_acd_2100a_5.py's own
# _workflow_engine_harness import; see that file for the identical pattern).
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

# EXPECTED RED: _installed_route_probe.py does not exist yet -- it is this
# AC's own principal deliverable (assigned to python-coder). This import
# fails at collection with ModuleNotFoundError until that module is
# authored; see the module docstring's "THE MODULE UNDER TEST DOES NOT EXIST
# YET" section for the exact contract it must provide.
from _installed_route_probe import (  # noqa: E402
    STOPPING_POINT_FIRST_QUESTION,
    install_route_into_temp_target,
    probe_installed_route,
    probe_source_route,
)

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_TIMEOUT = 60  # seconds; a real `scripts/build.py` run plus two Node harness runs.


# ---------------------------------------------------------------------------
# Fixture builder
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, check=True, capture_output=True, text=True
    )


def _make_git_project(tmp_path: Path) -> Path:
    """A real git repository, seeded with one commit -- the same starting
    directory condition a real consumer's own project already has before
    they ever run the installer, and the precondition the Pre-Stage-0
    workspace-setup permission gate's real pre-flight script needs to
    resolve "the repository" (see module docstring's "WHY THE PROBE MUST
    GIT-INIT" section for the verified failure mode without this).

    Mirrors unit_tests/workflows/test_acd_2100a_5.py's own
    ``_init_git_project`` -- deliberately not imported from that file (per
    this repository's convention of small, self-contained per-file
    fixtures rather than cross-file private-helper coupling).
    """
    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True)
    _run(["git", "init", "-q", "-b", "main", str(project_dir)])
    _run(["git", "-C", str(project_dir), "config", "user.email", "test@example.com"])
    _run(["git", "-C", str(project_dir), "config", "user.name", "Test"])
    (project_dir / "README.md").write_text("seed\n", encoding="utf-8")
    _run(["git", "-C", str(project_dir), "add", "README.md"])
    _run(["git", "-C", str(project_dir), "commit", "-q", "-m", "seed"])
    return project_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_installed_and_source_copies_both_reach_the_first_user_question():
    # covers: ACD-2100d-1
    # angle: deployed
    """AC-1: both runs reach the same point -- the first question the route
    puts to the user. The installer is run into a temporary target project;
    a run started there against the installed copy and a run started in the
    source checkout against the source copy, under identical starting
    directory conditions (a real, freshly seeded git project either way),
    both reach the first question.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100d1_deployed_") as tmp:
        target_dir = _make_git_project(Path(tmp))

        install_proc = install_route_into_temp_target(_WORKTREE_ROOT, target_dir)
        assert install_proc.returncode == 0, (
            f"installer failed to deploy into {target_dir}: "
            f"stdout={install_proc.stdout!r} stderr={install_proc.stderr!r}"
        )

        installed_result = probe_installed_route(target_dir, timeout=_TIMEOUT)
        source_result = probe_source_route(_WORKTREE_ROOT, timeout=_TIMEOUT)

        assert installed_result.stopping_point == STOPPING_POINT_FIRST_QUESTION, (
            f"installed copy did not reach the first question -- "
            f"stopping_point={installed_result.stopping_point!r}, "
            f"result={installed_result.harness_result.result!r}"
        )
        assert source_result.stopping_point == STOPPING_POINT_FIRST_QUESTION, (
            f"source copy did not reach the first question -- "
            f"stopping_point={source_result.stopping_point!r}, "
            f"result={source_result.harness_result.result!r}"
        )
        # THE PARITY CLAIM ITSELF: not merely that each reaches ITS OWN first
        # question, but that both reach the SAME point.
        assert installed_result.stopping_point == source_result.stopping_point, (
            f"installed and source copies reached DIFFERENT stopping points: "
            f"installed={installed_result.stopping_point!r} "
            f"source={source_result.stopping_point!r} -- this is the exact "
            f"divergence this AC exists to catch (the deployed workflow "
            f"observably behaving as a different program from the source one)."
        )


def test_neither_copy_halts_at_a_check_before_the_first_question():
    # covers: ACD-2100d-1
    # angle: failure
    """AC-2: neither run stops at a check performed before the first
    question. The assertion is made against each run's OWN RECORDED
    stopping point, never against the harness subprocess's exit code alone
    -- verified (see module docstring) that a Node wrapper around a HALTED
    script still exits 0, so returncode alone cannot distinguish a halt from
    success.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100d1_failure_") as tmp:
        target_dir = _make_git_project(Path(tmp))

        install_proc = install_route_into_temp_target(_WORKTREE_ROOT, target_dir)
        assert install_proc.returncode == 0, (
            f"installer failed to deploy into {target_dir}: "
            f"stdout={install_proc.stdout!r} stderr={install_proc.stderr!r}"
        )

        installed_result = probe_installed_route(target_dir, timeout=_TIMEOUT)
        source_result = probe_source_route(_WORKTREE_ROOT, timeout=_TIMEOUT)

        for copy_name, result in (
            ("installed", installed_result),
            ("source", source_result),
        ):
            # Demonstrate the exit-code trap directly: the Node subprocess
            # exits 0 regardless of whether the SCRIPT itself halted. If this
            # assertion ever fails, the harness itself crashed (a different,
            # infrastructural problem) rather than the workflow halting at a
            # startup check -- which is exactly why it is not, on its own,
            # evidence of reaching the first question.
            assert result.harness_result.returncode == 0, (
                f"{copy_name} copy's harness subprocess itself crashed "
                f"(returncode={result.harness_result.returncode}); "
                f"stderr={result.harness_result.stderr!r}"
            )
            # The REAL evidence: the run's own recorded stopping point. Any
            # value other than STOPPING_POINT_FIRST_QUESTION means the run
            # halted at some earlier, named startup check -- exactly the
            # outcome this Then clause forbids for either copy.
            assert result.stopping_point == STOPPING_POINT_FIRST_QUESTION, (
                f"{copy_name} copy halted at a startup check before the "
                f"first question -- its own recorded stopping point was "
                f"{result.stopping_point!r} (a returncode-only check would "
                f"have missed this: returncode="
                f"{result.harness_result.returncode}). "
                f"result={result.harness_result.result!r}"
            )


def test_parity_finding_is_produced_by_running_both_copies_not_by_diffing_them():
    # covers: ACD-2100d-1
    # angle: reachability
    # reachability_entry_point_answer.entry_point (verbatim from this AC's
    # own test_spec.surface_invoked -- see ACD-2100d-1.yaml): "the installed
    # route invoked in the temporary target project the way a consumer
    # invokes it, in a fresh process"
    """AC-3: the finding rests on what the two runs did rather than on any
    comparison of the two files. The deployed copy is invoked through the
    entry point a consumer actually uses (the installer-deployed
    ``.leafcutter/workflows/plan-feature.js``), in a fresh process, and the
    run's terminal payload -- produced by a real conditional branch inside
    the running script, not a canned literal -- is read back and consumed
    here. A deployed artifact that is byte-identical to the source and still
    cannot run would leave ``deployed_script.is_file()`` True while failing
    every assertion below; this test never reads or diffs either file's
    content, only what running the installed copy actually produced.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100d1_reach_") as tmp:
        target_dir = _make_git_project(Path(tmp))

        install_proc = install_route_into_temp_target(_WORKTREE_ROOT, target_dir)
        assert install_proc.returncode == 0, (
            f"installer failed to deploy into {target_dir}: "
            f"stdout={install_proc.stdout!r} stderr={install_proc.stderr!r}"
        )

        deployed_script = target_dir / ".leafcutter" / "workflows" / "plan-feature.js"
        assert deployed_script.is_file(), (
            f"installer did not deploy plan-feature.js into {target_dir} at all -- "
            "nothing to invoke, so this test cannot even attempt reachability."
        )

        installed_result = probe_installed_route(target_dir, timeout=_TIMEOUT)

        # REACHABILITY, NOT TOPOLOGY: the run must have produced a terminal
        # payload at all -- a script that never returns (hangs, throws before
        # any return, or is never actually invoked by the probe) leaves this
        # None, which would be indistinguishable from "the file exists but is
        # dead weight". Consuming this value in the next assertion is the
        # control-flow consumption this angle requires, not merely a symbol
        # or path-argument check.
        assert installed_result.harness_result.result is not None, (
            "installed copy produced no terminal payload at all -- the "
            "process ran but the script itself never reached a point where "
            "it returned a result, so nothing here was actually consumed."
        )
        assert installed_result.stopping_point == STOPPING_POINT_FIRST_QUESTION, (
            f"deployed artifact did not advance past its startup checks: "
            f"stopping_point={installed_result.stopping_point!r} "
            f"result={installed_result.harness_result.result!r} -- a "
            f"byte-identical-but-unrunnable deploy would fail exactly here."
        )
        assert len(installed_result.harness_result.agent_calls) > 0, (
            "installed copy dispatched zero agent() calls -- a run that "
            "never advances past its own top-level startup body cannot be "
            "said to have reached anything, regardless of what the "
            "installed file on disk contains."
        )
