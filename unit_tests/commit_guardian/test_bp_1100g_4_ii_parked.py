"""
MODULE: unit_tests/commit_guardian/test_bp_1100g_4_ii_parked.py
COVERS: BP-1100g-4-ii

Split-only sibling of test_bp_1100g_4_ii.py (GE-127a-1 size gate): the BO-4100a-1
amendment tests for PARKED work (status: deferred is passed over, status: blocked
is still refused). Same deployed-hook subprocess approach; helpers come from
_bp_1100g_4_ii_fixture.py.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bp_1100g_4_ii_fixture import (  # noqa: E402
    _DEPLOYED_HOOK,
    _SHARED_AC_ID,
    _SHARED_ANGLE,
    _build_ticket_fixture,
    _init_temp_git_project,
    _run_check,
)


class TestDeferredWorkWithAnUnclaimedPromiseIsPassedOverAndSaysSo(unittest.TestCase):
    """test_spec: test_deferred_work_with_an_unclaimed_promise_is_passed_over_and_says_so
    (angle: criterion). BO-4100a-1 amendment: parked work is not yet due."""

    def test_deferred_work_with_an_unclaimed_promise_is_passed_over_and_says_so(
        self,
    ) -> None:
        # covers: BP-1100g-4-ii
        # angle: criterion
        """A ticket declaring status: deferred, carrying an unclaimed promised
        kind, is NOT refused: the deployed check exits zero and states it was
        passed over, naming status deferred (it must read as parked, never as
        a plan that is still status: todo)."""
        self.assertTrue(
            _DEPLOYED_HOOK.is_file(),
            f"deployed check_proof_promise_claim.py not found at {_DEPLOYED_HOOK}",
        )
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            _init_temp_git_project(project_root)
            ticket_path = project_root / "TICKET-zz-bp1100g4ii-deferred.md"
            ticket_path.write_text(
                _build_ticket_fixture("status: deferred"), encoding="utf-8"
            )

            result = _run_check(project_root, ticket_path)

        self.assertEqual(
            result.returncode,
            0,
            "deferred (parked) work with an unclaimed promise must not be "
            f"refused: stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        combined = (result.stdout + result.stderr).lower()
        self.assertIn(
            "passed over",
            combined,
            f"the outcome must state the work was passed over: {combined!r}",
        )
        self.assertIn(
            "deferred",
            combined,
            f"the passed-over line must name the real status, deferred: {combined!r}",
        )
        self.assertNotIn(
            "todo",
            combined,
            f"a deferred ticket must not be described as status: todo: {combined!r}",
        )


class TestTheSameWorkOnceBlockedIsStillRefusedByName(unittest.TestCase):
    """test_spec: test_the_same_work_once_blocked_is_still_refused_by_name
    (angle: discrimination). Mutation guard against widening the exemption to
    "anything not finished"."""

    def test_the_same_work_once_blocked_is_still_refused_by_name(self) -> None:
        # covers: BP-1100g-4-ii
        # angle: discrimination
        """A fixture byte-identical to the deferred one apart from its status
        value, moved to status: blocked, is refused with a non-zero exit
        naming the piece of work and the unclaimed angle."""
        deferred_fixture = _build_ticket_fixture("status: deferred")
        blocked_fixture = _build_ticket_fixture("status: blocked")
        self.assertEqual(
            deferred_fixture.replace("status: deferred", "status: blocked"),
            blocked_fixture,
            "the blocked fixture must differ from the deferred one only by status",
        )
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            _init_temp_git_project(project_root)
            ticket_path = project_root / "TICKET-zz-bp1100g4ii-blocked.md"
            ticket_path.write_text(blocked_fixture, encoding="utf-8")

            result = _run_check(project_root, ticket_path)

        self.assertNotEqual(
            result.returncode,
            0,
            "blocked work with an unclaimed promise must still be refused: "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        combined = (result.stdout + result.stderr).lower()
        self.assertIn(_SHARED_AC_ID.lower(), combined)
        self.assertIn(_SHARED_ANGLE.lower(), combined)


if __name__ == "__main__":
    unittest.main()
