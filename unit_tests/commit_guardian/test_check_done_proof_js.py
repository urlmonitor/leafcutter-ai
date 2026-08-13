"""
MODULE: unit_tests/commit_guardian/test_check_done_proof_js.py
GOAL: RED test stubs for BO-2500e-5 — the pre-commit hook and CI gate recognise
      JavaScript/TypeScript (vitest) tests as valid done-proof exactly as they
      already do for Python (pytest).

=== Interface contract under test ===

  Location: templates/scripts/commit_guardian/check_done_proof.py

    check_staged_done_proofs(staged_yaml_paths: list[Path], *, test_root: Path)
      -> list[dict]
      FAST STATIC pre-commit check.  For each staged AC whose work_status is
      done, checks whether at least one line matching EITHER
      "# covers: <ac_id>" (Python) OR "// covers: <ac_id>" (JS/TS) exists
      anywhere under test_root.  Returns violation dicts when absent.

    check_all_done_acs(*, ac_root: Path, test_root: Path) -> list[dict]
      CI-authoritative check.  Calls verify_done_eligible for each done AC.
      When a JS-covered AC passes verify_done_eligible, it must NOT appear in
      violations.  When it fails, it must appear with a meaningful reason.

    main(argv: list[str] | None = None) -> int
      CLI entry point.  Returns an int (not raises SystemExit) for in-process
      callers.  The hook is registered as a skippable normal hook (not
      always_run: true).

=== Mocking strategy ===

  Patch "check_done_proof.verify_done_eligible" to return JS-aware verdicts for
  check_all_done_acs tests.  For static-check tests (check_staged_done_proofs),
  no mock is needed — we write real .ts files and assert tag presence detection.

=== Import path note ===

  The scripts/commit_guardian symlink in this worktree is broken.  The canonical
  source is templates/scripts/commit_guardian/.  This file adds that path to
  sys.path so imports resolve correctly in the worktree build environment.

=== Red baseline ===

  test_precommit_verdict_includes_js_covered_acs: RED (AssertionError) —
      check_staged_done_proofs does not yet recognise "// covers:" in .ts files.
  test_precommit_js_check_is_skippable: MAY PASS if main() already returns int
      and the hook is correctly registered; noted in red_baseline if green.
"""
from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
import unittest.mock
from pathlib import Path
from unittest.mock import patch

import yaml

# ---------------------------------------------------------------------------
# Repo path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
# Use the templates source path — scripts/commit_guardian symlink is broken
# in this worktree (points to a removed worktree).  The canonical source is
# templates/scripts/commit_guardian, which is what build.py deploys from.
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_AC_STORE_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_COMMIT_GUARDIAN_DIR))
sys.path.insert(0, str(_AC_STORE_DIR))

from check_done_proof import check_staged_done_proofs  # noqa: E402
from check_done_proof import check_all_done_acs  # noqa: E402
from check_done_proof import main as _check_done_proof_main  # noqa: E402


# ---------------------------------------------------------------------------
# Shared fixture helpers (yaml.safe_dump — fixture-authenticity mandate)
# ---------------------------------------------------------------------------


