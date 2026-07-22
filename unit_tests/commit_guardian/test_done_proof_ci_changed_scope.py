"""
MODULE: unit_tests/commit_guardian/test_done_proof_ci_changed_scope.py
GOAL: RED test stubs for BO-2500b-3 — diff-scoped CI mode for check_done_proof.py
      that evaluates done-proof ONLY on ACs changed in the current PR, making
      the check safe to promote to a REQUIRED (non-optional) merge gate without
      failing on legacy done-ACs that predate the covers-tag mandate.

BUSINESS CONTEXT: BO-2500b-3 mandates that the CI done-proof job be a blocking
    required status check. The current ci mode (check_all_done_acs) scans the
    WHOLE AC store, which includes hundreds of pre-existing done ACs that lack
    covers tags — so the job is kept informational (continue-on-error: true).
    A new diff-scoped mode restricts enforcement to ACs CHANGED in the PR,
    allowing the job to become required without triggering on legacy debt.

ARCHITECTURE: Three complementary targets these tests enforce:

  1. check_changed_done_acs(changed_yaml_paths, *, ac_root, test_root) -> list[dict]
        A new public function in scripts/commit_guardian/check_done_proof.py.
        Given AC YAML paths changed in the PR, evaluates done-proof (via
        verify_done_eligible) ONLY for those whose work_status is "done".
        Pre-existing done ACs NOT in changed_yaml_paths are never evaluated
        — this is the property that makes the mode safe to require.

  2. main() -- mode 'ci-changed' with --base <ref> (default: origin/main)
        A new mode that computes changed AC yaml paths via
        `git diff --name-only <base>...HEAD`, filters for
        docs/acceptance-criteria/**/*.yaml, and calls check_changed_done_acs.
        Exits non-zero (fail-closed) on any violation; exits 0 otherwise.

  3. .github/workflows/ci.yml structural contract
        The done-proof job must NOT have continue-on-error: true (it becomes
        a required gate), and must invoke --mode ci-changed (diff-scoped).
        These tests parse the REAL ci.yml — never a hand-typed copy.

FIXTURE AUTHENTICITY MANDATE (BO-2500c):
    All AC YAML fixtures are written with yaml.safe_dump (not hand-typed YAML).
    All covers-test fixtures are real .py files with genuine test bodies.
    ci.yml assertions parse the real file from the repo.

RED BASELINE:
    All tests are RED until python-coder:
      - Adds check_changed_done_acs() to check_done_proof.py
      - Extends main() with --mode ci-changed and --base <ref>
      - Updates .github/workflows/ci.yml: removes continue-on-error and
        switches the done-proof step to --mode ci-changed

=== Interface contract under test (to be implemented by python-coder) ===

  check_changed_done_acs(
      changed_yaml_paths: list[Path],
      *,
      ac_root: Path,
      test_root: Path,
  ) -> list[dict]

    Evaluates done-proof (via verify_done_eligible) for every AC YAML path
    in changed_yaml_paths whose work_status is "done".  ACs NOT in
    changed_yaml_paths are never evaluated, even if they are done and lack
    covers tests (key scoping invariant).  Returns violation dicts:
    {"ac_id": str, "reason": str}.

  main(argv) extended:
    New mode "ci-changed" added to argparse choices.
    New argument --base <ref> with default "origin/main".
    When --mode ci-changed: computes git diff paths, calls check_changed_done_acs,
    exits 1 if violations found, 0 otherwise.

  .github/workflows/ci.yml:
    done-proof job must NOT have continue-on-error: true.
    done-proof step must invoke check_done_proof.py --mode ci-changed.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Repo path wiring — same pattern as test_bo2500b_done_proof_hook.py
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "scripts" / "commit_guardian"
_AC_STORE_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_COMMIT_GUARDIAN_DIR))
sys.path.insert(0, str(_AC_STORE_DIR))

# This import FAILS with ImportError until python-coder adds check_changed_done_acs()
# to scripts/commit_guardian/check_done_proof.py.
# The ImportError IS the intended red state — all tests fail here until
# check_changed_done_acs is implemented.
from check_done_proof import check_changed_done_acs  # noqa: E402
from check_done_proof import main  # noqa: E402  (already exists; imported for CLI tests)

_PYTHON_EXE = sys.executable


# ---------------------------------------------------------------------------
# Shared fixture helpers (yaml.safe_dump — BO-2500c mandate)
# ---------------------------------------------------------------------------


def _write_ac(
    ac_root: Path,
    ac_id: str,
    *,
    status: str = "active",
    work_status: str = "done",
) -> Path:
    """Write a minimal AC YAML using yaml.safe_dump (mandate-compliant).

    Args:
        ac_root: Root directory of the synthetic AC store.
        ac_id: Identifier for the AC.
        status: AC lifecycle status (default: "active").
        work_status: AC work status (default: "done").

    Returns:
        Path to the written YAML file.
    """
    subdir = ac_root / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict = {
        "id": ac_id,
        "title": f"Synthetic test AC {ac_id}",
        "component": "build-orchestration",
        "level": "L2",
        "status": status,
        "work_status": work_status,
        "readiness": "draft",
        "priority": "medium",
        "depends_on": [],
        "amended_by": [],
        "covered_by": [],
        "implemented_by": [],
        "superseded_by": None,
    }
    # Mandate: use yaml.safe_dump, not a hand-typed YAML literal (BO-2500c).
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _write_test_file(test_root: Path, filename: str, content: str) -> Path:
    """Write a Python test file to test_root using textwrap.dedent.

    Args:
        test_root: Directory to place the test file.
        filename: Filename (e.g. "test_my_feature.py").
        content: Python source; leading whitespace is dedented automatically.

    Returns:
        Path to the written test file.
    """
    test_root.mkdir(parents=True, exist_ok=True)
    path = test_root / filename
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# TestCheckChangedDoneAcs — core function tests
# ---------------------------------------------------------------------------


class TestCheckChangedDoneAcs(unittest.TestCase):
    """BO-2500b-3: check_changed_done_acs evaluates done-proof only on changed ACs."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.test_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac1_changed_done_without_covers_is_reported(self) -> None:
        # covers: BO-2500b-3
        """A changed done AC with no covers test must be reported as a violation.

        check_changed_done_acs must call verify_done_eligible for changed done ACs.
        When no covers-tagged test exists in test_root, verify_done_eligible returns
        eligible=False, and the AC must appear in the returned violation list.

        To make this green: implement check_changed_done_acs() so it evaluates
        verify_done_eligible for each changed yaml path whose work_status is done.
        """
        ac_id = "BO-B3-CHANGED-NOTAG"
        ac_path = _write_ac(self.ac_root, ac_id, work_status="done")
        # test_root is intentionally empty — no covers tag exists

        violations = check_changed_done_acs(
            [ac_path],
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        ac_ids_in_violations = [v["ac_id"] for v in violations]
        self.assertIn(
            ac_id,
            ac_ids_in_violations,
            f"A changed done AC with no covers test must appear in violations. "
            f"Got violations: {violations}",
        )

    def test_ac1_changed_done_with_passing_covers_is_not_reported(self) -> None:
        # covers: BO-2500b-3
        """A changed done AC whose covers test PASSES must NOT be reported.

        check_changed_done_acs delegates to verify_done_eligible. When that oracle
        returns eligible=True (covers test exists and passes), no violation is emitted.
        """
        ac_id = "BO-B3-CHANGED-HASTAG"
        ac_path = _write_ac(self.ac_root, ac_id, work_status="done")
        _write_test_file(
            self.test_root,
            "test_changed_passing.py",
            f"""\
            def test_covers_changed_pass():
                # covers: {ac_id}
                pass  # genuinely passes
            """,
        )

        violations = check_changed_done_acs(
            [ac_path],
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        ac_ids_in_violations = [v["ac_id"] for v in violations]
        self.assertNotIn(
            ac_id,
            ac_ids_in_violations,
            f"A changed done AC with a passing covers test must NOT be reported. "
            f"Got violations: {violations}",
        )

    def test_ac1_preexisting_done_ac_not_in_changed_list_is_not_reported(
        self,
    ) -> None:
        # covers: BO-2500b-3
        # covers: BO-2500b-1-i
        """KEY INVARIANT: A pre-existing done AC NOT in changed_yaml_paths must never
        be reported, even when it has no covers test.

        This is the property that makes it safe to promote the CI check to a REQUIRED
        gate: pre-existing done ACs that predate the covers-tag mandate are silently
        ignored by check_changed_done_acs. Only ACs explicitly listed in
        changed_yaml_paths are evaluated.

        Proof that this test is the right guard: if check_changed_done_acs internally
        scans ac_root (like check_all_done_acs does), this test fails. Only an
        implementation that restricts evaluation to changed_yaml_paths passes.

        Both the "preexisting not reported" AND "changed is reported" assertions must
        hold simultaneously — verifying the function ran but only evaluated changed ACs.
        """
        # Preexisting AC: done, no covers test, NOT in the changed_yaml_paths list.
        preexisting_id = "BO-B3-PREEXIST-NOTAG"
        _write_ac(self.ac_root, preexisting_id, work_status="done")

        # Changed AC: done, no covers test, IS in the changed_yaml_paths list
        # (non-empty violations list proves the function actually executed).
        changed_id = "BO-B3-CHANGED-NOTAG2"
        changed_path = _write_ac(self.ac_root, changed_id, work_status="done")

        # Only the changed AC path is provided; preexisting AC must be silently ignored.
        violations = check_changed_done_acs(
            [changed_path],  # preexisting_id is intentionally absent
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        ac_ids_in_violations = [v["ac_id"] for v in violations]

        # The preexisting AC must NOT be reported (not in changed_yaml_paths).
        self.assertNotIn(
            preexisting_id,
            ac_ids_in_violations,
            "KEY INVARIANT: a pre-existing done AC NOT in changed_yaml_paths must "
            "NOT be reported, even when it has no covers test. "
            "check_changed_done_acs must evaluate ONLY the provided paths, "
            "not scan the full ac_root like check_all_done_acs does. "
            f"Got violations: {violations}",
        )

        # The changed AC MUST be reported (it IS in changed_yaml_paths, no covers test).
        self.assertIn(
            changed_id,
            ac_ids_in_violations,
            "The changed done AC without covers must still be reported "
            "(verifies the function actually ran and evaluated changed_yaml_paths). "
            f"Got violations: {violations}",
        )

    def test_ac1_changed_non_done_ac_is_not_reported(self) -> None:
        # covers: BO-2500b-3
        """A changed AC with work_status other than 'done' must NOT be evaluated.

        ACs in todo, in-progress, or any other non-done state are skipped even
        when they appear in changed_yaml_paths. The gate only applies to ACs
        explicitly marked done.
        """
        ac_id = "BO-B3-CHANGED-TODO"
        ac_path = _write_ac(self.ac_root, ac_id, work_status="todo")
        # No covers tag — but work_status is "todo", so this AC must be ignored.

        violations = check_changed_done_acs(
            [ac_path],
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        ac_ids_in_violations = [v["ac_id"] for v in violations]
        self.assertNotIn(
            ac_id,
            ac_ids_in_violations,
            "A changed AC with work_status=todo must NOT be reported. "
            f"Got violations: {violations}",
        )

    def test_ac1_changed_done_with_failing_covers_is_reported(self) -> None:
        # covers: BO-2500b-3
        # covers: BO-2500b-1-i
        """A changed done AC whose covers test FAILS must be reported (fail-closed).

        check_changed_done_acs delegates to verify_done_eligible which runs the
        actual pytest test. A covers tag that exists but whose test fails must
        still produce a violation — a static tag-presence check alone is insufficient.
        This is the same fail-closed contract as BO-2500b-1-i: a tag that exists
        but fails is still a blocked merge.
        """
        ac_id = "BO-B3-CHANGED-FAILING"
        ac_path = _write_ac(self.ac_root, ac_id, work_status="done")
        _write_test_file(
            self.test_root,
            "test_changed_failing.py",
            f"""\
            def test_covers_changed_fail():
                # covers: {ac_id}
                assert False, "intentional failure — changed-scope check must catch this"
            """,
        )

        violations = check_changed_done_acs(
            [ac_path],
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        ac_ids_in_violations = [v["ac_id"] for v in violations]
        self.assertIn(
            ac_id,
            ac_ids_in_violations,
            "A changed done AC with a failing covers test must be reported. "
            "check_changed_done_acs must run the actual test via verify_done_eligible, "
            "not just check tag presence (a failing tag is still a violation). "
            f"Got violations: {violations}",
        )

    def test_ac1_violation_dict_has_ac_id_and_reason_keys(self) -> None:
        # covers: BO-2500b-3
        """Each violation dict returned by check_changed_done_acs must have
        'ac_id' (str) and 'reason' (non-empty str) keys.

        Consistent with the violation shape required by check_staged_done_proofs
        and check_all_done_acs (same consumer contract across all three functions).
        """
        ac_id = "BO-B3-DICT-SHAPE"
        ac_path = _write_ac(self.ac_root, ac_id, work_status="done")
        # No covers tag — must produce a violation.

        violations = check_changed_done_acs(
            [ac_path],
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertTrue(
            len(violations) > 0,
            "Expected at least one violation from a done AC with no covers test.",
        )
        violation = violations[0]
        self.assertIn("ac_id", violation, "Each violation must have an 'ac_id' key.")
        self.assertIn("reason", violation, "Each violation must have a 'reason' key.")
        self.assertTrue(
            isinstance(violation["reason"], str) and len(violation["reason"]) > 0,
            f"The 'reason' value must be a non-empty string. Got: {violation['reason']!r}",
        )

    def test_ac1_empty_changed_list_returns_no_violations(self) -> None:
        # covers: BO-2500b-3
        """An empty changed_yaml_paths list must return an empty violations list.

        When git diff finds no changed AC yamls (e.g. the PR only touched .py files),
        check_changed_done_acs must return [] without scanning ac_root.
        Pre-existing done ACs in ac_root must NOT be evaluated.
        """
        # Pre-existing done AC in ac_root — must NOT be evaluated when list is empty.
        _write_ac(self.ac_root, "BO-B3-EMPTY-PREEXIST", work_status="done")

        violations = check_changed_done_acs(
            [],  # empty changed list
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertEqual(
            violations,
            [],
            "An empty changed_yaml_paths list must return [] (no violations). "
            "check_changed_done_acs must not scan ac_root when no paths are provided. "
            f"Got: {violations}",
        )


# ---------------------------------------------------------------------------
# TestCliChangedMode — CLI mode acceptance tests
# ---------------------------------------------------------------------------


class TestCliChangedMode(unittest.TestCase):
    """BO-2500b-3: main() must accept --mode ci-changed with --base <ref>."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.ac_root.mkdir(parents=True, exist_ok=True)
        self.test_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac1_cli_mode_ci_changed_is_accepted(self) -> None:
        # covers: BO-2500b-3
        """The CLI must accept --mode ci-changed without an argparse error (exit 2).

        Currently, _build_parser() only accepts 'precommit' and 'ci'. The coder
        must extend the choices list to include 'ci-changed'.

        --base HEAD is used so that git diff HEAD...HEAD produces an empty diff,
        meaning no AC yamls are changed, check_changed_done_acs is called with [],
        and the exit code is 0. The test asserts it is NOT 2 (argparse rejection).
        """
        proc = subprocess.run(
            [
                _PYTHON_EXE,
                str(_COMMIT_GUARDIAN_DIR / "check_done_proof.py"),
                "--mode", "ci-changed",
                "--ac-root", str(self.ac_root),
                "--test-root", str(self.test_root),
                "--base", "HEAD",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(_REPO_ROOT),  # run from repo root so git diff works
        )
        self.assertNotEqual(
            proc.returncode,
            2,
            f"--mode ci-changed must be accepted by the argparse CLI. "
            f"Return code 2 means argparse rejected it as 'invalid choice'. "
            f"To fix: add 'ci-changed' to the choices in _build_parser(). "
            f"stderr: {proc.stderr!r}",
        )

    def test_ac1_cli_mode_ci_changed_base_argument_accepted(self) -> None:
        # covers: BO-2500b-3
        """The CLI must accept --base <ref> alongside --mode ci-changed.

        After --mode ci-changed is implemented, --base must also be accepted.
        Currently --base is not in the parser; the coder must add it.
        """
        proc = subprocess.run(
            [
                _PYTHON_EXE,
                str(_COMMIT_GUARDIAN_DIR / "check_done_proof.py"),
                "--mode", "ci-changed",
                "--base", "HEAD",
                "--ac-root", str(self.ac_root),
                "--test-root", str(self.test_root),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(_REPO_ROOT),
        )
        # Argparse exits 2 for unrecognised arguments or invalid choices.
        # After implementation, this invocation must not exit with code 2.
        self.assertNotEqual(
            proc.returncode,
            2,
            f"--base must be accepted as a CLI argument in ci-changed mode. "
            f"Return code 2 means argparse rejected '--base' or '--mode ci-changed'. "
            f"To fix: add parser.add_argument('--base', ...) to _build_parser(). "
            f"stderr: {proc.stderr!r}",
        )

    def test_ac1_cli_mode_ci_changed_exits_0_on_empty_diff(self) -> None:
        # covers: BO-2500b-3
        """--mode ci-changed with --base HEAD must exit 0 when the diff is empty.

        --base HEAD causes git diff HEAD...HEAD = empty diff → no changed AC yamls
        → check_changed_done_acs([]) → no violations → exit 0.

        This test verifies the full end-to-end CLI path once --mode ci-changed is
        implemented: the mode is accepted, git diff is invoked, the result is
        correctly wired through check_changed_done_acs, and exit 0 is returned.
        """
        proc = subprocess.run(
            [
                _PYTHON_EXE,
                str(_COMMIT_GUARDIAN_DIR / "check_done_proof.py"),
                "--mode", "ci-changed",
                "--base", "HEAD",
                "--ac-root", str(self.ac_root),
                "--test-root", str(self.test_root),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(_REPO_ROOT),
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"--mode ci-changed with --base HEAD (empty diff) must exit 0 "
            f"(no violations when no changed ACs). "
            f"Got returncode={proc.returncode}. "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}",
        )


# ---------------------------------------------------------------------------
# TestCiYmlStructure — structural tests on .github/workflows/ci.yml
# ---------------------------------------------------------------------------


class TestCiYmlStructure(unittest.TestCase):
    """BO-2500b-3: The done-proof CI job must be a required, non-optional gate
    using the diff-scoped ci-changed mode.

    Tests parse the REAL ci.yml (not a hand-typed copy).
    """

    @classmethod
    def _load_ci_yml(cls) -> dict:
        """Load and parse the real ci.yml file.

        Returns:
            Parsed dict from the ci.yml YAML.
        """
        ci_yml_path = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
        with open(ci_yml_path, encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    @classmethod
    def _get_done_proof_job(cls) -> dict:
        """Return the done-proof job definition from ci.yml.

        Returns:
            Dict for the 'done-proof' job entry (may be empty if absent).
        """
        data = cls._load_ci_yml()
        return data.get("jobs", {}).get("done-proof", {})

    def test_ac1_done_proof_job_has_no_continue_on_error(self) -> None:
        # covers: BO-2500b-3
        """The done-proof job must NOT have continue-on-error: true.

        Currently: continue-on-error: true makes it an informational (non-blocking)
        job. After implementation: continue-on-error must be absent (or false) so
        that the job is a REQUIRED blocking gate.

        This test is RED now (continue-on-error: true is present in ci.yml).
        To make it green: remove the 'continue-on-error: true' line from the
        done-proof job in .github/workflows/ci.yml.
        """
        job = self._get_done_proof_job()
        continue_on_error = job.get("continue-on-error")
        self.assertFalse(
            continue_on_error,
            f"The done-proof CI job must NOT have continue-on-error: true. "
            f"Current value: {continue_on_error!r}. "
            f"Remove 'continue-on-error: true' from .github/workflows/ci.yml "
            f"to make the done-proof gate a required blocking check (BO-2500b-3).",
        )

    def test_ac1_done_proof_job_invokes_ci_changed_mode(self) -> None:
        # covers: BO-2500b-3
        """The done-proof job step must invoke check_done_proof.py with --mode ci-changed.

        Currently: --mode ci (whole-store scan, fails on legacy debt).
        After implementation: --mode ci-changed (PR-scoped, safe to require).

        Parses the REAL ci.yml for this assertion (never a hand-typed copy).

        This test is RED now ('--mode ci-changed' does not appear in ci.yml).
        To make it green: update the 'Run proof-of-done check' step in
        .github/workflows/ci.yml to use:
            python scripts/commit_guardian/check_done_proof.py --mode ci-changed ...
        """
        ci_yml_path = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
        ci_text = ci_yml_path.read_text(encoding="utf-8")
        self.assertIn(
            "--mode ci-changed",
            ci_text,
            "The done-proof CI job step must invoke check_done_proof.py with "
            "'--mode ci-changed' (diff-scoped mode). "
            "Currently the step uses '--mode ci' (whole-store scan). "
            "Update .github/workflows/ci.yml to use '--mode ci-changed' so that "
            "only ACs changed in the PR are evaluated (BO-2500b-3).",
        )

    def test_ac1_done_proof_job_step_passes_base_ref(self) -> None:
        # covers: BO-2500b-3
        """The done-proof job step must pass a --base argument for diff scoping.

        The ci-changed mode computes changed AC yamls via:
            git diff --name-only <base>...HEAD
        The step must specify the base ref so the diff is scoped to the PR.
        Expected: --base origin/${{ github.base_ref }} or equivalent.

        This test is RED now ('--base' does not appear in the done-proof job).
        Parses the REAL ci.yml for this assertion.
        """
        ci_yml_path = _REPO_ROOT / ".github" / "workflows" / "ci.yml"
        ci_text = ci_yml_path.read_text(encoding="utf-8")

        # '--base' must appear somewhere in ci.yml after the implementation.
        # (The typecheck job uses "origin/${{ github.base_ref }}" inline in git
        # commands, not as '--base'; '--base' is specific to check_done_proof.py.)
        self.assertIn(
            "--base",
            ci_text,
            "The done-proof CI step must pass a '--base' argument alongside "
            "'--mode ci-changed' so the git diff is scoped to the PR's changed files. "
            "Expected form: --base origin/${{ github.base_ref }} or --base origin/main. "
            "Update .github/workflows/ci.yml (BO-2500b-3).",
        )

    def test_ac1_done_proof_job_fetches_git_history_for_diff(self) -> None:
        # covers: BO-2500b-3
        """The done-proof job checkout step must fetch enough history for git diff.

        The ci-changed mode runs `git diff --name-only <base>...HEAD` which requires
        the base ref to be reachable. The checkout step must use fetch-depth: 0
        (or fetch the base ref explicitly) so the diff is not empty due to a
        shallow clone.

        This test is RED now (the done-proof job checkout does not fetch history).
        To make it green: add fetch-depth: 0 to the actions/checkout step in
        the done-proof job, or add a fetch step before the diff command.
        """
        job = self._get_done_proof_job()
        steps = job.get("steps", [])

        # Check for fetch-depth: 0 in the checkout step, OR a separate fetch step.
        has_full_history = False
        for step in steps:
            # Checkout with full history
            uses = step.get("uses", "")
            wiith = step.get("with", {}) or {}
            if "checkout" in uses and wiith.get("fetch-depth") == 0:
                has_full_history = True
                break
            # Explicit git fetch step
            run = step.get("run", "")
            if "git fetch" in run and "base_ref" in run:
                has_full_history = True
                break

        self.assertTrue(
            has_full_history,
            "The done-proof job must fetch enough git history for git diff to work. "
            "Add 'fetch-depth: 0' to the actions/checkout step, or add an explicit "
            "'git fetch' step that retrieves the base branch ref. "
            "Without this, git diff HEAD...HEAD produces an empty result even when "
            "AC yamls were changed in the PR (BO-2500b-3).",
        )


if __name__ == "__main__":
    unittest.main()
