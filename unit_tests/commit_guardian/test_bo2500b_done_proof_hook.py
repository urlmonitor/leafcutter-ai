"""
MODULE: unit_tests/commit_guardian/test_bo2500b_done_proof_hook.py
GOAL: RED test stubs for BO-2500b-1, BO-2500b-1-i, and the CI-mode function
      in scripts/commit_guardian/check_done_proof.py.
BUSINESS CONTEXT: BO-2500b gates mechanical proof-of-done at two layers:
    (1) a fast static pre-commit hook that checks covers-tag PRESENCE for ACs
    newly staged as done, and (2) an authoritative CI-mode check that calls
    verify_done_eligible() on every done AC and requires every covers-linked
    test to actually pass.  BO-2500b-1-i ensures that skipping the pre-commit
    hook locally (via --no-verify or a worktree without hook config) does not
    let unproven work reach the protected branch.
ARCHITECTURE: Tests import from scripts/commit_guardian/check_done_proof.py
    (does not yet exist — ImportError is the intended red state).  AC YAML
    fixtures are written with yaml.safe_dump (BO-2500c mandate).  Test-tree
    fixtures are real .py files.  commit_guardian.json is parsed from the
    REAL on-disk file.  CLI tests run mark_ac_done.py via subprocess.

=== Interface contract under test (to be implemented by python-coder) ===

  Location: scripts/commit_guardian/check_done_proof.py

    check_staged_done_proofs(
        staged_yaml_paths: list[Path],
        *,
        test_root: Path,
    ) -> list[dict]

    Fast, STATIC pre-commit check.  For each AC YAML path in
    staged_yaml_paths whose ``work_status`` field is ``done``, checks whether
    at least one line matching ``# covers: <ac_id>`` exists anywhere under
    test_root.  Does NOT run pytest (latency budget for pre-commit).
    Returns a list of violation dicts: {"ac_id": str, "reason": str}.

    check_all_done_acs(
        *,
        ac_root: Path,
        test_root: Path,
    ) -> list[dict]

    CI-authoritative check.  Scans ac_root for all ACs whose work_status is
    ``done``, calls verify_done_eligible() from done_proof.py for each, and
    returns a list of violation dicts: {"ac_id": str, "reason": str}.

    main(argv: list[str] | None = None) -> int

    CLI entry point.  Recognised flags include at least --mode {precommit,ci}
    (or --ci as a shorthand).  Exits 0 when no violations; non-zero otherwise.

  Location: scripts/ac_store/mark_ac_done.py — CLI extended by coder:

    _build_parser() must gain --test-root DIR so the CLI enforces the
    coverage gate when called with that flag.  main() must wire --test-root
    to mark_ac_done(..., test_root=Path(args.test_root)) when supplied.

=== Fixture authenticity mandate (dogfood BO-2500c) ===

  All AC YAML fixtures are written with yaml.safe_dump (not hand-typed YAML
  strings).  All test fixtures are real .py files with genuine test bodies.
  commit_guardian.json assertions parse the REAL on-disk file, never a copy.
  No mocking of pass/fail signals.

=== Red baseline ===

  All tests are RED until python-coder:
    - Creates scripts/commit_guardian/check_done_proof.py with
      check_staged_done_proofs() and check_all_done_acs().
    - Registers the hook in scripts/commit_guardian/commit_guardian.json.
    - Adds --test-root to _build_parser() in scripts/ac_store/mark_ac_done.py
      and wires it in main().
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Repo path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "scripts" / "commit_guardian"
_AC_STORE_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_COMMIT_GUARDIAN_DIR))
sys.path.insert(0, str(_AC_STORE_DIR))

# These imports FAIL with ImportError until python-coder creates
# scripts/commit_guardian/check_done_proof.py.
# That ImportError IS the intended red state — it confirms the production
# code does not yet exist.
from check_done_proof import check_all_done_acs  # noqa: E402
from check_done_proof import check_staged_done_proofs  # noqa: E402

# ---------------------------------------------------------------------------
# Shared fixture helpers (same pattern as test_bo2500a_done_proof.py)
# ---------------------------------------------------------------------------

_PYTHON_EXE = sys.executable


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
        status: AC lifecycle status ("active", "deprecated", etc.).
        work_status: AC work status ("todo", "done", etc.).

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
    # Mandate: use yaml.safe_dump, not a hand-typed YAML literal.
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
# BO-2500b-1 — Pre-commit hook core: check_staged_done_proofs()
# ---------------------------------------------------------------------------


class TestPreCommitHookCore(unittest.TestCase):
    """BO-2500b-1: Fast static pre-commit hook checks covers-tag PRESENCE."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.test_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac_done_without_covers_tag_is_a_violation(self) -> None:
        # covers: BO-2500b-1
        """An AC staged as done with no covers tag in test_root must produce a violation.

        check_staged_done_proofs must:
        - Read each staged YAML path and extract work_status
        - For those with work_status: done, scan test_root for '# covers: <ac_id>'
        - Return a violation dict when no tag is found anywhere in test_root
        """
        ac_id = "BO-B1-TEST-NOTAG"
        ac_path = _write_ac(self.ac_root, ac_id, work_status="done")
        # test_root is intentionally empty — no covers tag exists

        violations = check_staged_done_proofs(
            [ac_path],
            test_root=self.test_root,
        )

        self.assertTrue(
            len(violations) > 0,
            "An AC staged as done with no covers tag must produce at least one violation.",
        )
        ac_ids_in_violations = [v["ac_id"] for v in violations]
        self.assertIn(
            ac_id,
            ac_ids_in_violations,
            f"The violation must name the offending AC id '{ac_id}'.",
        )

    def test_ac_done_with_covers_tag_present_is_not_a_violation(self) -> None:
        # covers: BO-2500b-1
        """An AC staged as done WITH a covers tag in test_root must NOT be a violation.

        The check is STATIC (tag presence only), not a pytest run.
        A covers tag in a test file is sufficient proof for the pre-commit gate.
        """
        ac_id = "BO-B1-TEST-HASTAG"
        ac_path = _write_ac(self.ac_root, ac_id, work_status="done")
        _write_test_file(
            self.test_root,
            "test_covers_present.py",
            f"""\
            def test_something():
                # covers: {ac_id}
                pass
            """,
        )

        violations = check_staged_done_proofs(
            [ac_path],
            test_root=self.test_root,
        )

        ac_ids_in_violations = [v["ac_id"] for v in violations]
        self.assertNotIn(
            ac_id,
            ac_ids_in_violations,
            "An AC with a present covers tag must NOT be a pre-commit violation.",
        )

    def test_non_done_acs_are_ignored(self) -> None:
        # covers: BO-2500b-1
        """An AC staged as todo (not done) must NOT be checked or flagged.

        Bounded blast radius: only ACs newly set to done in this commit
        trigger the check.  ACs in other states are never evaluated.
        """
        ac_id = "BO-B1-TEST-TODO"
        ac_path = _write_ac(self.ac_root, ac_id, work_status="todo")
        # No covers tag exists — but it must not matter for a non-done AC

        violations = check_staged_done_proofs(
            [ac_path],
            test_root=self.test_root,
        )

        ac_ids_in_violations = [v["ac_id"] for v in violations]
        self.assertNotIn(
            ac_id,
            ac_ids_in_violations,
            "An AC staged as todo must NOT trigger a pre-commit violation.",
        )

    def test_violation_dict_contains_ac_id_and_reason(self) -> None:
        # covers: BO-2500b-1
        """Each violation dict must carry both 'ac_id' and 'reason' keys.

        The AC spec requires: 'on failure it must print the specific AC ids
        and reasons (missing/failing/non-passing linked test)'.
        """
        ac_id = "BO-B1-TEST-SHAPE"
        ac_path = _write_ac(self.ac_root, ac_id, work_status="done")

        violations = check_staged_done_proofs(
            [ac_path],
            test_root=self.test_root,
        )

        self.assertTrue(len(violations) > 0, "Expected at least one violation.")
        violation = violations[0]
        self.assertIn("ac_id", violation, "Each violation must have an 'ac_id' key.")
        self.assertIn("reason", violation, "Each violation must have a 'reason' key.")
        self.assertTrue(
            len(violation["reason"]) > 0,
            "The 'reason' value must be a non-empty string.",
        )

    def test_multiple_done_acs_each_checked_independently(self) -> None:
        # covers: BO-2500b-1
        """When multiple done ACs are staged, each is checked independently.

        One AC without a tag must produce a violation; one with a tag must not.
        """
        id_no_tag = "BO-B1-TEST-MULTI-NOTAG"
        id_with_tag = "BO-B1-TEST-MULTI-HASTAG"

        path_no_tag = _write_ac(self.ac_root, id_no_tag, work_status="done")
        path_with_tag = _write_ac(self.ac_root, id_with_tag, work_status="done")

        _write_test_file(
            self.test_root,
            "test_multi_covers.py",
            f"""\
            def test_covers_second():
                # covers: {id_with_tag}
                pass
            """,
        )

        violations = check_staged_done_proofs(
            [path_no_tag, path_with_tag],
            test_root=self.test_root,
        )

        ac_ids_in_violations = [v["ac_id"] for v in violations]
        self.assertIn(
            id_no_tag,
            ac_ids_in_violations,
            "The AC without a covers tag must produce a violation.",
        )
        self.assertNotIn(
            id_with_tag,
            ac_ids_in_violations,
            "The AC with a present covers tag must NOT produce a violation.",
        )


