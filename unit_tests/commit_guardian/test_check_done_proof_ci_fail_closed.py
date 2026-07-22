"""
MODULE: unit_tests/commit_guardian/test_check_done_proof_ci_fail_closed.py
GOAL: Fail-closed tests for DEFECT M-2 — check_done_proof.py in --mode ci exits
      0 (fail-open) when verify_done_eligible raises or returns a malformed
      verdict missing the 'eligible' key.

=== DEFECT M-2 (CI mode fails OPEN on checker error) ===

In templates/scripts/commit_guardian/check_done_proof.py:

    if __name__ == "__main__":
        try:
            sys.exit(main())
        except (OSError, ValueError, KeyError) as exc:
            print(f"...", file=sys.stderr)
            sys.exit(0)          # <-- exits 0 on KeyError

When running in --mode ci, the code path is:
    main() → check_all_done_acs() → verify_done_eligible() → verdict["eligible"]

If verify_done_eligible returns a dict without the 'eligible' key (e.g. due to
an upstream checker error), `verdict["eligible"]` raises KeyError.  This
KeyError propagates out of check_all_done_acs(), out of main(), and is caught
by the outer guard which calls sys.exit(0) — fail-OPEN.

The correct behavior is fail-CLOSED: any checker error in CI mode must cause
a non-zero exit so the PR is blocked pending human investigation.

=== Contract these tests enforce ===

  check_done_proof.main(['--mode', 'ci', ...]) when verify_done_eligible
  returns a malformed verdict (missing 'eligible'):

  MUST: return a non-zero exit code (1 or higher)
  MUST NOT: raise KeyError to the caller
  MUST NOT: return 0 (which would allow the PR to merge unchecked)

  The fail-closed requirement comes from BO-2500b-2: "CI is the authoritative
  backstop; a checker failure must not silently clear the gate."

=== Red baseline ===

  All tests are RED until python-coder fixes check_done_proof.py so that:
  - KeyError inside check_all_done_acs is caught within main() (not in the
    __main__ guard) and returns 1 instead of propagating.
  OR
  - The __main__ guard catches KeyError and calls sys.exit(1) not sys.exit(0).

  Current behavior: main() raises KeyError (because verdict["eligible"] fails),
  the test catches it via assertRaises, and then fails because main() should
  return a non-zero int, not raise at all.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
import unittest.mock
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

from check_done_proof import main  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_done_ac(ac_root: Path, ac_id: str) -> Path:
    """Write a minimal done AC YAML (yaml.safe_dump — mandate-compliant).

    Args:
        ac_root: Root of the synthetic AC store.
        ac_id: Identifier for the AC.

    Returns:
        Path to the written YAML file.
    """
    subdir = ac_root / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict = {
        "id": ac_id,
        "title": f"Synthetic done AC {ac_id}",
        "component": "build-orchestration",
        "level": "L2",
        "status": "active",
        "work_status": "done",  # done → CI mode will call verify_done_eligible
        "readiness": "approved",
        "priority": "medium",
        "estimated_complexity": "S",
        "depends_on": [],
        "amended_by": [],
        "covered_by": [],
        "implemented_by": [],
        "superseded_by": None,
    }
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# TestCheckDoneProofCiFailClosed — DEFECT M-2
# ---------------------------------------------------------------------------


class TestCheckDoneProofCiFailClosed(unittest.TestCase):
    """CI mode of check_done_proof must be fail-CLOSED on checker errors.

    DEFECT M-2: when verify_done_eligible returns a malformed verdict
    (missing 'eligible' key), main() must return non-zero, not raise KeyError
    which the __main__ guard converts to exit 0 (fail-open).
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.ac_root = root / "acs"
        self.test_root = root / "tests"
        self.test_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_m2_ci_mode_returns_nonzero_when_eligible_key_missing(self) -> None:
        # covers: BO-2500b-2
        """CI mode must return non-zero when verify_done_eligible returns a verdict
        missing the 'eligible' key (checker error / malformed verdict).

        DEFECT M-2: the current code path is:
          main() → check_all_done_acs() → verdict["eligible"]  ← KeyError
          KeyError propagates → __main__ guard → sys.exit(0)   ← fail-OPEN

        The contract: main() itself must handle the KeyError and return 1 (or
        higher), so the CI gate rejects the PR when a checker error occurs.

        When calling main() directly (not via __main__), the KeyError propagates
        from check_all_done_acs() to main() to the test — confirming DEFECT M-2.
        The test asserts main() returns non-zero, which is RED now because main()
        raises KeyError instead of returning.
        """
        _write_done_ac(self.ac_root, "BO-M2-FAIL-001")

        # Patch verify_done_eligible to return a malformed verdict (missing 'eligible').
        # This simulates a checker error / version mismatch where the oracle's
        # return contract is violated.
        malformed_verdict: dict = {
            "reason": "checker error — eligible key missing (simulated)",
            "passing_tests": [],
            "failing_tests": [],
            # NOTE: 'eligible' key is intentionally absent
        }

        with unittest.mock.patch(
            "check_done_proof.verify_done_eligible",
            return_value=malformed_verdict,
        ):
            try:
                result = main([
                    "--mode", "ci",
                    "--ac-root", str(self.ac_root),
                    "--test-root", str(self.test_root),
                ])
            except KeyError as exc:
                # DEFECT M-2 confirmed: main() raised KeyError instead of
                # returning a non-zero exit code. The __main__ guard would
                # silently convert this to sys.exit(0) (fail-open).
                self.fail(
                    f"DEFECT M-2: main() raised KeyError({exc!r}) instead of returning "
                    "a non-zero exit code. In CLI usage (via __main__), this KeyError "
                    "is caught by the outer guard and converted to sys.exit(0) — "
                    "fail-OPEN. The CI mode must be fail-CLOSED: catch the KeyError "
                    "inside main() (or check_all_done_acs) and return 1 so that a "
                    "checker error blocks the PR rather than silently clearing it."
                )

        self.assertNotEqual(
            result,
            0,
            f"DEFECT M-2: main(--mode ci) returned 0 when verify_done_eligible "
            "returned a malformed verdict (missing 'eligible' key). "
            "CI mode must return non-zero (fail-CLOSED) so that checker errors "
            "block the PR rather than silently passing (BO-2500b-2).",
        )

    def test_m2_ci_mode_returns_nonzero_when_eligible_key_is_none(self) -> None:
        # covers: BO-2500b-2
        """CI mode must return non-zero when eligible is None (falsy but present).

        A verdict with eligible=None is a checker failure that must be treated
        as ineligible — the CI gate must not let it pass.
        """
        _write_done_ac(self.ac_root, "BO-M2-FAIL-002")

        none_eligible_verdict: dict = {
            "eligible": None,  # None is falsy; must not pass the gate
            "reason": "checker returned None for eligible",
            "passing_tests": [],
            "failing_tests": [],
            "dangling_tags": [],
        }

        with unittest.mock.patch(
            "check_done_proof.verify_done_eligible",
            return_value=none_eligible_verdict,
        ):
            result = main([
                "--mode", "ci",
                "--ac-root", str(self.ac_root),
                "--test-root", str(self.test_root),
            ])

        self.assertNotEqual(
            result,
            0,
            "CI mode must return non-zero when eligible is None (falsy) — "
            "a None verdict is a checker error, not a pass (BO-2500b-2).",
        )

    def test_m2_ci_mode_returns_nonzero_when_done_ac_lacks_test_coverage(self) -> None:
        # covers: BO-2500b-2
        """CI mode must return non-zero when a done AC has no covering test.

        This is the standard violation path: an AC is marked done but no test
        with a matching '# covers:' tag exists.  The real verify_done_eligible
        call (no mocking) must detect this and cause main() to return 1.
        """
        ac_id = "BO-M2-REAL-001"
        _write_done_ac(self.ac_root, ac_id)
        # No test file with '# covers: BO-M2-REAL-001' exists → coverage missing

        result = main([
            "--mode", "ci",
            "--ac-root", str(self.ac_root),
            "--test-root", str(self.test_root),
        ])

        self.assertEqual(
            result,
            1,
            "CI mode must return 1 when a done AC has no covering test. "
            f"Got return code {result}. "
            "This is the standard violation path that BO-2500b-2 enforces.",
        )

    def test_m2_ci_mode_returns_0_when_all_done_acs_are_eligible(self) -> None:
        # covers: BO-2500b-2
        """CI mode must return 0 when all done ACs have passing tests.

        Regression test: the M-2 fix must not break the happy path.
        When all done ACs pass verify_done_eligible, CI mode returns 0.
        """
        ac_id = "BO-M2-PASS-001"
        _write_done_ac(self.ac_root, ac_id)

        passing_verdict: dict = {
            "eligible": True,
            "reason": "",
            "passing_tests": [f"unit_tests/test_{ac_id}.py::test_ok"],
            "failing_tests": [],
            "dangling_tags": [],
        }

        with unittest.mock.patch(
            "check_done_proof.verify_done_eligible",
            return_value=passing_verdict,
        ):
            result = main([
                "--mode", "ci",
                "--ac-root", str(self.ac_root),
                "--test-root", str(self.test_root),
            ])

        self.assertEqual(
            result,
            0,
            "CI mode must return 0 when all done ACs pass verify_done_eligible. "
            f"Got return code {result}.",
        )


if __name__ == "__main__":
    unittest.main()
