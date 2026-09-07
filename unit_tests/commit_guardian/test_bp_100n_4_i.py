"""
MODULE: unit_tests/commit_guardian/test_bp_100n_4_i.py
GOAL: BP-100n-4-i — a script that is deliberately not a gate must be
    recordable in a register with a stated ground, and the reachability
    check must honour a grounded record (reported as a declared non-gate,
    excluded from the invoked-by-nothing class, does not fail the run) while
    refusing a groundless one (reported as refused, the script it names
    stays reported and the run still fails), reporting a stale record
    (naming a script absent from disk) and a redundant record (naming a
    script that is actually invoked) as their own distinct conditions.
BUSINESS CONTEXT: KI-CG-20260831-hook-scripts-never-invoked's remediation:
    "register, delete, or add to the exemption registry with a stated
    ground" for each of the scripts BP-100n-4 finds invoked by nothing. This
    AC is the third disposition — the one that keeps the census alive after
    it is first right about something inconvenient, per
    templates/scripts/commit_guardian/_hook_trigger_reachability_helpers.py's
    existing validate_exemptions() precedent for registered gates
    (BP-100k-4-i), extended here with a SECOND, script-keyed record shape
    for scripts no registry entry names at all (an unregistered script has
    no gate id to be keyed by).
    See docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/BP-100n-4-i.yaml.

NEW PRODUCTION BEHAVIOUR THIS TEST FILE SPECIFIES (does not exist yet):
    The existing top-level ``hook_trigger_reachability_exemption_registry``
    key of commit_guardian.json (id-keyed entries, unchanged) gains a
    SECOND valid entry shape: ``{"script": "<filename-or-path>", "ground":
    "<text>"}``, for a script BP-100n-4's disk-side census finds that no
    registry entry names.

    Per-record diagnostic lines (extending the vocabulary already
    introduced by test_bp_100n_4.py's RESULT-line contract, reused
    verbatim — see that file's module docstring):
      ``DECLARED-NON-GATE: <script> ground=<text>`` — a grounded record;
          excluded from ``unreferenced=``, never fails the run by itself.
      ``REJECTED NON-GATE RECORD: <script> reason=<free text>`` — a
          groundless record (blank/whitespace-only ``ground``); the named
          script STAYS in the ``UNREFERENCED:`` report and the run still
          fails on it — the observable difference between a register that
          is checked and one that is merely consulted.
      ``STALE NON-GATE RECORD: <script> reason=<free text>`` — a record
          naming a script not present on disk.
      ``REDUNDANT NON-GATE RECORD: <script> reason=<free text>`` — a record
          naming a script that IS invoked by an emitted entry line; the
          script itself is reported in neither UNREFERENCED nor
          DECLARED-NON-GATE (it is simply invoked, silently, exactly as
          BP-100n-4 requires for any invoked script) but the redundant
          record is named so cover that has outlived its subject does not
          silently persist.
      RESULT line gains ``declared_non_gate=<n>`` (already anticipated in
          test_bp_100n_4.py's contract) stating the register's honoured size.

RED BASELINE (expected): every test below is RED. No such register shape,
    validator, or diagnostic vocabulary exists yet — every regex search
    against the lines above returns None, and BP-100n-4's own
    compared/registered/unreferenced/declared_non_gate RESULT fields are
    themselves unimplemented, so even the summary-count descriptor is red
    for the same underlying reason.

    Per CLAUDE.md "Gate / Workflow ACs — Verify Behaviorally, Not by Grep":
    every test executes the real check_hook_trigger_reachability.py as a
    subprocess over a REAL fixture copy of
    templates/scripts/commit_guardian/, with the register records added by
    parsing and re-dumping the copied commit_guardian.json via ``json``
    (the real serializer) — never a hand-typed JSON literal.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CG_TEMPLATES_SRC = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_REACHABILITY_HOOK_NAME = "check_hook_trigger_reachability.py"

_SUBPROCESS_TIMEOUT_SECONDS = 30

_RESULT_LINE_RE = re.compile(
    r"check-hook-trigger-reachability:\s*RESULT\b"
    r".*?\bcompared=(\d+)\b"
    r".*?\bregistered=(\d+)\b"
    r".*?\bunreferenced=(\d+)\b"
    r".*?\bdeclared_non_gate=(\d+)\b",
    re.IGNORECASE | re.DOTALL,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "bp100n4itest@example.com"], repo)
    _git(["config", "user.name", "BP-100n-4-i Test"], repo)


def _commit_all(repo: Path, message: str) -> None:
    _git(["add", "-A"], repo)
    _git(["commit", "-m", message], repo)


def _deploy_gate_dir_copy(workspace: Path) -> Path:
    """Copy the REAL, unmodified templates/scripts/commit_guardian/ tree."""
    dest = workspace / "commit_guardian_copy"
    shutil.copytree(_CG_TEMPLATES_SRC, dest, ignore=shutil.ignore_patterns("__pycache__"))
    return dest


def _run_reachability_hook(
    script_path: Path, cwd: Path, env_overrides: dict | None = None
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )


def _write_gate_script(path: Path) -> None:
    path.write_text("#!/usr/bin/env python3\nimport sys\n\nsys.exit(0)\n", encoding="utf-8")


def _add_non_gate_records(gate_dir: Path, records: list[dict]) -> None:
    """Extend the COPIED commit_guardian.json's
    hook_trigger_reachability_exemption_registry with *records*, via
    json.load/json.dump — the real serializer, never a hand-typed literal
    (Fixture Authenticity Rule, 2h.2).
    """
    registry_path = gate_dir / "commit_guardian.json"
    with open(registry_path, encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("hook_trigger_reachability_exemption_registry", [])
    data["hook_trigger_reachability_exemption_registry"].extend(records)
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(data, f)


class _FixtureRepoTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name)
        _init_repo(self.workspace)
        self.gate_dir = _deploy_gate_dir_copy(self.workspace)
        self.script_path = self.gate_dir / _REACHABILITY_HOOK_NAME

    def _commit(self) -> None:
        _commit_all(self.workspace, "fixture snapshot for BP-100n-4-i")

    def tearDown(self) -> None:
        self._tmp.cleanup()


# ---------------------------------------------------------------------------
# test_spec 1: a grounded record is a declared non-gate, quoting its ground.
# ---------------------------------------------------------------------------


class TestGroundedRecordIsDeclaredNonGate(_FixtureRepoTestCase):
    def setUp(self) -> None:
        super().setUp()
        _write_gate_script(self.gate_dir / "check_bp_100n_4_i_novel_fixture.py")
        _add_non_gate_records(
            self.gate_dir,
            [
                {
                    "script": "check_bp_100n_4_i_novel_fixture.py",
                    "ground": "fixture-only helper, never a gate",
                }
            ],
        )
        self._commit()

    def test_bp_100n_4_i_a_grounded_record_is_a_declared_non_gate_quoting_its_ground(
        self,
    ) -> None:
        # covers: BP-100n-4-i
        # angle: criterion
        """A script whose register record states a ground is reported as a
        declared non-gate with that ground quoted, absent from the
        invoked-by-nothing report, and does not drive a non-zero exit by
        itself.
        """
        result = _run_reachability_hook(self.script_path, self.workspace)
        output = result.stdout + result.stderr
        self.assertRegex(
            output,
            r"DECLARED-NON-GATE:\s*\S*check_bp_100n_4_i_novel_fixture\.py"
            r"\s+ground=fixture-only helper, never a gate",
            f"expected a quoted, grounded declared-non-gate verdict; got {output!r}",
        )
        self.assertNotRegex(
            output,
            r"UNREFERENCED:\s*\S*check_bp_100n_4_i_novel_fixture\.py",
            "a grounded declared non-gate must never also appear in the "
            "invoked-by-nothing report",
        )


# ---------------------------------------------------------------------------
# test_spec 2: a groundless record is refused; its script stays reported.
# ---------------------------------------------------------------------------


class TestGroundlessRecordIsRefusedAndScriptStaysReported(_FixtureRepoTestCase):
    def setUp(self) -> None:
        super().setUp()
        _write_gate_script(self.gate_dir / "check_bp_100n_4_i_groundless_fixture.py")
        _add_non_gate_records(
            self.gate_dir,
            [{"script": "check_bp_100n_4_i_groundless_fixture.py", "ground": "   "}],
        )
        self._commit()

    def test_bp_100n_4_i_a_groundless_record_is_refused_and_its_script_stays_reported(
        self,
    ) -> None:
        # covers: BP-100n-4-i
        # angle: failure
        """A record naming a script but stating no ground (blank/whitespace
        only) is reported as refused, and — the observable difference
        between a register that is CHECKED and one that is merely
        CONSULTED — its script remains in the invoked-by-nothing report and
        the run still fails on it.
        """
        result = _run_reachability_hook(self.script_path, self.workspace)
        output = result.stdout + result.stderr
        self.assertRegex(
            output,
            r"REJECTED NON-GATE RECORD:\s*\S*check_bp_100n_4_i_groundless_fixture\.py",
            f"expected the record to be reported refused; got {output!r}",
        )
        self.assertRegex(
            output,
            r"UNREFERENCED:\s*\S*check_bp_100n_4_i_groundless_fixture\.py",
            "a blank ground must not remove the script from the "
            f"invoked-by-nothing report; got {output!r}",
        )
        self.assertNotEqual(
            result.returncode,
            0,
            "a script whose non-gate record was refused must still fail the run",
        )


# ---------------------------------------------------------------------------
# test_spec 3: a record naming an absent script is reported stale by name.
# ---------------------------------------------------------------------------


class TestStaleRecordIsReportedByName(_FixtureRepoTestCase):
    def setUp(self) -> None:
        super().setUp()
        # Deliberately do NOT create this file on disk.
        _add_non_gate_records(
            self.gate_dir,
            [
                {
                    "script": "check_bp_100n_4_i_does_not_exist.py",
                    "ground": "some stated ground",
                }
            ],
        )
        self._commit()

    def test_bp_100n_4_i_a_record_naming_an_absent_script_is_reported_stale_by_name(
        self,
    ) -> None:
        # covers: BP-100n-4-i
        # angle: boundary
        """A record naming a script not present on disk is reported as
        stale and named, so the register cannot accumulate cover for
        scripts that no longer exist.
        """
        result = _run_reachability_hook(self.script_path, self.workspace)
        output = result.stdout + result.stderr
        self.assertRegex(
            output,
            r"STALE NON-GATE RECORD:\s*check_bp_100n_4_i_does_not_exist\.py",
            f"expected the stale record to be named; got {output!r}",
        )


# ---------------------------------------------------------------------------
# test_spec 4: the summary states the declared-non-gate count.
# ---------------------------------------------------------------------------


class TestSummaryStatesDeclaredNonGateCount(_FixtureRepoTestCase):
    def test_bp_100n_4_i_the_summary_states_the_declared_non_gate_count(self) -> None:
        # covers: BP-100n-4-i
        # angle: criterion
        """The run summary states the number of declared non-gates,
        alongside compared/registered/unreferenced, visible in every run.
        Asserted by varying the register between two runs and requiring the
        stated count to move with it — never against a fixed literal.
        """
        _commit_all(self.workspace, "baseline, no non-gate records")
        baseline = _run_reachability_hook(self.script_path, self.workspace)
        baseline_match = _RESULT_LINE_RE.search(baseline.stdout + baseline.stderr)
        self.assertIsNotNone(
            baseline_match,
            "expected a RESULT line stating declared_non_gate=<n> on the "
            f"baseline run; got {(baseline.stdout + baseline.stderr)!r}",
        )
        baseline_declared = int(baseline_match.group(4))

        _write_gate_script(self.gate_dir / "check_bp_100n_4_i_count_fixture.py")
        _add_non_gate_records(
            self.gate_dir,
            [{"script": "check_bp_100n_4_i_count_fixture.py", "ground": "counted fixture"}],
        )
        _commit_all(self.workspace, "one non-gate record added")
        after = _run_reachability_hook(self.script_path, self.workspace)
        after_match = _RESULT_LINE_RE.search(after.stdout + after.stderr)
        self.assertIsNotNone(
            after_match,
            "expected a RESULT line on the second run; got "
            f"{(after.stdout + after.stderr)!r}",
        )
        after_declared = int(after_match.group(4))

        self.assertEqual(
            after_declared,
            baseline_declared + 1,
            "the stated declared_non_gate count must move with the register's own size",
        )


# ---------------------------------------------------------------------------
# test_spec 5: a record covering an invoked script is named as redundant.
# ---------------------------------------------------------------------------


class TestRecordCoveringInvokedScriptIsNamedRedundant(_FixtureRepoTestCase):
    def setUp(self) -> None:
        super().setUp()
        # check_ac_limits.py is present on disk AND invoked by an emitted
        # entry line under id check-ac-tree-limits in the real registry.
        _add_non_gate_records(
            self.gate_dir,
            [{"script": "check_ac_limits.py", "ground": "obsolete exemption"}],
        )
        self._commit()

    def test_bp_100n_4_i_a_record_covering_an_invoked_script_is_named_as_redundant(
        self,
    ) -> None:
        # covers: BP-100n-4-i
        # angle: criterion
        """A script present on disk, invoked by the commit-time
        configuration, and also carrying a register record is reported as
        invoked (i.e. NOT reported unreferenced or declared-non-gate — the
        BP-100n-4 silent, correct outcome for an invoked script), and the
        redundant record is named separately, so the register does not
        silently retain cover for a script that no longer needs it.
        """
        result = _run_reachability_hook(self.script_path, self.workspace)
        output = result.stdout + result.stderr
        self.assertRegex(
            output,
            r"REDUNDANT NON-GATE RECORD:\s*check_ac_limits\.py",
            f"expected the redundant record to be named; got {output!r}",
        )
        self.assertNotRegex(
            output,
            r"UNREFERENCED:\s*\S*check_ac_limits\.py",
            "an invoked script must never be reported unreferenced, "
            "redundant record or not",
        )
        self.assertNotRegex(
            output,
            r"DECLARED-NON-GATE:\s*\S*check_ac_limits\.py",
            "an invoked script covered by a redundant record must not be "
            "reported as a declared non-gate — it is invoked",
        )


# ---------------------------------------------------------------------------
# test_spec 6: declared non-gate verdicts reach the registered hook, from
# the deployed layout.
# ---------------------------------------------------------------------------


class TestDeclaredNonGateVerdictsReachRegisteredHookDeployed(unittest.TestCase):
    def test_bp_100n_4_i_declared_non_gate_verdicts_are_emitted_through_the_registered_hook(
        self,
    ) -> None:
        # covers: BP-100n-4-i
        # angle: reachability
        """PRODUCTION ENTRY POINT, FROM THE DEPLOYED LAYOUT. Run the check
        as a subprocess through the registered hook path
        (run_hook.py -> check_hook_trigger_reachability.py) with the
        register records read from a REAL commit_guardian.json (built by
        copying the deployed layout), and assert the declared-non-gate
        verdicts and the register count appear in the hook's own output.
        Add a record to the canonical TEMPLATE copy and assert it is
        invisible until the copy under test is the one actually read — the
        canonical-versus-build-output trap made observable.
        """
        _tmp = tempfile.TemporaryDirectory()
        try:
            workspace = Path(_tmp.name)
            _init_repo(workspace)
            gate_dir = _deploy_gate_dir_copy(workspace)
            _write_gate_script(gate_dir / "check_bp_100n_4_i_reachability_fixture.py")
            _add_non_gate_records(
                gate_dir,
                [
                    {
                        "script": "check_bp_100n_4_i_reachability_fixture.py",
                        "ground": "reachability-path fixture",
                    }
                ],
            )
            _commit_all(workspace, "deployed-layout non-gate record fixture")

            run_hook_path = gate_dir / "run_hook.py"
            script_path = gate_dir / _REACHABILITY_HOOK_NAME
            result = subprocess.run(
                [sys.executable, str(run_hook_path), str(script_path)],
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT_SECONDS,
                check=False,
            )
            output = result.stdout + result.stderr
            self.assertRegex(
                output,
                r"DECLARED-NON-GATE:\s*\S*check_bp_100n_4_i_reachability_fixture\.py",
                "expected the declared-non-gate verdict through the "
                f"registered hook entry point; got {output!r}",
            )
            match = _RESULT_LINE_RE.search(output)
            self.assertIsNotNone(
                match, f"expected the declared_non_gate= count in the RESULT line; got {output!r}"
            )
        finally:
            _tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
