"""
MODULE: unit_tests/ac_store/test_acd_1200f_2_i.py
GOAL: Tests for ACD-1200f-2-i — traverse_ac_tree must emit each leaf exactly
      once even when that leaf is reachable by more than one covered_by path.
      A duplicated leaf id is not a cosmetic wart: goal_to_epic generates one
      ticket per returned id, so a duplicate becomes a duplicate ticket for the
      same AC.
COVERS: ACD-1200f-2-i

Diamond fixture used throughout (mirrors the Gherkin exactly):

    ROOT-002         L0  covered_by: [ROOT-002a]
    ROOT-002a        L1  covered_by: [ROOT-002a-1, ROOT-002a-1-i, ROOT-002a-2]
      ROOT-002a-1    L2  covered_by: [ROOT-002a-1-i]
        ROOT-002a-1-i  L3  covered_by: []
      ROOT-002a-2    L2  covered_by: []

ROOT-002a-1-i is reachable twice: directly from ROOT-002a's covered_by, and
indirectly via ROOT-002a-1's covered_by. The three distinct leaves are
ROOT-002a-1, ROOT-002a-1-i and ROOT-002a-2.

NOTE ON PATCHING: these tests patch nothing. traverse_ac_tree is called for
real against a real on-disk store. Per the 2026-09-14 decomposition of
goal_to_epic.py, patching "goal_to_epic.<name>" no longer intercepts anything —
each name is defined and called inside its own sibling module and resolved
through that module's globals. traverse_ac_tree itself stayed in
scripts/ac_store/scan_ac_store.py and is imported from there.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from scan_ac_store import traverse_ac_tree  # noqa: E402

#: The distinct L2/L3 leaves beneath ROOT-002, independent of traversal order.
_EXPECTED_LEAVES = {"ROOT-002a-1", "ROOT-002a-1-i", "ROOT-002a-2"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_ac(
    ac_root: Path,
    ac_id: str,
    level: str,
    *,
    covered_by: list[str] | None = None,
) -> Path:
    """Write one active, todo AC YAML file into *ac_root* via the real serializer.

    The bytes on disk come from ``yaml.dump`` — the same serializer the store
    itself is written with — so the loader under test parses the real on-disk
    format rather than a hand-typed literal.

    Args:
        ac_root: Root directory of the throwaway AC store.
        ac_id: The AC id, also used to derive the component subdirectory.
        level: AC flight level (``L0``/``L1``/``L2``/``L3``).
        covered_by: Child AC ids, or ``None`` for an empty list.

    Returns:
        Path: The written YAML file.
    """
    parts = ac_id.split("-")
    subdir = ac_root / "-".join(parts[:2]) if len(parts) >= 2 else ac_root
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict = {
        "id": ac_id,
        "title": f"Test AC {ac_id}",
        "level": level,
        "status": "active",
        "work_status": "todo",
        "covered_by": covered_by if covered_by is not None else [],
    }
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _build_diamond_tree(ac_root: Path) -> None:
    """Populate *ac_root* with the ROOT-002 diamond from the Gherkin Given.

    The L1 lists ALL descendants (children and grandchildren) while the L2 ALSO
    lists its own L3 child, so ROOT-002a-1-i sits at the bottom of a diamond.

    Args:
        ac_root: Root directory of the throwaway AC store.
    """
    _write_ac(ac_root, "ROOT-002", "L0", covered_by=["ROOT-002a"])
    _write_ac(
        ac_root,
        "ROOT-002a",
        "L1",
        covered_by=["ROOT-002a-1", "ROOT-002a-1-i", "ROOT-002a-2"],
    )
    _write_ac(ac_root, "ROOT-002a-1", "L2", covered_by=["ROOT-002a-1-i"])
    _write_ac(ac_root, "ROOT-002a-1-i", "L3", covered_by=[])
    _write_ac(ac_root, "ROOT-002a-2", "L2", covered_by=[])


# ---------------------------------------------------------------------------
# ACD-1200f-2-i
# ---------------------------------------------------------------------------


class TestDiamondReachableLeafIsEmittedOnce:
    """ACD-1200f-2-i: multi-path reachability must not duplicate a leaf."""

    def test_acd_1200f_2_i_diamond_reachable_leaf_appears_exactly_once(
        self, tmp_path: Path
    ) -> None:
        # covers: ACD-1200f-2-i
        # angle: criterion
        """ROOT-002a-1-i occurs EXACTLY ONCE, not twice.

        It is reachable both directly from ROOT-002a's covered_by and
        indirectly via ROOT-002a-1's covered_by. Occurrences are counted rather
        than tested for membership: a plain ``in`` check passes on the
        duplicated output this AC exists to prevent.
        """
        ac_root = tmp_path / "acs"
        _build_diamond_tree(ac_root)

        result = traverse_ac_tree("ROOT-002", ac_root)
        occurrences = Counter(result)["ROOT-002a-1-i"]

        assert occurrences == 1, (
            "ROOT-002a-1-i is reachable by two covered_by paths but must be "
            f"emitted once. Counted {occurrences} occurrence(s) in: {result}"
        )

    def test_acd_1200f_2_i_every_other_leaf_appears_exactly_once(
        self, tmp_path: Path
    ) -> None:
        # covers: ACD-1200f-2-i
        # angle: criterion
        """ROOT-002a-1 and ROOT-002a-2 each appear exactly once.

        The whole result is duplicate-free, not just the diamond node — a guard
        applied only to the node that happens to sit at the diamond's foot would
        pass the test above and fail here.
        """
        ac_root = tmp_path / "acs"
        _build_diamond_tree(ac_root)

        result = traverse_ac_tree("ROOT-002", ac_root)
        counts = Counter(result)

        for leaf_id in ("ROOT-002a-1", "ROOT-002a-2"):
            assert counts[leaf_id] == 1, (
                f"{leaf_id} must be emitted exactly once. Counted "
                f"{counts[leaf_id]} occurrence(s) in: {result}"
            )

    def test_acd_1200f_2_i_result_length_equals_distinct_leaf_count(
        self, tmp_path: Path
    ) -> None:
        # covers: ACD-1200f-2-i
        # angle: boundary
        """The result is exactly the three distinct leaves — no more, no fewer.

        Pins both failure directions at once: ``len(result) == len(set(result))``
        catches a de-duplication that never happened, and comparing the set to
        the expected three catches one that over-corrected and dropped a genuine
        leaf (e.g. a guard that marks a node seen before deciding to emit it).
        """
        ac_root = tmp_path / "acs"
        _build_diamond_tree(ac_root)

        result = traverse_ac_tree("ROOT-002", ac_root)

        assert len(result) == len(set(result)), (
            f"The result must contain no duplicates. Got: {result}"
        )
        assert set(result) == _EXPECTED_LEAVES, (
            f"The distinct leaves must be {sorted(_EXPECTED_LEAVES)}. "
            f"Got: {sorted(set(result))}"
        )
        assert len(result) == len(_EXPECTED_LEAVES), (
            f"The total leaf count must be {len(_EXPECTED_LEAVES)}. Got: {result}"
        )


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 [ACD-1200f-2-i/test-writer]: Initial tests, authored from the AC's
  three test_spec descriptors. All three are GREEN on arrival — the visited-set
  guard the AC asks for is already present in _dfs_collect_leaves (the ``seen``
  set threaded through from traverse_ac_tree), so these tests are a regression
  lock rather than a red baseline. Reported as a TDD-order signal rather than
  weakened to manufacture red. Nothing is patched: the diamond store is written
  with yaml.dump and traverse_ac_tree is imported from its owning sibling,
  scan_ac_store, never through the goal_to_epic facade.
====================================================================
"""