# ---------------------------------------------------------------------------
# BO-2500b-1 — Hook registration in commit_guardian.json
# ---------------------------------------------------------------------------


class TestPreCommitHookRegistration(unittest.TestCase):
    """BO-2500b-1: The pre-commit hook must be registered in commit_guardian.json.

    Assertions parse the REAL on-disk commit_guardian.json, not a copy.
    """

    def _load_commit_guardian(self) -> dict:
        """Return the parsed commit_guardian.json from the real repo path."""
        cg_path = _REPO_ROOT / "scripts" / "commit_guardian" / "commit_guardian.json"
        return json.loads(cg_path.read_text(encoding="utf-8"))

    def test_hook_config_key_exists_in_commit_guardian_json(self) -> None:
        # covers: BO-2500b-1
        """commit_guardian.json must contain a top-level config key for the
        proof-of-done hook (e.g. 'done_proof' or 'proof_of_done').

        To make this green, python-coder must add a top-level key
        (e.g. 'done_proof': {...}) to commit_guardian.json.
        """
        data = self._load_commit_guardian()
        candidate_keys = {"done_proof", "proof_of_done", "check_done_proof"}
        present_keys = set(data.keys()) & candidate_keys

        self.assertTrue(
            len(present_keys) > 0,
            f"commit_guardian.json must contain a top-level config key for the "
            f"done-proof hook. Expected one of: {sorted(candidate_keys)}. "
            f"Found top-level keys: {sorted(data.keys())}.",
        )

    def test_hook_manifest_entry_exists_for_done_proof(self) -> None:
        # covers: BO-2500b-1
        """hooks_manifest.hooks must contain an entry for the done-proof hook.

        To make this green, python-coder must append an entry with an id
        containing 'done-proof' or 'proof-of-done' to the hooks array.
        """
        data = self._load_commit_guardian()
        hooks = data.get("hooks_manifest", {}).get("hooks", [])
        hook_ids = [h.get("id", "") for h in hooks]

        matching = [
            hid
            for hid in hook_ids
            if "done-proof" in hid
            or "proof-of-done" in hid
            or "done_proof" in hid
        ]

        self.assertTrue(
            len(matching) > 0,
            f"hooks_manifest.hooks must contain an entry for the done-proof hook. "
            f"Current hook ids: {sorted(hook_ids)}",
        )

    def test_hook_manifest_entry_references_check_done_proof_py(self) -> None:
        # covers: BO-2500b-1
        """The hooks_manifest entry's 'entry' field must reference check_done_proof.py."""
        data = self._load_commit_guardian()
        hooks = data.get("hooks_manifest", {}).get("hooks", [])

        matching = [
            h
            for h in hooks
            if "check_done_proof" in h.get("entry", "")
            or "check_done_proof" in h.get("id", "")
        ]

        self.assertTrue(
            len(matching) > 0,
            "A hooks_manifest entry must reference check_done_proof.py in its 'entry' field.",
        )

    def test_hook_manifest_entry_is_skippable_not_always_run(self) -> None:
        # covers: BO-2500b-1
        """The done-proof hook entry must NOT have always_run: true.

        The AC mandates the hook is bypassable via SKIP=<hook-id> / --no-verify.
        always_run: true would prevent skipping and violate the skippability
        requirement.
        """
        data = self._load_commit_guardian()
        hooks = data.get("hooks_manifest", {}).get("hooks", [])

        # Find the done-proof hook entry
        done_proof_entries = [
            h
            for h in hooks
            if "done-proof" in h.get("id", "")
            or "check_done_proof" in h.get("entry", "")
        ]

        self.assertTrue(
            len(done_proof_entries) > 0,
            "done-proof hook entry must exist in hooks_manifest before skippability "
            "can be verified.  Add the entry first.",
        )

        for entry in done_proof_entries:
            self.assertNotEqual(
                entry.get("always_run"),
                True,
                f"Hook entry '{entry.get('id')}' must NOT have always_run: true — "
                "the hook must be bypassable via SKIP or --no-verify.",
            )


