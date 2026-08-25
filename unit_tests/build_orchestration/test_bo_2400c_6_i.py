"""
MODULE: unit_tests/build_orchestration/test_bo_2400c_6_i.py
GOAL: The correctness trap. BO-2400c-6's naive implementation — handing the
      resolver's own (post-cycle-drain) id_index straight to traverse_ac_tree
      — silently drops any subtree that hangs off a cycle member, with no
      error. These tests exist to catch exactly that regression before it
      ships, using a CONSTRUCTED cyclic fixture (the live docs/acceptance-
      criteria store is acyclic today — verified 2026-08-24 per BO-2400c-6-i's
      own text — so a guard built against it would exercise nothing).
COVERS: BO-2400c-6, BO-2400c-6-i

=== The fixture ===

    BO-TST-CYC-T00 (L0)  covered_by=[BO-TST-CYC-A00, BO-TST-CYC-O01]
    BO-TST-CYC-A00 (L0, todo)  depends_on=[BO-TST-CYC-B00]  covered_by=[BO-TST-CYC-A01]
    BO-TST-CYC-B00 (L0, todo)  depends_on=[BO-TST-CYC-A00]
    BO-TST-CYC-A01 (L2, todo)                                    <- reachable from
                                                                     the target ONLY
                                                                     via A00's covered_by
    BO-TST-CYC-O01 (L2, todo)  depends_on=[BO-TST-CYC-A00]        <- outside the cycle,
                                                                     depends on a cycle
                                                                     member

A00 <-> B00 form a dependency cycle. _drain_cycles() (scan_ac_store.py:886)
removes A00 and B00 from the resolver's own id_index AND all_records IN
PLACE, before the tree walk ever runs. Today traverse_ac_tree rebuilds its
own pristine (undrained) index on every call, so A01 — reachable only
through A00 — still resolves correctly. If a future change hands the
DRAINED index straight to the walk instead, the walk hits `id_index.get
("BO-TST-CYC-A00") is None` while descending from the target, returns
immediately, and A01 silently vanishes from the build set. No exception, no
warning about the loss — just fewer members.

=== Verified ground truth (test-writer pre-flight, 2026-08-25) ===

Executed against the live (pre-fix) implementation before this file was
written:

    fast_lane.resolve_connected_build_set("BO-TST-CYC-T00", ac_root=...)
        == ['BO-TST-CYC-A01', 'BO-TST-CYC-O01']

    stderr contains:
        WARNING: dependency cycle detected (store-wide scan continues with
        acyclic ACs): BO-TST-CYC-A00 -> BO-TST-CYC-B00 -> BO-TST-CYC-A00

    The only traverse_ac_tree() call made during that resolution is:
        traverse_ac_tree('BO-TST-CYC-T00', <ac_root>, exclude_done=True)
    — no ``id_index`` keyword is passed at all (the closure step's own
    depends_on lookup at fast_lane.py:785 already uses the resolver's drained
    id_index directly and short-circuits on A00 before traverse_ac_tree is
    ever invoked for it — this is a SEPARATE, pre-existing code path from the
    subtree walk, and is why the subtree route through T00 -> A00 -> A01,
    not the depends_on-closure route, is what exercises the trap).

=== Why three of these four tests PASS immediately ===

test_cycle_adjacent_subtree_resolves_identically,
test_record_reachable_only_through_a_cycle_member_is_not_lost, and
test_cycle_diagnostic_still_reported_after_consolidation are DELIBERATE
regression guards, not red-today tests — BO-2400c-6-i's own test_rationale
requires this: "This guard lands with, or before, the consolidation change —
never after it... The pre-change answer must be captured from the
resolution as it behaves BEFORE the consolidation lands." Since no
production code has changed yet, "before" is simply what these tests observe
right now. They exist to fail loudly the moment a future change narrows the
answer.

test_walk_receives_an_undrained_view_after_cycle_removal is the RED one: it
asserts on the (not yet implemented) contract that resolve_connected_
build_set must SUPPLY an id_index to traverse_ac_tree, and that the supplied
index must be undrained. Today no id_index is passed at all, so it fails for
the right reason.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

# ---------------------------------------------------------------------------
# Repo path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_AC_STORE_DIR = _REPO_ROOT / "scripts" / "ac_store"
_FAST_LANE_DIR = _REPO_ROOT / "scripts" / "build_orchestration"
for _p in (_AC_STORE_DIR, _FAST_LANE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import fast_lane  # noqa: E402

_TARGET_ID = "BO-TST-CYC-T00"
_CYCLE_A_ID = "BO-TST-CYC-A00"
_CYCLE_B_ID = "BO-TST-CYC-B00"
_CHILD_LEAF_ID = "BO-TST-CYC-A01"  # reachable from target ONLY through CYCLE_A
_OUTSIDE_LEAF_ID = "BO-TST-CYC-O01"  # outside the cycle, depends on CYCLE_A

# The recorded pre-consolidation answer (verified live — see module docstring).
_EXPECTED_PRE_CHANGE_ANSWER = [_CHILD_LEAF_ID, _OUTSIDE_LEAF_ID]


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_ac(
    ac_root: Path,
    ac_id: str,
    *,
    level: str,
    work_status: str,
    readiness: str = "approved",
    depends_on: list | None = None,
    covered_by: list | None = None,
) -> Path:
    """Write a minimal AC YAML file using yaml.safe_dump (fixture-authenticity mandate)."""
    subdir = ac_root / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    data: dict = {
        "id": ac_id,
        "title": f"Synthetic test AC {ac_id}",
        "component": "build-orchestration",
        "level": level,
        "status": "active",
        "work_status": work_status,
        "readiness": readiness,
        "priority": "medium",
        "estimated_complexity": "S",
        "depends_on": depends_on if depends_on is not None else [],
        "covered_by": covered_by if covered_by is not None else [],
        "amended_by": [],
        "implemented_by": [],
        "superseded_by": None,
    }
    path = subdir / f"{ac_id}.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _build_cycle_adjacent_store(ac_root: Path) -> None:
    """Build the cyclic + cycle-adjacent fixture described in the module docstring.

    A00 <-> B00 is a genuine dependency cycle. A01 hangs off A00's covered_by
    and is reachable from the target ONLY by passing through A00. O01 sits
    outside the cycle and depends_on a cycle member (A00).
    """
    _write_ac(
        ac_root,
        _TARGET_ID,
        level="L0",
        work_status="todo",
        covered_by=[_CYCLE_A_ID, _OUTSIDE_LEAF_ID],
    )
    _write_ac(
        ac_root,
        _CYCLE_A_ID,
        level="L0",
        work_status="todo",
        depends_on=[_CYCLE_B_ID],
        covered_by=[_CHILD_LEAF_ID],
    )
    _write_ac(
        ac_root,
        _CYCLE_B_ID,
        level="L0",
        work_status="todo",
        depends_on=[_CYCLE_A_ID],
    )
    _write_ac(ac_root, _CHILD_LEAF_ID, level="L2", work_status="todo")
    _write_ac(
        ac_root,
        _OUTSIDE_LEAF_ID,
        level="L2",
        work_status="todo",
        depends_on=[_CYCLE_A_ID],
    )


class _CycleFixtureTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.ac_root.mkdir(parents=True, exist_ok=True)
        _build_cycle_adjacent_store(self.ac_root)

    def tearDown(self) -> None:
        self._tmp.cleanup()


# ---------------------------------------------------------------------------
# BO-2400c-6: the correctness trap itself — RED today
# ---------------------------------------------------------------------------


class TestWalkReceivesAnUndrainedViewAfterCycleRemoval(_CycleFixtureTestCase):
    """BO-2400c-6 (failure angle): the id_index handed to traverse_ac_tree
    during resolution must still contain the cycle members _drain_cycles
    removed from the resolver's own working view.
    """

    def test_walk_receives_an_undrained_view_after_cycle_removal(self) -> None:
        # covers: BO-2400c-6
        """On a constructed store containing a cycle, the record set the walk
        is given still contains the cycle members that the drain removed
        from the resolver's own working view.

        RED today: resolve_connected_build_set does not pass an ``id_index``
        keyword to traverse_ac_tree at all yet (verified live — the single
        call made is ``traverse_ac_tree('BO-TST-CYC-T00', <root>,
        exclude_done=True)``, no id_index kwarg). Once the consolidation
        lands, every call must supply one, and it must be the UNDRAINED view
        (still containing BO-TST-CYC-A00 / BO-TST-CYC-B00) — never the
        resolver's own post-_drain_cycles index, which would silently drop
        BO-TST-CYC-A01 (see the module docstring's correctness-trap
        explanation).
        """
        real_traverse = fast_lane.traverse_ac_tree
        captured_calls: list[tuple[tuple, dict]] = []

        def capturing_traverse(*args, **kwargs):
            captured_calls.append((args, kwargs))
            return real_traverse(*args, **kwargs)

        with mock.patch.object(fast_lane, "traverse_ac_tree", side_effect=capturing_traverse):
            fast_lane.resolve_connected_build_set(_TARGET_ID, ac_root=self.ac_root)

        self.assertTrue(
            captured_calls,
            "traverse_ac_tree was never invoked during resolution — the subtree walk "
            "step (fast_lane.py ~772) must call it at least once.",
        )

        missing_index_calls = [
            (args, kwargs) for args, kwargs in captured_calls if kwargs.get("id_index") is None
        ]
        self.assertFalse(
            missing_index_calls,
            "Every traverse_ac_tree call made by resolve_connected_build_set must "
            "supply a caller-built id_index once the store-read consolidation lands "
            f"(BO-2400c-6). {len(missing_index_calls)} of {len(captured_calls)} call(s) "
            f"supplied none: {missing_index_calls!r}",
        )

        for args, kwargs in captured_calls:
            supplied_index = kwargs["id_index"]
            for cycle_member in (_CYCLE_A_ID, _CYCLE_B_ID):
                self.assertIn(
                    cycle_member,
                    supplied_index,
                    "The id_index handed to traverse_ac_tree must be UNDRAINED: it "
                    f"must still contain the cycle member {cycle_member!r} that "
                    "_drain_cycles removed from the resolver's own working view "
                    "(BO-2400c-6 correctness trap — handing over the drained index "
                    "would silently drop the subtree hanging off it, e.g. "
                    f"{_CHILD_LEAF_ID!r}). Supplied index keys: "
                    f"{sorted(supplied_index.keys())!r}. Call args: {args!r}",
                )


# ---------------------------------------------------------------------------
# BO-2400c-6-i: equivalence guard — deliberate regression guards, green today
# ---------------------------------------------------------------------------


class TestCycleAdjacentSubtreeResolvesIdentically(_CycleFixtureTestCase):
    """BO-2400c-6-i: the resolved set for a cycle-adjacent target must be
    identical before and after the store-read consolidation.

    DELIBERATE REGRESSION GUARD (see module docstring "Why three of these
    four tests PASS immediately"): pins today's verified-live answer as the
    expected value so a future change cannot silently narrow it.
    """

    def test_cycle_adjacent_subtree_resolves_identically(self) -> None:
        # covers: BO-2400c-6-i
        """On the constructed cyclic fixture, the resolved ordered id list
        matches the answer recorded from the pre-consolidation behaviour,
        member for member and in order.
        """
        result = fast_lane.resolve_connected_build_set(_TARGET_ID, ac_root=self.ac_root)

        self.assertEqual(
            result,
            _EXPECTED_PRE_CHANGE_ANSWER,
            "The resolved set for a cycle-adjacent target must match the recorded "
            f"pre-consolidation answer exactly (BO-2400c-6-i). Expected "
            f"{_EXPECTED_PRE_CHANGE_ANSWER!r}, got {result!r}. A resolution that "
            "returns fewer members while reporting no error is a failure of this "
            "criterion, not an optimisation.",
        )


class TestRecordReachableOnlyThroughACycleMemberIsNotLost(_CycleFixtureTestCase):
    """BO-2400c-6-i (boundary angle): the cycle-adjacent leaf must not vanish.

    DELIBERATE REGRESSION GUARD — see module docstring.
    """

    def test_record_reachable_only_through_a_cycle_member_is_not_lost(self) -> None:
        # covers: BO-2400c-6-i
        """The record reachable from the target only by passing through a
        cycle member (BO-TST-CYC-A01, reachable only via BO-TST-CYC-A00)
        appears in the post-change answer whenever it appeared in the
        pre-change answer.

        This is the single assertion that would fail under the naive "hand
        the drained index straight to the walk" implementation — it is
        isolated here from the full-list equivalence check above so a
        reviewer can see exactly which record the trap would silently drop.
        """
        result = fast_lane.resolve_connected_build_set(_TARGET_ID, ac_root=self.ac_root)

        self.assertIn(
            _CHILD_LEAF_ID,
            result,
            f"{_CHILD_LEAF_ID!r} is reachable from {_TARGET_ID!r} ONLY through the "
            f"cycle member {_CYCLE_A_ID!r}. It must remain in the resolved set after "
            "the store-read consolidation lands (BO-2400c-6-i) — its disappearance "
            "with no error is exactly the phantom-done regression this AC guards "
            f"against. Got: {result!r}",
        )


class TestCycleDiagnosticStillReportedAfterConsolidation(_CycleFixtureTestCase):
    """BO-2400c-6-i (failure angle): the cycle warning must still fire.

    DELIBERATE REGRESSION GUARD — see module docstring.
    """

    def test_cycle_diagnostic_still_reported_after_consolidation(self) -> None:
        # covers: BO-2400c-6-i
        """The resolution against the cyclic fixture still reports the cycle
        it found; consolidating the reading did not silence the diagnostic.

        Uses a plain stderr capture (redirect, not pytest capsys) so this
        stays a unittest.TestCase like its siblings in this file.
        """
        import contextlib
        import io

        captured_stderr = io.StringIO()
        with contextlib.redirect_stderr(captured_stderr):
            fast_lane.resolve_connected_build_set(_TARGET_ID, ac_root=self.ac_root)

        stderr_text = captured_stderr.getvalue()

        self.assertIn(
            "WARNING",
            stderr_text,
            "resolve_connected_build_set must still emit a WARNING for the detected "
            f"dependency cycle after the store-read consolidation (BO-2400c-6-i). "
            f"Got stderr: {stderr_text!r}",
        )
        self.assertTrue(
            _CYCLE_A_ID in stderr_text or _CYCLE_B_ID in stderr_text,
            "The cycle diagnostic must still name the cyclic AC ids "
            f"({_CYCLE_A_ID!r} / {_CYCLE_B_ID!r}). Got stderr: {stderr_text!r}",
        )


if __name__ == "__main__":
    unittest.main()
