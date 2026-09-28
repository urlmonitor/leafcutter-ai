"""
MODULE: test_acd_2100d_3
GOAL: RED-baseline behavioral tests for ACD-2100d-3 -- "Installing into a
    project where the route starts leaves the route still able to start."

WHAT THIS RECORD REQUIRES (verbatim from its own criteria): given a project
    in which a run reaches the first question the route puts to the user
    BEFORE the installer is run, running the current installer against that
    project must leave a run started there AFTERWARDS still reaching that
    same first question, and it must not stop at any check that did not stop
    it before. The verdict is a RELATION between two recorded observations of
    the SAME project (one before the installer runs, one after) -- never an
    after-state-only check, and never a comparison of the files the
    installer copied.

THE ENTRY POINT UNDER TEST -- ``scripts/ci/check_consumer_install.py`` --
    ALREADY EXISTS (it is the wired consumer-install-simulation job's own
    entry point, ``.github/workflows/ci.yml:552-557``) but does NOT YET
    perform the before/after route-start measurement this record requires.
    Per this ticket's own Implementation Notes ("THE GATE THAT ACTUALLY RUNS
    ON AN INSTALLER CHANGE ALREADY EXISTS -- WIRE INTO IT RATHER THAN ADDING
    A SECOND ONE"), every test below drives THIS SAME CLI script as a real
    subprocess (never a second, standalone script) and reads its stdout/
    stderr and exit code -- the observable contract python-coder must extend
    it to satisfy (test-writer's own specification, per this repo's TDD
    convention):

        A new, distinct exit code for "the Given precondition was not met" --
        so it can never be confused with 0 (pass), 1 (a plain failure, e.g.
        build.py itself failed or a reference did not resolve), or 2
        (usage/environment error):

            _EXIT_PRECONDITION_NOT_MET = 3

        Before ``_maybe_run_build()`` runs, the script must check whether
        ``target_dir/.leafcutter/workflows/plan-feature.js`` ALREADY exists
        (a route deployed by some PRIOR install, real or seeded) and, if so,
        probe it via the SAME shared harness ACD-2100d-1 built
        (``unit_tests/_installed_route_probe.probe_installed_route()``,
        reached by inserting ``<package_dir>/unit_tests`` onto ``sys.path`` --
        this repo's own test tree, never deployed to a consumer, which this
        ticket's own Implementation Notes confirm is correct: "Neither the CI
        check directory nor the test tree is deployed into a target install,
        and that is correct: both are package-development tooling"). If
        NOTHING is deployed there yet (a genuinely fresh scratch install --
        this AC's Given does not apply and the existing empty-scratch-
        directory CI usage must stay green), the before-measurement is simply
        ``None`` and this whole check is skipped -- not a failure.

        After the installer has run and the deployed tree has been verified,
        if (and only if) a before-reading was taken, probe the SAME
        ``target_dir`` again via ``probe_installed_route()`` for the
        after-reading, then print a verdict to stdout (exit 0) or stderr
        (non-zero exit) that MUST contain, verbatim:

          - when before did not reach the first question:
            the literal substring ``"PRECONDITION NOT MET"``, and exit
            ``_EXIT_PRECONDITION_NOT_MET`` (3) -- this must never be reported
            as a pass (exit 0), regardless of what the after-reading shows.
          - when before reached the first question but after does not:
            the literal substring ``"route-start regression"``, and exit 1.
          - otherwise (both reach the first question):
            exit 0, and the literal substrings
            ``f"before={STOPPING_POINT_FIRST_QUESTION!r}"`` and
            ``f"after={STOPPING_POINT_FIRST_QUESTION!r}"`` -- so the PAIR of
            recorded observations is visible in the verdict, not only the
            after-reading.

    Every literal marker string and exit code above is a hard requirement of
    the tests below, not a suggestion -- they are this record's own
    observable contract, chosen so the tests can verify it through the real
    CLI entry point (subprocess) rather than by importing an internal helper
    directly.

WHY A NON-GIT ``target_dir`` PRODUCES A REAL, REPRODUCIBLE REGRESSION
    (verified empirically this session, 2026-09-08, by running the real
    ``probe_installed_route()`` and the real ``check_workspace_setup_
    permission.py`` against a genuinely non-git temporary directory): the
    REAL current ``plan-feature.js`` source's Pre-Stage-0 workspace-setup
    permission gate is populated by ``_workflow_engine_harness.
    _default_args_for_script()``, which runs the real ``scripts/worktree/
    check_workspace_setup_permission.py`` pre-flight against the deployed
    tree. That pre-flight resolves "the repository" via git ancestry
    (``resolve_repo_root()``); against a target with no ``.git`` anywhere in
    its ancestry OR sibling tree, it returns ``permits: false, outcome:
    "read_failure", reason: "No repository could be resolved from the
    current directory."`` -- and the real workflow halts on that verdict
    with ``result.status == "error"`` BEFORE the first question is ever
    reached (classified by the shared probe as ``"halted:error"``, never
    ``STOPPING_POINT_FIRST_QUESTION``). A minimal stub script that performs
    no such check at all (see ``_NO_CHECKS_STUB_JS`` below) reaches the first
    question regardless of git state. Seeding a non-git ``target_dir`` with
    that stub as the "before" state and then letting the REAL installer
    overwrite it with the REAL source therefore constructs a genuine,
    deterministic regression: the project's own copy did not carry the
    repository-resolution check, and the installed artifact does.

NOT COMPARING FILES: no test below asserts on file byte-equality between the
    deployed and source copies as ITS OWN evidence of pass/fail -- per this
    ticket's explicit prohibition on file-diff evidence. Where a deployed
    file's content is inspected at all (the reachability test), it is only
    to confirm the installer genuinely replaced a stub with the REAL,
    functioning script (so the subsequent CLI-exit-code assertion cannot be
    dismissed as "of course it failed, the file itself was never deployed
    properly") -- the finding this record requires still comes exclusively
    from the CLI's own exit code and verdict text, produced by STARTING two
    real runs.

TICKET: 22_TICKET-20260826-ACD-2100d-3.md
AC: ACD-2100d-3
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

# unit_tests/ must be on sys.path so the root-level shared probe module is
# importable from this sub-package (unit_tests/portability/) -- same pattern
# as unit_tests/portability/test_acd_2100d_1.py.
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _installed_route_probe import (  # noqa: E402
    STOPPING_POINT_FIRST_QUESTION,
    install_route_into_temp_target,
    probe_installed_route,
)

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_CHECK_CONSUMER_INSTALL_SCRIPT = _WORKTREE_ROOT / "scripts" / "ci" / "check_consumer_install.py"

_PROBE_TIMEOUT = 60  # seconds; a single Node harness run against a real installed copy.
_CLI_TIMEOUT = 240  # seconds; a real build.py run plus up to two Node harness runs.

# ---------------------------------------------------------------------------
# This record's own observable contract (see module docstring) -- the exact
# exit code and marker substrings python-coder's extension of
# check_consumer_install.py must produce.
# ---------------------------------------------------------------------------
_EXIT_PRECONDITION_NOT_MET = 3
_EXIT_REGRESSION = 1
_MARKER_PRECONDITION_NOT_MET = "PRECONDITION NOT MET"
_MARKER_REGRESSION = "route-start regression"

# A minimal deployed-route stub that performs NO startup checks at all and
# reaches the first question unconditionally -- represents "a project's own
# copy [that] did not carry" whatever check the real installed source
# carries (see module docstring's "WHY A NON-GIT target_dir" section).
_NO_CHECKS_STUB_JS = (
    "'use strict';\n"
    "return { status: 'paused_awaiting_input', gate_id: 'covered-route-gate' };\n"
)

# A minimal deployed-route stub that halts BEFORE ever reaching any gate --
# represents "a project in which a run [does NOT] reach the first question
# ... before the installer is run" (this AC's Given violated).
_BROKEN_BEFORE_JS = (
    "'use strict';\n"
    "throw new Error("
    "'simulated pre-existing corruption: this project could not start "
    "before the installer ran');\n"
)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, check=True, capture_output=True, text=True
    )


def _make_git_project(tmp_path: Path) -> Path:
    """A real git repository, seeded with one commit. Mirrors
    unit_tests/portability/test_acd_2100d_1.py's own ``_make_git_project`` --
    deliberately not imported from that file (small, self-contained per-file
    fixtures over cross-file private-helper coupling).
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