# ---------------------------------------------------------------------------
# BO-2500b-2 — CI-mode check: check_all_done_acs()
# ---------------------------------------------------------------------------


class TestCIModeCheck(unittest.TestCase):
    """BO-2500b-2: CI-mode uses verify_done_eligible on every done AC in scope."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.test_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ci_mode_flags_done_ac_with_no_covers_test(self) -> None:
        # covers: BO-2500b-2
        """CI-mode must flag a done AC with no covers-linked test in test_root.

        check_all_done_acs calls verify_done_eligible for each done AC.
        When verify_done_eligible returns eligible=False (no linked test),
        the result must include a violation.
        """
        ac_id = "BO-B2-TEST-NOCI"
        _write_ac(self.ac_root, ac_id, work_status="done")
        # No covers tag in test_root

        violations = check_all_done_acs(
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        ac_ids_in_violations = [v["ac_id"] for v in violations]
        self.assertIn(
            ac_id,
            ac_ids_in_violations,
            "CI-mode must flag a done AC with no passing covers test.",
        )

    def test_ci_mode_flags_done_ac_with_failing_covers_test(self) -> None:
        # covers: BO-2500b-2
        """CI-mode must flag a done AC whose covers test FAILS.

        The CI check is authoritative: it runs the real test via
        verify_done_eligible, which invokes pytest as a subprocess.
        A failing test must produce a violation even if the tag is present.
        """
        ac_id = "BO-B2-TEST-FAIL"
        _write_ac(self.ac_root, ac_id, work_status="done")
        _write_test_file(
            self.test_root,
            "test_failing_ci_cover.py",
            f"""\
            def test_covers_b2_fail():
                # covers: {ac_id}
                assert False, "intentional failure — CI must catch this"
            """,
        )

        violations = check_all_done_acs(
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        ac_ids_in_violations = [v["ac_id"] for v in violations]
        self.assertIn(
            ac_id,
            ac_ids_in_violations,
            "CI-mode must flag a done AC whose covers test fails.",
        )

    def test_ci_mode_does_not_flag_done_ac_with_passing_covers_test(self) -> None:
        # covers: BO-2500b-2
        """CI-mode must NOT flag a done AC whose covers test PASSES.

        When verify_done_eligible returns eligible=True, no violation is emitted.
        """
        ac_id = "BO-B2-TEST-PASS"
        _write_ac(self.ac_root, ac_id, work_status="done")
        _write_test_file(
            self.test_root,
            "test_passing_ci_cover.py",
            f"""\
            def test_covers_b2_pass():
                # covers: {ac_id}
                pass  # genuinely passes
            """,
        )

        violations = check_all_done_acs(
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        ac_ids_in_violations = [v["ac_id"] for v in violations]
        self.assertNotIn(
            ac_id,
            ac_ids_in_violations,
            "CI-mode must NOT flag a done AC whose covers test passes.",
        )

    def test_ci_mode_ignores_non_done_acs(self) -> None:
        # covers: BO-2500b-2
        """CI-mode must not check or flag ACs that are not work_status: done."""
        ac_id_todo = "BO-B2-TEST-TODO"
        _write_ac(self.ac_root, ac_id_todo, work_status="todo")
        # No covers tag — but must be ignored because work_status != done

        violations = check_all_done_acs(
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        ac_ids_in_violations = [v["ac_id"] for v in violations]
        self.assertNotIn(
            ac_id_todo,
            ac_ids_in_violations,
            "CI-mode must NOT check or flag non-done ACs.",
        )

    def test_ci_mode_violation_dict_shape(self) -> None:
        # covers: BO-2500b-2
        """Each violation returned by check_all_done_acs must have 'ac_id' and 'reason' keys."""
        ac_id = "BO-B2-TEST-DICTSHAPE"
        _write_ac(self.ac_root, ac_id, work_status="done")

        violations = check_all_done_acs(
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        self.assertTrue(len(violations) > 0, "Expected at least one CI violation.")
        v = violations[0]
        self.assertIn("ac_id", v, "CI violation must have an 'ac_id' key.")
        self.assertIn("reason", v, "CI violation must have a 'reason' key.")
        self.assertTrue(len(v["reason"]) > 0, "The reason field must be non-empty.")

    def test_ci_mode_uses_verify_done_eligible_engine(self) -> None:
        # covers: BO-2500b-2
        """CI-mode verdict must be derived from verify_done_eligible, not a static scan.

        A done AC with a covers tag that FAILS the test must still be a violation.
        A static tag-presence check (like the pre-commit hook) would incorrectly
        pass this case.  CI must run the tests, not just check tag presence.
        """
        ac_id = "BO-B2-TEST-ENGINEUSE"
        _write_ac(self.ac_root, ac_id, work_status="done")
        # Tag IS present, but the test FAILS — CI must still flag it
        _write_test_file(
            self.test_root,
            "test_engine_use.py",
            f"""\
            def test_covers_engine_use():
                # covers: {ac_id}
                raise RuntimeError("this test always raises — CI must detect the failure")
            """,
        )

        violations = check_all_done_acs(
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        ac_ids_in_violations = [v["ac_id"] for v in violations]
        self.assertIn(
            ac_id,
            ac_ids_in_violations,
            "CI-mode must detect a failing covers test even when the tag is present. "
            "A static-only check would incorrectly pass this case — "
            "verify_done_eligible must be called.",
        )


# ---------------------------------------------------------------------------
# BO-2500b-1-i — CI catches work whose pre-commit check was skipped
# ---------------------------------------------------------------------------


class TestCICatchesSkippedPreCommit(unittest.TestCase):
    """BO-2500b-1-i: The CI gate catches work that bypassed the pre-commit hook."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.test_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ci_gate_catches_locally_skipped_proof(self) -> None:
        # covers: BO-2500b-1-i
        """A commit whose pre-commit check was skipped still fails the CI gate.

        Simulates the scenario: the developer ran 'git commit --no-verify',
        bypassing the proof-of-done pre-commit hook.  The AC was set to done
        without a covers test.  CI must still detect and block it because
        check_all_done_acs derives its verdict from the committed branch
        state via verify_done_eligible, not from pre-commit hook state.
        """
        ac_id = "BO-B1I-TEST-SKIP"
        # AC is done, no covers tag was written — pre-commit was bypassed
        _write_ac(self.ac_root, ac_id, work_status="done")

        # CI-mode runs regardless of whether the pre-commit hook executed
        violations = check_all_done_acs(
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        ac_ids_in_violations = [v["ac_id"] for v in violations]
        self.assertIn(
            ac_id,
            ac_ids_in_violations,
            "CI must catch a done AC with no covers proof, even when the "
            "pre-commit hook was locally skipped with --no-verify.",
        )

    def test_worktree_missing_hook_config_still_caught_by_ci(self) -> None:
        # covers: BO-2500b-1-i
        """A commit from a worktree without hook config is still caught by CI.

        In a worktree lacking .pre-commit-config.yaml, all pre-commit hooks
        are silently skipped (see project memory: worktree pre-commit gap).
        The CI check must catch the violation regardless, because its verdict
        is derived solely from verify_done_eligible(ac_root, test_root) on
        the committed branch state — no pre-commit state is involved.
        """
        ac_id = "BO-B1I-TEST-WORKTREE"
        # Written as done, no covers tag — as if produced in a hook-config-less worktree
        _write_ac(self.ac_root, ac_id, work_status="done")

        violations = check_all_done_acs(
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        ac_ids_in_violations = [v["ac_id"] for v in violations]
        self.assertIn(
            ac_id,
            ac_ids_in_violations,
            "CI must detect a done AC without covers proof regardless of "
            "whether the committing worktree had hook config.",
        )

    def test_ci_verdict_derived_from_committed_state_only(self) -> None:
        # covers: BO-2500b-1-i
        """When the committed state includes a passing covers test, CI accepts it.

        The CI verdict is derived only from ac_root + test_root (committed
        branch state).  It reads no pre-commit hook logs, no hook metadata,
        and no files outside these two roots.  This test verifies the
        function accepts committed-state proof, not that it reads hook state.
        """
        ac_id = "BO-B1I-TEST-COMMITTED"
        _write_ac(self.ac_root, ac_id, work_status="done")
        # A passing covers test exists in the committed tree
        _write_test_file(
            self.test_root,
            "test_committed_state.py",
            f"""\
            def test_covers_committed_state():
                # covers: {ac_id}
                pass  # genuinely passes — committed branch includes this
            """,
        )

        violations = check_all_done_acs(
            ac_root=self.ac_root,
            test_root=self.test_root,
        )

        ac_ids_in_violations = [v["ac_id"] for v in violations]
        self.assertNotIn(
            ac_id,
            ac_ids_in_violations,
            "When committed state includes a passing covers test, CI must not "
            "flag the AC — the verdict is based on committed state only.",
        )


# ---------------------------------------------------------------------------
# BO-2500b-1 — CLI: mark_ac_done gains --test-root
# ---------------------------------------------------------------------------


class TestMarkAcDoneCLI(unittest.TestCase):
    """CLI: mark_ac_done.py --test-root enforces the coverage gate end-to-end."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.test_root.mkdir(parents=True, exist_ok=True)
        self.ac_id = "BO-B-CLI-TEST"
        _write_ac(
            self.ac_root,
            self.ac_id,
            status="active",
            work_status="todo",
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_cli_help_lists_test_root_flag(self) -> None:
        # covers: BO-2500b-1
        """mark_ac_done.py --help must list --test-root as a recognised option.

        To make this green, _build_parser() in mark_ac_done.py must add:
            parser.add_argument('--test-root', metavar='DIR', ...)
        """
        script = _REPO_ROOT / "scripts" / "ac_store" / "mark_ac_done.py"
        proc = subprocess.run(
            [_PYTHON_EXE, str(script), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertIn(
            "--test-root",
            proc.stdout,
            "--test-root must appear in mark_ac_done.py --help output.",
        )

    def test_cli_exits_with_code_3_when_no_covers_test(self) -> None:
        # covers: BO-2500b-1
        """mark_ac_done --test-root exits 3 when coverage gate fails.

        With --test-root pointing at a directory with no covers tag, the
        gate must refuse with exit code 3 (coverage gate refusal, distinct
        from code 1 = lookup error, code 2 = inactive AC).
        """
        script = _REPO_ROOT / "scripts" / "ac_store" / "mark_ac_done.py"
        proc = subprocess.run(
            [
                _PYTHON_EXE,
                str(script),
                "--ac",
                self.ac_id,
                "--ac-root",
                str(self.ac_root),
                "--test-root",
                str(self.test_root),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(
            proc.returncode,
            3,
            f"mark_ac_done --test-root must exit 3 (coverage gate refusal) "
            f"when no covers test exists. "
            f"Got returncode={proc.returncode}. "
            f"stdout={proc.stdout!r} stderr={proc.stderr!r}",
        )

    def test_cli_refusal_output_names_ac_id(self) -> None:
        # covers: BO-2500b-1
        """When --test-root triggers a refusal, the output must name the AC id.

        The error message must be machine-readable (includes the AC id)
        so the developer knows which AC was refused.
        """
        script = _REPO_ROOT / "scripts" / "ac_store" / "mark_ac_done.py"
        proc = subprocess.run(
            [
                _PYTHON_EXE,
                str(script),
                "--ac",
                self.ac_id,
                "--ac-root",
                str(self.ac_root),
                "--test-root",
                str(self.test_root),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        combined = proc.stdout + proc.stderr
        self.assertIn(
            self.ac_id,
            combined,
            "The refusal output must name the AC id so the developer knows "
            "which AC was refused by the coverage gate.",
        )

    def test_cli_exits_zero_when_covers_test_passes(self) -> None:
        # covers: BO-2500b-1
        """mark_ac_done --test-root exits 0 when the covers test passes.

        When the AC is active, test_root contains a passing covers-tagged test,
        and verify_done_eligible returns eligible=True, the CLI must succeed
        (exit 0) and write work_status: done to the AC YAML.
        """
        _write_test_file(
            self.test_root,
            "test_cli_passing.py",
            f"""\
            def test_covers_cli_test():
                # covers: {self.ac_id}
                pass  # genuinely passes
            """,
        )
        script = _REPO_ROOT / "scripts" / "ac_store" / "mark_ac_done.py"
        proc = subprocess.run(
            [
                _PYTHON_EXE,
                str(script),
                "--ac",
                self.ac_id,
                "--ac-root",
                str(self.ac_root),
                "--test-root",
                str(self.test_root),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"mark_ac_done --test-root must exit 0 when the covers test passes. "
            f"stderr={proc.stderr!r}",
        )

    def test_cli_without_test_root_skips_coverage_gate(self) -> None:
        # covers: BO-2500b-1
        """mark_ac_done without --test-root must NOT enforce the coverage gate.

        Backward compatibility: the coverage gate is opt-in via --test-root.
        Without it, mark_ac_done must succeed (exit 0) even when no covers
        test exists (pre-existing behaviour must be preserved).
        """
        script = _REPO_ROOT / "scripts" / "ac_store" / "mark_ac_done.py"
        proc = subprocess.run(
            [
                _PYTHON_EXE,
                str(script),
                "--ac",
                self.ac_id,
                "--ac-root",
                str(self.ac_root),
                # No --test-root: coverage gate must NOT apply
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"mark_ac_done without --test-root must exit 0 (backward compat). "
            f"stderr={proc.stderr!r}",
        )


if __name__ == "__main__":
    unittest.main()