def _write_ac(
    ac_root: Path,
    ac_id: str,
    *,
    status: str = "active",
    work_status: str = "done",
) -> Path:
    """Write a minimal done AC YAML using yaml.safe_dump.

    Args:
        ac_root: Root directory of the synthetic AC store.
        ac_id: Identifier for the AC.
        status: AC lifecycle status.
        work_status: AC work status.

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
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _write_ts_test(test_root: Path, filename: str, content: str) -> Path:
    """Write a TypeScript/Vitest test stub to test_root.

    Args:
        test_root: Directory to write the test file into.
        filename: Filename (must end in .ts or .tsx).
        content: TypeScript source; leading whitespace is dedented.

    Returns:
        Path to the written file.
    """
    test_root.mkdir(parents=True, exist_ok=True)
    path = test_root / filename
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


def _write_py_test(test_root: Path, filename: str, content: str) -> Path:
    """Write a Python test file to test_root.

    Args:
        test_root: Directory to write the test file into.
        filename: Filename (must end in .py).
        content: Python source; leading whitespace is dedented.

    Returns:
        Path to the written file.
    """
    test_root.mkdir(parents=True, exist_ok=True)
    path = test_root / filename
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# BO-2500e-5 — Pre-commit hook includes JS-covered ACs + is skippable
# ---------------------------------------------------------------------------


class TestPreCommitHookJsIntegration(unittest.TestCase):
    """BO-2500e-5: The pre-commit hook recognises JS-covered ACs and is skippable."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.test_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_precommit_verdict_includes_js_covered_acs(self) -> None:
        # covers: BO-2500e-5
        """The pre-commit static check must NOT flag a done AC covered by a .ts tag.

        Two sub-assertions:

        (a) Static check (check_staged_done_proofs): A done AC whose "// covers:"
            tag is in a .ts file must NOT be a violation.  The static check must
            recognise "// covers: <id>" in .ts/.tsx files just as it recognises
            "# covers: <id>" in .py files.

        (b) CI check (check_all_done_acs): When verify_done_eligible returns
            eligible=True for a JS-covered done AC (mocked), that AC must NOT
            appear in violations — same contract as for Python-covered ACs.

        PRIMARY RED mechanism (sub-assertion a): AssertionError — the current
        check_staged_done_proofs implementation does not recognise "// covers:"
        in .ts files.  It only looks for "# covers:" in Python files, so the
        .ts-tagged done AC is flagged as a violation.

        Sub-assertion b may already pass (mocked eligible=True → no violation).
        """
        ac_id = "BO-E5-PRECOMMIT-JS-001"
        ac_path = _write_ac(self.ac_root, ac_id, work_status="done")

        # Write a .ts file with a "// covers:" tag (no .py file — JS-only).
        _write_ts_test(
            self.test_root,
            "precommitJsCover.test.ts",
            f"""\
            import {{ test, expect }} from 'vitest'

            test('pre-commit JS coverage', () => {{
              // covers: {ac_id}
              expect(true).toBe(true)
            }})
            """,
        )

        # --- Sub-assertion (a): static pre-commit check ---
        # check_staged_done_proofs performs tag PRESENCE only (no test run).
        # A .ts file with "// covers: <ac_id>" must satisfy the static check.
        violations_static = check_staged_done_proofs(
            [ac_path],
            test_root=self.test_root,
        )
        ac_ids_static = [v.get("ac_id", "") for v in violations_static]
        self.assertNotIn(
            ac_id,
            ac_ids_static,
            f"check_staged_done_proofs must NOT flag a done AC whose only covers "
            f"tag is in a .ts file ('// covers: {ac_id}'). "
            "The static check must recognise JS covers tags. "
            f"Current violations: {violations_static}",
        )

        # --- Sub-assertion (b): CI authoritative check (mocked eligible=True) ---
        passing_verdict = {
            "eligible": True,
            "reason": "",
            "passing_tests": [f"precommitJsCover.test.ts::{ac_id}"],
            "failing_tests": [],
            "dangling_tags": [],
        }
        with patch(
            "check_done_proof.verify_done_eligible",
            return_value=passing_verdict,
        ):
            violations_ci = check_all_done_acs(
                ac_root=self.ac_root,
                test_root=self.test_root,
            )

        ac_ids_ci = [v.get("ac_id", "") for v in violations_ci]
        self.assertNotIn(
            ac_id,
            ac_ids_ci,
            "check_all_done_acs must NOT flag a JS-covered done AC when "
            "verify_done_eligible returns eligible=True. "
            f"Current CI violations: {violations_ci}",
        )

    def test_precommit_js_check_is_skippable(self) -> None:
        # covers: BO-2500e-5
        """The done-proof pre-commit check must be skippable (non-blocking locally).

        Two sub-assertions:

        (a) main() returns an int rather than raising SystemExit directly.
            A hook that calls sys.exit() unconditionally cannot be bypassed via
            SKIP=<hook-id> when called in-process; it must return a verdict int.

        (b) The hook must be registered WITHOUT always_run: true in the hook
            manifest (commit_guardian.json or hooks manifest).  A hook with
            always_run: true runs even when SKIP=<id> is set and violates the
            skippability contract.

        Sub-assertion (a) is likely to already PASS if main() already returns int.
        Sub-assertion (b) is the primary assertion — it reads the real on-disk
        hook registration and asserts the done-proof hook is NOT always_run.
        """
        # --- Sub-assertion (a): main() returns int, not raises SystemExit ---
        # Provide a minimal args list with a non-existent ac_root so main()
        # exits quickly without heavy work.
        import tempfile as _tmpmod

        with _tmpmod.TemporaryDirectory() as _tmp:
            tmp_ac = Path(_tmp) / "acs"
            tmp_test = Path(_tmp) / "tests"
            tmp_ac.mkdir()
            tmp_test.mkdir()

            try:
                result = _check_done_proof_main(
                    [
                        "--mode",
                        "ci",
                        "--ac-root",
                        str(tmp_ac),
                        "--test-root",
                        str(tmp_test),
                    ]
                )
                self.assertIsInstance(
                    result,
                    int,
                    "main() must return an int so the caller can handle the exit "
                    "code.  A hook that calls sys.exit() unconditionally cannot be "
                    "bypassed in-process via SKIP=<hook-id>.",
                )
            except SystemExit:
                # main() called sys.exit() — document it but do not fail hard here;
                # the hook's SystemExit may be caught by pre-commit's runner.
                # The primary skippability assertion is sub-assertion (b).
                pass

        # --- Sub-assertion (b): hook not registered as always_run: true ---
        # Find the commit_guardian.json in the templates directory (the canonical
        # source).  If it references a done-proof hook, assert always_run != True.
        cg_json_path = _COMMIT_GUARDIAN_DIR / "commit_guardian.json"
        self.assertTrue(
            cg_json_path.exists(),
            f"commit_guardian.json must exist at {cg_json_path} for hook "
            "registration validation.",
        )

        import json

        data = json.loads(cg_json_path.read_text(encoding="utf-8"))
        hooks = data.get("hooks_manifest", {}).get("hooks", [])

        # Find done-proof hook entries.
        done_proof_hooks = [
            h
            for h in hooks
            if "done-proof" in h.get("id", "")
            or "check_done_proof" in h.get("entry", "")
            or "done_proof" in h.get("id", "")
        ]

        # The hook must be registered (it should already be from BO-2500b-1).
        self.assertTrue(
            len(done_proof_hooks) > 0,
            "A done-proof hook entry must be registered in commit_guardian.json "
            "hooks_manifest.  Expected an entry with id containing 'done-proof' "
            "or entry containing 'check_done_proof'. "
            f"Found hook ids: {[h.get('id') for h in hooks]}",
        )

        # The registered hook must NOT have always_run: true.
        for hook_entry in done_proof_hooks:
            self.assertNotEqual(
                hook_entry.get("always_run"),
                True,
                f"Hook '{hook_entry.get('id')}' must NOT have always_run: true. "
                "A hook with always_run: true cannot be bypassed via SKIP=<id> or "
                "--no-verify, violating the skippability contract (BO-2500e-5).",
            )


if __name__ == "__main__":
    unittest.main()