def _seed_route(target_dir: Path, js_body: str) -> None:
    """Write ``js_body`` directly to
    ``target_dir/.leafcutter/workflows/plan-feature.js``, creating parent
    directories as needed. This simulates a route ALREADY deployed by some
    prior install (real or synthetic) -- the pre-existing state the CLI
    under test must read as its OWN "before" measurement, BEFORE it ever
    invokes build.py. Never used to fabricate the AFTER measurement -- the
    installer's own real run is what produces that.
    """
    script_path = target_dir / ".leafcutter" / "workflows" / "plan-feature.js"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(js_body, encoding="utf-8")


def _run_check_consumer_install(target_dir: Path, *, timeout: int) -> subprocess.CompletedProcess:
    """Invoke the REAL production entry point -- ``scripts/ci/
    check_consumer_install.py`` -- as a real subprocess, in a fresh process,
    exactly as the wired CI job invokes it (``--package-dir`` /
    ``--target-dir``). This is the reachability surface every test below
    uses; none of them import check_consumer_install.py's internals.
    """
    return subprocess.run(
        [
            sys.executable,
            str(_CHECK_CONSUMER_INSTALL_SCRIPT),
            "--package-dir",
            str(_WORKTREE_ROOT),
            "--target-dir",
            str(target_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_the_route_reaches_the_first_question_before_and_after_the_install():
    # covers: ACD-2100d-3
    # angle: criterion
    """AC-1: a run started in the project afterwards still reaches the first
    question. A temporary target project is measured first (seeded with a
    real, already-deployed route reaching the first question); the real
    installer (via check_consumer_install.py) is then run against that same
    project, and the measurement is repeated. The assertion is over the PAIR
    of recorded observations -- both ``before=`` and ``after=`` must be
    present in the CLI's own verdict text -- not merely over the second one.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100d3_pair_") as tmp:
        target_dir = _make_git_project(Path(tmp))

        seed_install = install_route_into_temp_target(_WORKTREE_ROOT, target_dir)
        assert seed_install.returncode == 0, (
            f"fixture setup failed -- could not seed a pre-existing deployed "
            f"route: stdout={seed_install.stdout!r} stderr={seed_install.stderr!r}"
        )
        seed_probe = probe_installed_route(target_dir, timeout=_PROBE_TIMEOUT)
        assert seed_probe.stopping_point == STOPPING_POINT_FIRST_QUESTION, (
            f"fixture invalid -- the pre-existing route must already reach "
            f"the first question before this test's own installer run: "
            f"{seed_probe.stopping_point!r}"
        )

        proc = _run_check_consumer_install(target_dir, timeout=_CLI_TIMEOUT)
        combined = proc.stdout + proc.stderr

        assert proc.returncode == 0, (
            f"check_consumer_install.py must report a pass (no regression) "
            f"when both readings reach the first question: got returncode="
            f"{proc.returncode}, output={combined!r}"
        )
        before_marker = f"before={STOPPING_POINT_FIRST_QUESTION!r}"
        after_marker = f"after={STOPPING_POINT_FIRST_QUESTION!r}"
        assert before_marker in combined and after_marker in combined, (
            "the verdict must report BOTH the before and the after stopping "
            f"point -- an after-only check does not satisfy this record. "
            f"expected {before_marker!r} and {after_marker!r} in output: "
            f"{combined!r}"
        )


def test_a_project_already_broken_before_the_install_does_not_pass_the_guarantee():
    # covers: ACD-2100d-3
    # angle: boundary
    """AC-1 (boundary case, load-bearing): a project seeded with a route that
    HALTS before the installer ever runs must never be reported a pass, even
    though the installer's own re-deploy repairs it. The verdict must be
    precondition-not-met and distinguishable from a pass. Also demonstrates,
    over this SAME fixture, that an after-state-only check WOULD have
    reported a pass -- the contrast that proves the before-measurement is
    load-bearing rather than computed and discarded.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100d3_broken_before_") as tmp:
        target_dir = _make_git_project(Path(tmp))
        _seed_route(target_dir, _BROKEN_BEFORE_JS)

        proc = _run_check_consumer_install(target_dir, timeout=_CLI_TIMEOUT)
        combined = proc.stdout + proc.stderr

        assert proc.returncode == _EXIT_PRECONDITION_NOT_MET, (
            f"a project that halted BEFORE the installer ran must be "
            f"reported precondition-not-met (exit {_EXIT_PRECONDITION_NOT_MET}), "
            f"never a plain pass (0) or an undifferentiated failure: got "
            f"returncode={proc.returncode}, output={combined!r}"
        )
        assert proc.returncode != 0, "must never be reported as a pass"
        assert _MARKER_PRECONDITION_NOT_MET in combined, (
            f"verdict must carry an explicit precondition-not-met marker so "
            f"it is distinguishable from a pass in the output itself: "
            f"{combined!r}"
        )

        # THE LOAD-BEARING CONTRAST: an after-state-only assertion over this
        # SAME fixture would have reported a pass, because the installer's
        # own re-deploy overwrote the broken file with a real, functioning
        # copy. This proves the before-measurement did real work rather than
        # being computed and discarded.
        after_only = probe_installed_route(target_dir, timeout=_PROBE_TIMEOUT)
        assert after_only.stopping_point == STOPPING_POINT_FIRST_QUESTION, (
            f"fixture invalid for this contrast -- expected the installer's "
            f"re-deploy to leave the project healthy on its own: "
            f"{after_only.stopping_point!r}"
        )


def test_a_startup_halt_the_project_did_not_have_before_the_install_is_reported():
    # covers: ACD-2100d-3
    # angle: failure
    """AC-2/AC-3 (the live hazard, run the wrong way round): install an
    artifact that carries a startup check the project's own copy did not
    carry (the real repository-resolution pre-flight, against a genuinely
    non-git target the minimal stub never checks at all), and assert the
    verdict is a regression naming the check that now stops the run.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100d3_regression_") as tmp:
        target_dir = Path(tmp) / "project"
        target_dir.mkdir(parents=True)
        # Deliberately NOT git-init'd -- see module docstring's "WHY A
        # NON-GIT target_dir" section: this is what makes the REAL current
        # source's repository-resolution pre-flight halt after the install,
        # while the stub seeded below performs no such check at all.
        _seed_route(target_dir, _NO_CHECKS_STUB_JS)

        seed_probe = probe_installed_route(target_dir, timeout=_PROBE_TIMEOUT)
        assert seed_probe.stopping_point == STOPPING_POINT_FIRST_QUESTION, (
            f"fixture invalid -- the seeded stub must reach the first "
            f"question with no checks performed: {seed_probe.stopping_point!r}"
        )

        proc = _run_check_consumer_install(target_dir, timeout=_CLI_TIMEOUT)
        combined = proc.stdout + proc.stderr

        assert proc.returncode == _EXIT_REGRESSION, (
            f"install introduced a startup check the project did not halt "
            f"at before -- expected exit {_EXIT_REGRESSION} (regression), "
            f"got {proc.returncode}: {combined!r}"
        )
        assert _MARKER_REGRESSION in combined, (
            f"verdict must name this a route-start regression, not an "
            f"undifferentiated failure: output={combined!r}"
        )
        before_marker = f"before={STOPPING_POINT_FIRST_QUESTION!r}"
        assert before_marker in combined, (
            f"a regression verdict must still report the BEFORE reading "
            f"that makes it a regression (rather than a plain failure): "
            f"{combined!r}"
        )
        after_marker = f"after={STOPPING_POINT_FIRST_QUESTION!r}"
        assert after_marker not in combined, (
            f"the after reading must be the DIFFERENT, halted value that "
            f"names what the install introduced, not the first-question "
            f"sentinel repeated: {combined!r}"
        )


def test_both_findings_come_from_runs_started_in_the_project_not_from_the_copy_list():
    # covers: ACD-2100d-3
    # angle: reachability
    # reachability_entry_point_answer.entry_point (this AC's own
    # test_spec.surface_invoked, verbatim): "python scripts/ci/
    # check_consumer_install.py --package-dir <pkg> --target-dir <target>
    # (CLI via subprocess) -- the wired consumer-install-simulation CI
    # entry point (.github/workflows/ci.yml:552-557)"
    """AC-3: both measurements are taken by invoking the entry point a
    consumer uses, in a fresh process -- so an install whose copied files
    are impeccable and whose deployed route still cannot start fails this
    test. The deployed file is confirmed to be the REAL, functioning script
    (not a leftover stub or a truncated copy) purely so the subsequent
    exit-code assertion cannot be dismissed as "the file was never really
    deployed" -- the finding itself still comes exclusively from the CLI's
    own exit code, produced by starting two real runs, never from comparing
    file contents.
    """
    with tempfile.TemporaryDirectory(prefix="acd2100d3_reach_") as tmp:
        target_dir = Path(tmp) / "project"
        target_dir.mkdir(parents=True)
        _seed_route(target_dir, _NO_CHECKS_STUB_JS)

        proc = _run_check_consumer_install(target_dir, timeout=_CLI_TIMEOUT)
        combined = proc.stdout + proc.stderr

        deployed_script = target_dir / ".leafcutter" / "workflows" / "plan-feature.js"
        assert deployed_script.is_file(), (
            "installer did not deploy plan-feature.js at all -- nothing to "
            "invoke, so this test cannot even attempt reachability."
        )
        deployed_text = deployed_script.read_text(encoding="utf-8")
        assert deployed_text != _NO_CHECKS_STUB_JS, (
            "installer did not actually replace the seeded stub -- fixture "
            "invalid for this test."
        )
        assert "covered-route-gate" in deployed_text and len(deployed_text) > 1000, (
            "deployed file is not the real, functioning route (an "
            "'impeccable copy') -- fixture invalid for this test."
        )

        # REACHABILITY, NOT TOPOLOGY: despite the deployed copy being a
        # genuine, complete install (asserted above), the CLI's own exit
        # code -- which main() only returns after computing the verdict from
        # TWO REAL runs it started -- still reports the regression. A
        # dispatch-topology or file-manifest check has nothing here to
        # distinguish from a pass; only starting a run in the project reveals
        # it. This is the control-flow consumption the angle requires: the
        # process's own exit code forks specifically on the runtime result.
        assert proc.returncode == _EXIT_REGRESSION, (
            f"a deployed route that copied perfectly but cannot start must "
            f"still fail this CLI's own exit code: got {proc.returncode}, "
            f"output={combined!r}"
        )
        assert _MARKER_REGRESSION in combined, combined


# DECISION HISTORY
# ================================================================================
# - 2026-09-08 [test-writer/EPIC-StartingNewWorkTheProperWayAlways/22]: Wrote
#   RED-baseline e2e tests for ACD-2100d-3 against the EXISTING
#   scripts/ci/check_consumer_install.py CLI (subprocess), per the ticket's
#   own instruction to wire into that already-gated entry point rather than
#   add a second one. Verified empirically this session (ad-hoc scripts, not
#   committed) that: (1) a minimal stub script bypassing all startup checks
#   reaches STOPPING_POINT_FIRST_QUESTION via the real harness in ~0.2s; (2) a
#   script that throws synchronously is classified "halted:no_terminal_
#   payload"; (3) a genuinely non-git target_dir makes the REAL current
#   source's workspace-setup-permission pre-flight halt with
#   result.status=="error" (repository could not be resolved), while the
#   stub above does not perform that check at all -- giving a real,
#   deterministic regression fixture without needing to check out any prior
#   git revision of the package; (4) build.py's placeholder substitution
#   (`{{config.output_root}}` -> `.leafcutter`) means the deployed copy is
#   NOT byte-identical to the source template even on a totally clean
#   install, so the reachability test asserts on functional content markers
#   instead of byte equality. All four tests are expected to fail at
#   assertion time (not at collection) against the CURRENT
#   check_consumer_install.py, which does not yet perform any before/after
#   route-start measurement -- see the module docstring for the exact
#   exit-code/marker contract python-coder must add.
#   (#EPIC-StartingNewWorkTheProperWayAlways/22)
# ================================================================================
