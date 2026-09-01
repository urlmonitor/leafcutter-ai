"""
MODULE: test_bp_900h_6
GOAL: RED test stubs for AC BP-900h-6 — the consumer-simulation job USES the
    install by attempting a REAL adopter first commit through the ordinary
    commit path (no skip flag, no environment override, no direct guard
    invocation), and reports which deployed commit-time guards actually
    EXECUTED during that commit — a record captured from the commit path's
    own output, never derived by re-reading the deployed
    ``.pre-commit-config.yaml`` registry.
TICKET: tickets/00_inbox/epics/EPIC-TheNumberingGuaranteeHoldsAtEveryStage/10_TICKET-20260825-BP-900h-6.md
AC: BP-900h-6 (source_ac)

CONTRACT (fixed by THIS test file — unlike BP-900h-1's test file, no prior
    ticket-supervisor empirical validation exists for BP-900h-6, so this
    test-writer defines the entry-point contract python-coder must implement
    against; GE-122d-6 depends on this AC and re-invokes the SAME entry point
    rather than reimplementing it, so the contract below is the one that
    ticket must also target):

    python scripts/ci/check_adopter_first_commit.py \\
        --target-dir <dir already containing a real skills_config.json and a
                       real .pre-commit-config.yaml at its root — i.e. the
                       output of BP-900h-1's check_consumer_install.py, or an
                       equivalently-shaped synthetic project>
        [--report-json <path>]

    Behaviour:
      1. Requires ``<target-dir>/skills_config.json`` and
         ``<target-dir>/.pre-commit-config.yaml`` to already exist. Exit 2
         ("usage/environment error — run check_consumer_install.py first")
         if either is absent.
      2. git-initialises ``<target-dir>`` if it is not already a repo, and
         sets a LOCAL git identity (``user.email`` / ``user.name``) on it so
         the commit can complete on an identity-less CI runner.
      3. Runs ``pre-commit install`` inside ``<target-dir>`` so the deployed
         commit-time guards are wired into the ordinary ``git commit`` hook
         path (this is what "with the deployed commit-time guards active"
         means in the AC's Given clause).
      4. Makes an ordinary adopter-shaped change: modifies
         ``skills_config.json`` (adds/updates one JSON key) — the adopter's
         own config file, per the ticket's Implementation Notes ("the
         project's own skills_config.json, or a README the adopter writes...
         do not stage an artifact from one of the numbered namespaces").
      5. ``git add skills_config.json`` — ONLY that file, never
         ``git add -A``, so the guard-execution surface matches what an
         adopter's first ordinary change actually stages, not the whole
         deployed tree (which would smuggle numbered-namespace content into
         the commit under test).
      6. ``git commit -m ...`` with NO ``--no-verify``, NO ``SKIP`` env var,
         NO ``PRE_COMMIT_ALLOW_NO_CONFIG``, and no direct invocation of any
         guard script — the ordinary commit path only.
      7. Captures the executed-guard record FROM THAT COMMIT'S OWN OUTPUT
         (pre-commit's per-hook Passed/Failed/Skipped report) — NEVER by
         re-parsing ``.pre-commit-config.yaml``'s hook list and assuming
         every listed hook ran. A hook whose ``files:`` filter excludes the
         staged file is Skipped, not executed, and MUST NOT appear in
         ``guards_executed``.
      8. Emits a JSON report (always to stdout as the last line prefixed
         ``REPORT-JSON:``; also written to ``--report-json`` when given)
         shaped:
             {
               "outcome": "passed" | "empty" | "blocked",
               "commit_completed": bool,
               "guards_executed": [{"id": str, "status": "Passed"|"Failed"}],
               "blocked_guard": {"id": str, "detail": str} | null
             }
         plus a human-readable summary line that PRINTS the guard id(s) in
         both the "passed" and "empty" cases (the "empty" case's line
         explicitly states zero guards executed) — so a commit that
         completed because nothing ran is visibly distinct in plain job
         output from a commit that completed because every guard passed,
         not only distinguishable by exit code.

    Exit codes:
      0 — the commit completed and every guard that ran passed
          (outcome == "passed", guards_executed non-empty).
      1 — the commit did not complete because a guard blocked it
          (outcome == "blocked"), OR the commit completed but ZERO guards
          executed at all (outcome == "empty" — the "guards were never
          wired" case this AC exists to catch).
      2 — usage/environment error.

    ``scripts/ci/check_adopter_first_commit.py`` does NOT exist yet in this
    worktree (confirmed via ``ls scripts/ci/`` before authoring this file —
    only ``__init__.py``, ``check_consumer_install.py``, and
    ``check_fixture_orphans.py`` are present), so every test below is
    expected to fail RED at authoring time: the subprocess invocation exits
    non-zero (Python's launcher exit code 2, "can't open file ...") rather
    than satisfying the outcome/exit-code assertions below.

REAL-ARTIFACT BEHAVIORAL TEST NOTE (BP-1100f-2 / real-effect round-trip +
    ticket constraint "ATTEMPT A REAL COMMIT — invoking a guard script
    directly ... does not cover this"): every test below drives a REAL
    ``git init`` + ``pre-commit install`` + ``git commit`` against a real
    filesystem project (never mocked) and reads the result back from the
    script's real stdout / ``--report-json`` file. Test 1 additionally
    drives a REAL ``build.py`` deploy via BP-900h-1's
    ``check_consumer_install.py`` into a directory that started genuinely
    empty — never a copy of this repository, and never with the opt-in
    documentation-seeding step run.
"""
# @ac-tag: BP-900h-6

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Path setup. conftest.py in this directory already inserts the worktree
# root onto sys.path; we additionally need concrete paths to the scripts
# under test (invoked as subprocesses, so no import is required, but we do
# need the worktree root to build --package-dir / locate ci.yml).
# ---------------------------------------------------------------------------
_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _WORKTREE_ROOT / "scripts" / "ci" / "check_adopter_first_commit.py"
_CONSUMER_INSTALL_SCRIPT = _WORKTREE_ROOT / "scripts" / "ci" / "check_consumer_install.py"
_CI_YML_PATH = _WORKTREE_ROOT / ".github" / "workflows" / "ci.yml"
_CONSUMER_JOB_NAME = "consumer-install-sim"


