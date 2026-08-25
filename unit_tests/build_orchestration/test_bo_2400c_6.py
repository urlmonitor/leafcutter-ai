"""
MODULE: unit_tests/build_orchestration/test_bo_2400c_6.py
GOAL: RED test stubs for BO-2400c-6 — resolve_connected_build_set() must read
      every store record AT MOST ONCE per resolution, and the resolved id
      list it produces must not change when that reading is consolidated.
COVERS: BO-2400c-6

=== What must be true after python-coder's change ===

1. traverse_ac_tree() in scripts/ac_store/scan_ac_store.py accepts an
   optional, keyword-only ``id_index`` parameter. When supplied, the walk
   consumes it directly and performs NO further directory read / YAML parse
   of its own.
2. resolve_connected_build_set() in scripts/build_orchestration/fast_lane.py
   builds its id_index ONCE (as it already does around line 761) and passes
   that same mapping into every traverse_ac_tree() call it makes, instead of
   letting each call re-walk and re-parse the whole store.

=== Cost assertion discipline (mandatory per BO-2400c-6) ===

The AC text is explicit that the only acceptable mechanical assertion for the
cost half of this criterion is a COUNT of parses/opens, never elapsed time —
a wall-clock assertion flakes on shared CI and is deleted by the first person
it inconveniences, silently uncovering the regression it was meant to guard.
test_one_resolution_parses_each_store_file_at_most_once below counts calls
into ``scan_ac_store._load_ac`` (the sole file-open / YAML-parse choke point
used by both ``traverse_ac_tree`` and ``resolve_connected_build_set``'s own
index build) — never a timer.

=== Verified ground truth (test-writer pre-flight, 2026-08-25) ===

Both tests were executed against a live probe of the CURRENT (pre-fix)
implementation before being committed to this file:

- The multi-expansion fixture below causes each of its 6 YAML files to be
  parsed via ``_load_ac`` exactly 4 TIMES in one ``resolve_connected_build_set``
  call (1 for the initial id_index build + 1 for the ``traverse_ac_tree(ac_id)``
  call + 1 per not-done composite dependency it expands — 2 here). This is the
  RED state test_one_resolution_parses_each_store_file_at_most_once captures.
- resolve_connected_build_set("BO-TST-RC-P00", ...) against that same fixture
  returns ``['BO-TST-RC-P01', 'BO-TST-RC-Q01', 'BO-TST-RC-R01']`` today. That
  is the pinned expected value in test_resolved_set_unchanged_for_a_multi_
  expansion_target — a DELIBERATE regression guard (see its docstring): the
  answer is already correct, only the I/O cost is wrong, so this test is
  expected to PASS immediately and must keep passing after the fix.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from collections import Counter
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

import scan_ac_store  # noqa: E402
import fast_lane  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helpers — fixture-authenticity mandate: yaml.safe_dump, never a
# hand-typed YAML literal. Mirrors unit_tests/build_orchestration/
# test_fast_lane_connected.py's _write_ac helper.
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


def _build_multi_expansion_store(ac_root: Path) -> None:
    """Build a store whose resolution requires >= 2 composite expansions.

    BO-TST-RC-P00 (L0) -> BO-TST-RC-P01 (L2, todo) depends_on [Q00, R00]
    BO-TST-RC-Q00 (L0, todo) -> BO-TST-RC-Q01 (L2, todo)   composite expansion #1
    BO-TST-RC-R00 (L0, todo) -> BO-TST-RC-R01 (L2, todo)   composite expansion #2

    resolve_connected_build_set("BO-TST-RC-P00", ...) must expand BOTH Q00 and
    R00 (neither is done) to reach their leaves — satisfying the AC's
    "requires expanding two or more not-done composite dependencies" precondition.
    """
    _write_ac(ac_root, "BO-TST-RC-P00", level="L0", work_status="todo", covered_by=["BO-TST-RC-P01"])
    _write_ac(
        ac_root,
        "BO-TST-RC-P01",
        level="L2",
        work_status="todo",
        depends_on=["BO-TST-RC-Q00", "BO-TST-RC-R00"],
    )
    _write_ac(ac_root, "BO-TST-RC-Q00", level="L0", work_status="todo", covered_by=["BO-TST-RC-Q01"])
    _write_ac(ac_root, "BO-TST-RC-Q01", level="L2", work_status="todo")
    _write_ac(ac_root, "BO-TST-RC-R00", level="L0", work_status="todo", covered_by=["BO-TST-RC-R01"])
    _write_ac(ac_root, "BO-TST-RC-R01", level="L2", work_status="todo")


# ---------------------------------------------------------------------------
# BO-2400c-6: cost — count parses, never wall-clock
# ---------------------------------------------------------------------------


class TestOneResolutionParsesEachStoreFileAtMostOnce(unittest.TestCase):
    """BO-2400c-6: no store record is parsed more than once per resolution."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.ac_root.mkdir(parents=True, exist_ok=True)
        _build_multi_expansion_store(self.ac_root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_one_resolution_parses_each_store_file_at_most_once(self) -> None:
        # covers: BO-2400c-6
        """No YAML file in the store is parsed more than once during one
        resolve_connected_build_set() call, for a target requiring 2+
        composite expansions.

        Counts calls into scan_ac_store._load_ac (the sole parse/open choke
        point reached by both traverse_ac_tree and resolve_connected_build_set's
        own index build), per file path. Asserts the max per-path count is 1 —
        deliberately NEVER a wall-clock bound (the AC forbids timing assertions:
        they flake on shared CI and get deleted, silently uncovering the
        regression).

        RED today: verified live, each of the 6 fixture files is parsed 4
        times in one call (1 initial index build + 1 traverse_ac_tree(ac_id)
        + 1 per not-done composite dependency expanded — 2 here).
        """
        real_load_ac = scan_ac_store._load_ac
        calls: list[Path] = []

        def counting_load_ac(path: Path):
            calls.append(path)
            return real_load_ac(path)

        with mock.patch.object(scan_ac_store, "_load_ac", side_effect=counting_load_ac), \
                mock.patch.object(fast_lane, "_load_ac", side_effect=counting_load_ac):
            fast_lane.resolve_connected_build_set("BO-TST-RC-P00", ac_root=self.ac_root)

        per_file_counts = Counter(calls)
        over_parsed = {str(p): c for p, c in per_file_counts.items() if c > 1}

        self.assertFalse(
            over_parsed,
            "resolve_connected_build_set must parse each store record at most once "
            f"per resolution (BO-2400c-6). Over-parsed files (path -> parse count): "
            f"{over_parsed!r}. Total _load_ac calls: {len(calls)} across "
            f"{len(per_file_counts)} distinct files — expected at most "
            f"{len(per_file_counts)} total calls (one per file)."
        )


class TestResolvedSetUnchangedForMultiExpansionTarget(unittest.TestCase):
    """BO-2400c-6: consolidating the reads must not change the resolved set.

    DELIBERATE REGRESSION GUARD — not a red-today test. resolve_connected_
    build_set already produces the correct answer for this fixture (only its
    I/O cost is wrong today), so this test PASSES immediately. Its job is to
    fail loudly if a future "read the store once" change also changes the
    answer, per the AC: "a resolution that returns fewer members than before
    while reporting no error is a failure of this criterion, not an
    optimisation."
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.ac_root.mkdir(parents=True, exist_ok=True)
        _build_multi_expansion_store(self.ac_root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_resolved_set_unchanged_for_a_multi_expansion_target(self) -> None:
        # covers: BO-2400c-6
        """The resolved ordered id list for a multi-expansion target is exactly
        the answer this same store produces today (verified live) — same
        members, same order.
        """
        result = fast_lane.resolve_connected_build_set("BO-TST-RC-P00", ac_root=self.ac_root)

        expected = [
            "BO-TST-RC-P01",
            "BO-TST-RC-Q01",
            "BO-TST-RC-R01",
        ]
        self.assertEqual(
            result,
            expected,
            "Consolidating the store reads must not change the resolved connected "
            f"build set (BO-2400c-6). Expected {expected!r}, got {result!r}.",
        )


if __name__ == "__main__":
    unittest.main()