def _run_check_adopter_first_commit(*extra_args: str) -> subprocess.CompletedProcess[str]:
    """Invoke scripts/ci/check_adopter_first_commit.py as a real subprocess.

    Deliberately does NOT special-case a missing script file: if the script
    does not exist yet, ``subprocess.run`` still returns a
    ``CompletedProcess`` (Python's launcher exits with code 2 and prints
    "can't open file ..." to stderr) rather than raising, so callers can
    assert on ``returncode`` / ``stdout`` / ``stderr`` uniformly whether the
    script exists or not. This is the expected RED path today.
    """
    argv = [sys.executable, str(_SCRIPT_PATH), *extra_args]
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def _extract_report_json(result: subprocess.CompletedProcess[str]) -> dict:
    """Pull the ``REPORT-JSON:``-prefixed line out of stdout and parse it.

    Raises ``AssertionError`` (not a silent ``None``) when no such line is
    found, so a test that calls this gets a clear failure message pointing
    at the real captured output rather than a confusing ``KeyError``
    downstream.
    """
    for line in result.stdout.splitlines():
        if line.startswith("REPORT-JSON:"):
            payload = line[len("REPORT-JSON:") :].strip()
            try:
                return json.loads(payload)
            except json.JSONDecodeError as exc:  # pragma: no cover - diagnostic path
                raise AssertionError(
                    f"REPORT-JSON line was not valid JSON: {payload!r} ({exc})\n"
                    f"Full stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
                ) from exc
    raise AssertionError(
        "No 'REPORT-JSON:' line found in stdout — check_adopter_first_commit.py "
        "must always emit one as the machine-readable outcome record.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def _build_synthetic_adopter_project(project_dir: Path, precommit_config_yaml: str) -> None:
    """Build a minimal, real, on-disk project shaped like a deployed install.

    Writes ONLY the two files check_adopter_first_commit.py requires
    (``skills_config.json`` and ``.pre-commit-config.yaml``) — deliberately
    NOT a copy of this repository and NOT a full build.py deploy, so tests
    2-5 stay fast while still exercising a REAL git repo + REAL pre-commit
    run (never mocked). Does NOT git-init: that is the script's own
    responsibility per the contract above (step 2), so these tests also
    prove the script performs it.
    """
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "skills_config.json").write_text(
        json.dumps({"_comment": "adopter's own minimal config"}), encoding="utf-8"
    )
    (project_dir / ".pre-commit-config.yaml").write_text(precommit_config_yaml, encoding="utf-8")


def _always_pass_hook_yaml(hook_id: str) -> str:
    """A local, system-language pre-commit hook that always exits 0.

    Filtered to only run on ``skills_config.json`` — the exact file
    check_adopter_first_commit.py stages — so it is guaranteed to actually
    execute (not be Skipped) against the adopter's first commit.
    """
    return textwrap.dedent(
        f"""\
        repos:
          - repo: local
            hooks:
              - id: {hook_id}
                name: {hook_id}
                entry: python3 -c "import sys; sys.exit(0)"
                language: system
                files: ^skills_config\\.json$
                pass_filenames: false
        """
    )


def _pass_and_skip_hook_yaml(passing_id: str, skipped_id: str) -> str:
    """One hook that runs against skills_config.json (Passed), one that never matches (Skipped).

    Ground truth for test 2: a script that DERIVES the executed-guard record
    from this file's hook list (rather than capturing it from the commit's
    own output) would wrongly include ``skipped_id`` too, since it is
    registered here even though it never actually runs.
    """
    return textwrap.dedent(
        f"""\
        repos:
          - repo: local
            hooks:
              - id: {passing_id}
                name: {passing_id}
                entry: python3 -c "import sys; sys.exit(0)"
                language: system
                files: ^skills_config\\.json$
                pass_filenames: false
              - id: {skipped_id}
                name: {skipped_id}
                entry: python3 -c "import sys; sys.exit(0)"
                language: system
                files: ^this-file-will-never-be-staged\\.txt$
                pass_filenames: false
        """
    )


_HOSTILE_HOOK_ID = "adopter-hostile-organization-verified-check"
_HOSTILE_HOOK_DEMANDED_STRING = "organization_verified"


def _adopter_hostile_hook_yaml() -> str:
    """A hook that blocks over content a brand-new adopter's file legitimately lacks.

    Requires the string "organization_verified" to already be present in
    ``skills_config.json`` — something check_adopter_first_commit.py's own
    minimal adopter edit (per the contract, "adds/updates one JSON key") has
    no reason to include, so this is exactly the "guard blocks an adopter
    over an artifact a brand-new project legitimately does not yet have"
    shape the AC's Then-clause names.
    """
    check = (
        "import sys,io;"
        "content=io.open('skills_config.json',encoding='utf-8').read();"
        "sys.exit(0) if 'organization_verified' in content else "
        "(sys.stderr.write('ERROR: organization_verified key missing — "
        "adopters must verify their organization before committing\\n') or sys.exit(1))"
    )
    return textwrap.dedent(
        f"""\
        repos:
          - repo: local
            hooks:
              - id: {_HOSTILE_HOOK_ID}
                name: {_HOSTILE_HOOK_ID}
                entry: python3 -c "{check}"
                language: system
                files: ^skills_config\\.json$
                pass_filenames: false
        """
    )


def _empty_registry_yaml() -> str:
    """A structurally valid pre-commit config with zero hooks registered.

    Ground truth for the "guards were never wired" failure mode this AC
    exists to catch (KI-BO-030-adjacent: "the four commit-guardian checks
    that are deployed and registered nowhere"). ``pre-commit install`` +
    ``git commit`` both succeed against this file; zero hook lines are ever
    printed, because there is nothing to run.
    """
    return "repos: []\n"


def test_bp900h6_adopter_first_commit_completes_in_a_from_empty_install(tmp_path: Path) -> None:
    """AC BP-900h-6 happy path: real build + real commit through the ordinary path.

    Builds a consumer-simulation project into a directory that started
    empty (via BP-900h-1's REAL check_consumer_install.py — never a copy of
    this repository, never with the opt-in documentation-seeding step run),
    then invokes check_adopter_first_commit.py against it. Asserts the
    commit actually completes: ``git log`` inside the project shows exactly
    one commit, and the script's own exit code / JSON report agree.

    RED at authoring time: scripts/ci/check_adopter_first_commit.py does not
    exist, so the subprocess invocation cannot succeed.
    """
    # covers: BP-900h-6
    # angle: deployed
    target_dir = tmp_path / "consumer_project"

    install_result = subprocess.run(
        [
            sys.executable,
            str(_CONSUMER_INSTALL_SCRIPT),
            "--package-dir",
            str(_WORKTREE_ROOT),
            "--target-dir",
            str(target_dir),
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert install_result.returncode == 0, (
        "Precondition failed: BP-900h-1's check_consumer_install.py must "
        "succeed before the adopter-first-commit step can be exercised.\n"
        f"stdout:\n{install_result.stdout}\nstderr:\n{install_result.stderr}"
    )

    result = _run_check_adopter_first_commit("--target-dir", str(target_dir))

    assert result.returncode == 0, (
        "check_adopter_first_commit.py did not exit 0 for an ordinary "
        "adopter change against a real, freshly-built consumer-sim "
        f"install.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    log = subprocess.run(
        ["git", "-C", str(target_dir), "log", "--oneline"],
        capture_output=True,
        text=True,
        check=False,
    )
    commit_lines = [line for line in log.stdout.splitlines() if line.strip()]
    assert len(commit_lines) == 1, (
        "Expected exactly one real commit in the consumer-sim project after "
        f"check_adopter_first_commit.py ran. git log --oneline gave:\n{log.stdout}\n"
        f"(git log stderr: {log.stderr})\n"
        f"check_adopter_first_commit.py stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    report = _extract_report_json(result)
    assert report["commit_completed"] is True, (
        f"Expected commit_completed: true in the JSON report. Full report: {report}"
    )
    assert report["outcome"] == "passed", (
        "Expected outcome 'passed' for a real deployed install's ordinary "
        f"first commit with no adopter-hostile guard present. Full report: {report}"
    )


def test_bp900h6_executed_guard_record_is_captured_from_the_commit_itself(tmp_path: Path) -> None:
    """AC BP-900h-6: the executed-guard record must come from the commit's own output.

    Configures one hook that WILL actually run against the staged file
    (Passed) and one hook registered in .pre-commit-config.yaml that can
    NEVER match the staged file (files: filter excludes it entirely, so
    pre-commit reports it Skipped, not executed). A script that derives its
    record by re-reading the registry file's hook list — rather than
    capturing what the commit path itself reported — would wrongly include
    the never-run hook too, since both are equally "registered".

    RED at authoring time: scripts/ci/check_adopter_first_commit.py does not
    exist.
    """
    # covers: BP-900h-6
    # angle: reachability
    passing_id = "bp900h6-runs-and-passes"
    skipped_id = "bp900h6-registered-but-never-matches"
    project_dir = tmp_path / "synthetic_project"
    _build_synthetic_adopter_project(
        project_dir, _pass_and_skip_hook_yaml(passing_id, skipped_id)
    )

    result = _run_check_adopter_first_commit("--target-dir", str(project_dir))

    report = _extract_report_json(result)
    executed_ids = {entry["id"] for entry in report.get("guards_executed", [])}

    assert executed_ids, (
        "Expected a non-empty executed-guard record (at least the always-"
        f"matching hook must appear as executed). Full report: {report}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert passing_id in executed_ids, (
        f"Expected {passing_id!r} (which matches the staged file and always "
        f"exits 0) in guards_executed. Full report: {report}"
    )
    assert skipped_id not in executed_ids, (
        f"{skipped_id!r} is registered in .pre-commit-config.yaml but its "
        "files: filter can never match the staged file, so pre-commit "
        "reports it Skipped — it must NOT appear in guards_executed. A "
        "record that includes it was derived from the registry file rather "
        f"than captured from the commit's own output. Full report: {report}"
    )
    assert result.returncode == 0, (
        f"Expected exit 0 (the one guard that ran, passed).\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def test_bp900h6_empty_executed_guard_record_fails_the_job(tmp_path: Path) -> None:
    """AC BP-900h-6 must-block case: zero guards executed must fail the job.

    Uses a structurally valid .pre-commit-config.yaml with zero hooks
    registered (``repos: []``) — the real KI-BO-030-adjacent shape of "the
    guards were never wired". The underlying git commit itself completes
    (there is nothing to block it), but the job must still report failure,
    because a completed commit backed by zero guard executions is not a
    real adopter-experience validation.

    RED at authoring time: scripts/ci/check_adopter_first_commit.py does not
    exist.
    """
    # covers: BP-900h-6
    # angle: failure
    project_dir = tmp_path / "unwired_project"
    _build_synthetic_adopter_project(project_dir, _empty_registry_yaml())

    result = _run_check_adopter_first_commit("--target-dir", str(project_dir))

    report = _extract_report_json(result)
    assert report["commit_completed"] is True, (
        "The underlying git commit must complete even when zero guards ran "
        f"(nothing was configured to block it). Full report: {report}"
    )
    assert report["guards_executed"] == [], (
        f"Expected an empty guards_executed list. Full report: {report}"
    )
    assert report["outcome"] == "empty", (
        f"Expected outcome 'empty' for a commit with zero guard executions. Full report: {report}"
    )
    assert result.returncode != 0, (
        "check_adopter_first_commit.py must exit non-zero when the commit "
        "completed but no guard executed at all — an install in which "
        "nothing was wired must never be reported as a successful adopter "
        f"experience.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_bp900h6_adopter_hostile_guard_fixture_turns_the_job_red(tmp_path: Path) -> None:
    """AC BP-900h-6 can-it-go-red demonstration: a hostile guard must block and be named.

    Installs a guard fixture that requires content ("organization_verified")
    a brand-new adopter's skills_config.json legitimately does not yet have.
    Without this test, the job would be a green box that stays green on the
    exact adopter-blocking-guard defect it exists to catch.

    RED at authoring time: scripts/ci/check_adopter_first_commit.py does not
    exist.
    """
    # covers: BP-900h-6
    # angle: criterion
    project_dir = tmp_path / "hostile_guard_project"
    _build_synthetic_adopter_project(project_dir, _adopter_hostile_hook_yaml())

    result = _run_check_adopter_first_commit("--target-dir", str(project_dir))

    assert result.returncode != 0, (
        "check_adopter_first_commit.py must fail (non-zero exit) when a "
        "deployed guard blocks the adopter's first commit over content a "
        f"brand-new project legitimately does not have.\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

    report = _extract_report_json(result)
    assert report["outcome"] == "blocked", f"Expected outcome 'blocked'. Full report: {report}"
    blocked_guard = report.get("blocked_guard")
    assert blocked_guard is not None and blocked_guard.get("id") == _HOSTILE_HOOK_ID, (
        f"Expected blocked_guard.id == {_HOSTILE_HOOK_ID!r} (AC: 'naming the "
        f"guard that blocked'). Full report: {report}"
    )
    assert _HOSTILE_HOOK_DEMANDED_STRING in blocked_guard.get("detail", ""), (
        f"Expected blocked_guard.detail to name the content it demanded "
        f"({_HOSTILE_HOOK_DEMANDED_STRING!r}). Full report: {report}"
    )
    combined_output = result.stdout + result.stderr
    assert _HOSTILE_HOOK_ID in combined_output, (
        "AC: 'naming the guard that blocked' — expected the guard id to "
        f"appear in the job's plain output too.\nstdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def test_bp900h6_nothing_ran_is_reported_differently_from_everything_passed(
    tmp_path: Path,
) -> None:
    """AC BP-900h-6: the "empty" and "passed" outcomes must be visibly distinct.

    Both underlying git commits succeed (commit_completed: true in both
    reports), so exit status is not the ONLY signal available — this test
    additionally asserts the human-readable output text itself differs, with
    guard names printed in both cases per the AC ("the job records which
    guards actually executed ... and reports that record as part of its
    output").

    RED at authoring time: scripts/ci/check_adopter_first_commit.py does not
    exist.
    """
    # covers: BP-900h-6
    # angle: boundary
    passing_id = "bp900h6-boundary-everything-passed"
    passed_project = tmp_path / "passed_project"
    _build_synthetic_adopter_project(passed_project, _always_pass_hook_yaml(passing_id))

    empty_project = tmp_path / "empty_project"
    _build_synthetic_adopter_project(empty_project, _empty_registry_yaml())

    passed_result = _run_check_adopter_first_commit("--target-dir", str(passed_project))
    empty_result = _run_check_adopter_first_commit("--target-dir", str(empty_project))

    passed_report = _extract_report_json(passed_result)
    empty_report = _extract_report_json(empty_result)

    assert passed_report["commit_completed"] is True
    assert empty_report["commit_completed"] is True
    assert passed_report["outcome"] == "passed"
    assert empty_report["outcome"] == "empty"

    passed_text = passed_result.stdout
    empty_text = empty_result.stdout

    assert passed_text != empty_text, (
        "A commit that completed because every guard that ran passed must "
        "produce visibly different job output from a commit that completed "
        f"because no guard ran.\npassed stdout:\n{passed_text}\n"
        f"empty stdout:\n{empty_text}"
    )
    assert passing_id in passed_text, (
        f"Expected the guard name {passing_id!r} printed in the 'passed' "
        f"case's output (AC: guard names printed). stdout:\n{passed_text}"
    )
    assert passing_id not in empty_text, (
        "The 'empty' case's output must not claim the (unrelated, "
        f"different-project) guard {passing_id!r} ran.\nstdout:\n{empty_text}"
    )
    assert passed_result.returncode == 0
    assert empty_result.returncode != 0


def test_bp900h6_ci_step_has_no_continue_on_error_and_no_pull_request_skip() -> None:
    """AC BP-900h-6: the real ci.yml step must have no continue-on-error / no PR skip.

    Parses the ACTUAL .github/workflows/ci.yml this repo's CI runs — never a
    hand-typed fixture (BP-1100f-2 / real-artifact rule) — and asserts the
    consumer-simulation job's use-the-install step exists, carries no
    ``continue-on-error``, and neither the job nor the step carries an
    ``if:`` condition that skips it on ``pull_request`` events.

    RED at authoring time: no step in ci.yml yet invokes
    check_adopter_first_commit.py (the step does not exist), so the "find
    exactly one such step" assertion fails.
    """
    # covers: BP-900h-6
    # angle: real_artifact
    assert _CI_YML_PATH.is_file(), f"Expected {_CI_YML_PATH} to exist."
    workflow = yaml.safe_load(_CI_YML_PATH.read_text(encoding="utf-8"))

    jobs = workflow.get("jobs", {})
    assert _CONSUMER_JOB_NAME in jobs, (
        f"Expected job {_CONSUMER_JOB_NAME!r} in ci.yml. Jobs found: {sorted(jobs)}"
    )
    job = jobs[_CONSUMER_JOB_NAME]

    job_if = job.get("if")
    assert job_if is None or "pull_request" not in str(job_if), (
        f"Job {_CONSUMER_JOB_NAME!r} must not carry an `if:` that excludes "
        f"pull_request events. Found: {job_if!r}"
    )

    steps = job.get("steps", [])
    matching_steps = [
        step
        for step in steps
        if "check_adopter_first_commit.py" in str(step.get("run", ""))
    ]
    assert len(matching_steps) == 1, (
        "Expected exactly one step in the consumer-simulation job invoking "
        f"check_adopter_first_commit.py. Found {len(matching_steps)}. "
        f"Full step list: {steps}"
    )
    step = matching_steps[0]

    assert "continue-on-error" not in step or not step["continue-on-error"], (
        f"AC: the step must carry no continue-on-error. Step: {step}"
    )
    step_if = step.get("if")
    assert step_if is None or "pull_request" not in str(step_if), (
        f"AC: the step must not be skipped on pull_request events. Step: {step}"
    )


def test_bp900h6_workflow_step_and_test_invoke_the_same_entry_point() -> None:
    """AC BP-900h-6 / IT-PO 2026-08-25: the workflow step must call the SAME script.

    Reads the real ci.yml step's `run:` command and asserts it resolves to
    the exact same script file this test module invokes throughout
    (scripts/ci/check_adopter_first_commit.py), and that the step carries no
    logic of its own beyond arguments (no `&&`, `;`, `|`, or multi-line
    shell block) — otherwise every other test in this file would be
    exercising a COPY of the job rather than the job itself.

    RED at authoring time: no such step exists yet in ci.yml.
    """
    # covers: BP-900h-6
    # angle: seam
    workflow = yaml.safe_load(_CI_YML_PATH.read_text(encoding="utf-8"))
    jobs = workflow.get("jobs", {})
    job = jobs.get(_CONSUMER_JOB_NAME, {})
    steps = job.get("steps", [])
    matching_steps = [
        step
        for step in steps
        if "check_adopter_first_commit.py" in str(step.get("run", ""))
    ]
    assert len(matching_steps) == 1, (
        "Expected exactly one step invoking check_adopter_first_commit.py "
        f"in job {_CONSUMER_JOB_NAME!r}. Found {len(matching_steps)}. "
        f"Full step list: {steps}"
    )
    run_command = matching_steps[0]["run"]

    for forbidden in ("&&", ";", "|", "\n"):
        assert forbidden not in run_command, (
            f"AC: the step must carry no logic of its own beyond arguments — "
            f"found {forbidden!r} in run command: {run_command!r}. Behaviour "
            "belongs in check_adopter_first_commit.py, not inlined in ci.yml."
        )

    # The command must reference the script at the exact repo-relative path
    # this test module resolves _SCRIPT_PATH from (leafcutter-ai/ is the
    # checkout subdirectory per the job's `actions/checkout` `path:`).
    expected_relative_script = "scripts/ci/check_adopter_first_commit.py"
    assert expected_relative_script in run_command, (
        f"Expected the ci.yml step's run command to invoke "
        f"{expected_relative_script!r} (the same script "
        f"{_SCRIPT_PATH} this test module invokes) — found: {run_command!r}"
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-01 [test-writer/EPIC-TheNumberingGuaranteeHoldsAtEveryStage/10_BP-900h-6]:
#   Initial failing test stubs. scripts/ci/check_adopter_first_commit.py does
#   not exist yet (confirmed via ls scripts/ci/ before authoring — only
#   __init__.py, check_consumer_install.py, check_fixture_orphans.py are
#   present). Unlike BP-900h-1's sibling test file, no ticket-supervisor
#   empirical validation had already fixed this AC's CLI contract, so this
#   file defines it: a single `--target-dir` CLI entry point that
#   git-initialises the project, runs `pre-commit install`, makes an
#   adopter-shaped edit to skills_config.json only (never `git add -A`,
#   per the ticket's Implementation Notes about numbered-namespace content),
#   commits through the ordinary path, and emits a `REPORT-JSON:`-prefixed
#   JSON line capturing outcome/commit_completed/guards_executed/
#   blocked_guard — captured from the commit's own pre-commit output, never
#   derived from re-reading .pre-commit-config.yaml's hook list (test 2's
#   Skipped-vs-executed hook pair is the ground truth that would catch a
#   registry-derived implementation). Tests 3-5 build lightweight synthetic
#   git projects (real git init + real pre-commit install + real git commit,
#   never mocked, per BP-1100f-2) rather than a full build.py deploy, to keep
#   runtime reasonable while still proving the empty/blocked/boundary
#   outcomes on real commit paths; test 1 alone drives the full real
#   BP-900h-1 build.py deploy into a genuinely empty directory (angle:
#   deployed). Tests 6-7 parse the real on-disk .github/workflows/ci.yml via
#   yaml.safe_load — never a hand-typed fixture — and are expected to fail
#   on "step not found", since the new step does not exist in ci.yml yet.
#   Direct `git commit` invocation from this agent's own Bash tool is
#   blocked by the enforce_commit_delegation PreToolUse hook, so the
#   pre-commit-config fixture shapes above (empty registry / skip-filtered
#   hook / hostile hook) were designed from first principles against
#   pre-commit's documented per-hook Passed/Failed/Skipped reporting rather
#   than empirically probed via an interactive `git commit` in this
#   environment — python-coder should treat the exact substring/regex used
#   to parse pre-commit's stdout as its own implementation detail, since
#   these tests only assert on check_adopter_first_commit.py's OWN
#   REPORT-JSON output, not on pre-commit's raw text.
# ====================================================================
