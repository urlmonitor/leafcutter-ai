"""
MODULE: test_tree_traversal
GOAL: Unit tests for traverse_ac_tree() in scan_ac_store.py.
TICKET: EPIC-GoalToEpic/01_tree-traversal-ticket-generation.md
COVERS: ACS-1000, ACD-1200a-1-i, ACD-1200a-9-i

NOTE: leaf semantics are level-based (a node is a leaf iff its level is in
{L2, L3}), NOT covered_by-based. This matches the production contract in
scan_ac_store.py, build_ac_mode_detection.py, and goal_to_epic.py. The earlier
covered_by-based definition (ACD-1200a-1) was superseded; see ACS-1000.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from scan_ac_store import traverse_ac_tree  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _write_ac(ac_root: Path, ac_id: str, covered_by: list[str] | None = None) -> Path:
    """Write a minimal AC YAML file into *ac_root* and return its path."""
    parts = ac_id.split("-")
    subdir = ac_root / "-".join(parts[:2]) if len(parts) >= 2 else ac_root
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict = {
        "id": ac_id,
        "title": f"AC {ac_id}",
        "level": "L0" if len(parts) == 1 else ("L1" if len(parts) == 2 else "L2"),
        "status": "active",
        "work_status": "todo",
        "covered_by": covered_by if covered_by else [],
    }
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _write_ac_explicit(
    ac_root: Path,
    ac_id: str,
    level: str,
    covered_by: list[str],
) -> None:
    """Write a minimal AC YAML with an explicit *level* value (not inferred).

    Preferred over _write_ac for leaf-semantics tests: leaf-ness is determined
    by the level field, so tests that exercise the level-based contract must set
    levels explicitly rather than relying on id-segment inference.
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
        "covered_by": covered_by,
    }
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")


# ---------------------------------------------------------------------------
# ACS-1000: level-based leaf collection from a mixed tree
# ---------------------------------------------------------------------------


class TestTraverseAcTreeLeafCollection:
    """ACS-1000: tree traversal returns only L2/L3 leaf ACs from a mixed tree."""

    def test_ac1_only_l2_l3_returned_from_mixed_tree(self, tmp_path: Path) -> None:
        # covers: ACS-1000
        """ACS-1000: leaves are the L2/L3 nodes; L0/L1 composites are excluded.

        An L2 node that itself has L3 children is still emitted (level-based),
        and traversal recurses into those children.
        """
        # Build tree: L0 -> L1a, L1b; L1a -> L2(a-1, a-2); L1b -> L2(b-1);
        # L2 a-1 -> L3 a-1-i.
        _write_ac_explicit(tmp_path, "ACD-050", "L0", ["ACD-050a", "ACD-050b"])
        _write_ac_explicit(tmp_path, "ACD-050a", "L1", ["ACD-050a-1", "ACD-050a-2"])
        _write_ac_explicit(tmp_path, "ACD-050b", "L1", ["ACD-050b-1"])
        _write_ac_explicit(tmp_path, "ACD-050a-1", "L2", ["ACD-050a-1-i"])
        _write_ac_explicit(tmp_path, "ACD-050a-2", "L2", [])
        _write_ac_explicit(tmp_path, "ACD-050a-1-i", "L3", [])
        _write_ac_explicit(tmp_path, "ACD-050b-1", "L2", [])

        result = traverse_ac_tree("ACD-050", tmp_path)

        # All L2/L3 nodes are leaves; L0/L1 composites are excluded.
        assert set(result) == {
            "ACD-050a-1",
            "ACD-050a-1-i",
            "ACD-050a-2",
            "ACD-050b-1",
        }, f"Expected all L2/L3 leaf ACs, got: {result}"
        assert "ACD-050" not in result, "L0 root must be excluded"
        assert "ACD-050a" not in result, "L1 composite must be excluded"
        assert "ACD-050b" not in result, "L1 composite must be excluded"

    def test_ac1_composites_excluded(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-1
        """AC-1: Composite ACs (with non-empty covered_by) must not appear in results."""
        _write_ac(tmp_path, "ACD-050", covered_by=["ACD-050a"])
        _write_ac(tmp_path, "ACD-050a", covered_by=["ACD-050a-1"])
        _write_ac(tmp_path, "ACD-050a-1", covered_by=[])

        result = traverse_ac_tree("ACD-050", tmp_path)

        assert "ACD-050" not in result, "Root should not be in leaf result"
        assert "ACD-050a" not in result, "Composite L1 should not be in leaf result"
        assert "ACD-050a-1" in result

    def test_ac1_depth_first_alphabetical_order(self, tmp_path: Path) -> None:
        # covers: ACS-1000
        """ACS-1000: Leaves returned in depth-first, alphabetical-sibling order."""
        # covered_by listed out of order to prove siblings are visited alphabetically.
        _write_ac_explicit(tmp_path, "ACD-050", "L0", ["ACD-050b", "ACD-050a"])
        _write_ac_explicit(tmp_path, "ACD-050a", "L1", ["ACD-050a-2", "ACD-050a-1"])
        _write_ac_explicit(tmp_path, "ACD-050b", "L2", [])  # leaf
        _write_ac_explicit(tmp_path, "ACD-050a-1", "L2", [])  # leaf
        _write_ac_explicit(tmp_path, "ACD-050a-2", "L2", [])  # leaf

        result = traverse_ac_tree("ACD-050", tmp_path)

        # depth-first alphabetical: ACD-050a (alpha first) -> ACD-050a-1, ACD-050a-2, then ACD-050b
        assert result == ["ACD-050a-1", "ACD-050a-2", "ACD-050b"], (
            f"Expected depth-first alphabetical order, got: {result}"
        )

    def test_ac1_performance_200_nodes(self, tmp_path: Path) -> None:
        # covers: ACS-1000
        """ACS-1000: Traversal completes in under 200ms for trees up to 200 nodes."""
        # Build a wide tree: L0 root -> 10 L1 composites -> 19 L2 leaves each.
        # 1 + 10 + 190 = 201 nodes; only the 190 L2 leaves are emitted.
        root_children = [f"ACD-PERF-{i:03d}" for i in range(10)]
        _write_ac_explicit(tmp_path, "ACD-PERF", "L0", root_children)
        for child in root_children:
            grandchildren = [f"{child}-{j:03d}" for j in range(19)]
            _write_ac_explicit(tmp_path, child, "L1", grandchildren)
            for gc in grandchildren:
                _write_ac_explicit(tmp_path, gc, "L2", [])

        start = time.perf_counter()
        result = traverse_ac_tree("ACD-PERF", tmp_path)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert len(result) == 190, f"Expected 190 leaf ACs, got {len(result)}"
        assert elapsed_ms < 200, f"Traversal took {elapsed_ms:.1f}ms — exceeded 200ms budget"

    def test_ac1_absent_covered_by_l2_is_leaf(self, tmp_path: Path) -> None:
        # covers: ACS-1000
        """ACS-1000: leaf-ness is level-based, so an L2 node with an absent
        covered_by field is still emitted, while an L1 with an absent
        covered_by field is still excluded (composite)."""
        _write_ac_explicit(tmp_path, "ACD-050", "L0", ["ACD-050a", "ACD-050b"])

        # ACD-050a: L2 with NO covered_by key at all (absent, not empty list).
        subdir = tmp_path / "ACD-050"
        subdir.mkdir(parents=True, exist_ok=True)
        l2_data = {"id": "ACD-050a", "title": "AC ACD-050a", "level": "L2", "status": "active", "work_status": "todo"}
        (subdir / "ACD-050a.yaml").write_text(yaml.dump(l2_data), encoding="utf-8")

        # ACD-050b: L1 with NO covered_by key — a composite with no descendants.
        l1_data = {"id": "ACD-050b", "title": "AC ACD-050b", "level": "L1", "status": "active", "work_status": "todo"}
        (subdir / "ACD-050b.yaml").write_text(yaml.dump(l1_data), encoding="utf-8")

        result = traverse_ac_tree("ACD-050", tmp_path)
        assert "ACD-050a" in result, "L2 with absent covered_by should be a leaf"
        assert "ACD-050b" not in result, "L1 with absent covered_by must stay composite"


# ---------------------------------------------------------------------------
# ACD-1200a-1-i: L1-scoped traversal
# ---------------------------------------------------------------------------


class TestTraverseAcTreeL1Scope:
    """AC-2 (ACD-1200a-1-i): L1-scoped traversal excludes sibling L1 branches."""

    def test_ac1i_l1_scoped_excludes_sibling_branches(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-1-i
        """ACD-1200a-1-i: Traversal scoped to an L1 excludes sibling L1 branches."""
        _write_ac(tmp_path, "ACD-050", covered_by=["ACD-050a", "ACD-050b"])
        _write_ac(tmp_path, "ACD-050a", covered_by=["ACD-050a-1"])
        _write_ac(tmp_path, "ACD-050b", covered_by=["ACD-050b-1"])
        _write_ac(tmp_path, "ACD-050a-1", covered_by=[])
        _write_ac(tmp_path, "ACD-050b-1", covered_by=[])

        # Scope traversal to ACD-050a only
        result = traverse_ac_tree("ACD-050a", tmp_path)

        assert "ACD-050a-1" in result, "ACD-050a-1 should be in L1-scoped result"
        assert "ACD-050b-1" not in result, "ACD-050b-1 (sibling branch) must be excluded"
        assert "ACD-050b" not in result, "Sibling L1 ACD-050b must be excluded"

    def test_ac1i_l1_scoped_returns_exact_subtree(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-1-i
        """ACD-1200a-1-i: L1-scoped result contains exactly the leaves under that L1."""
        _write_ac(tmp_path, "ACD-050", covered_by=["ACD-050a", "ACD-050b", "ACD-050c"])
        _write_ac(tmp_path, "ACD-050a", covered_by=["ACD-050a-1", "ACD-050a-2"])
        _write_ac(tmp_path, "ACD-050b", covered_by=["ACD-050b-1"])
        _write_ac(tmp_path, "ACD-050c", covered_by=[])
        _write_ac(tmp_path, "ACD-050a-1", covered_by=[])
        _write_ac(tmp_path, "ACD-050a-2", covered_by=[])
        _write_ac(tmp_path, "ACD-050b-1", covered_by=[])

        result = traverse_ac_tree("ACD-050a", tmp_path)

        assert set(result) == {"ACD-050a-1", "ACD-050a-2"}, (
            f"L1-scoped traversal from ACD-050a should return only its leaves, got {result}"
        )

    def test_ac1i_leaf_l2_root_returns_itself(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-1-i
        """ACD-1200a-1-i: When the scoped root is itself an L2/L3 leaf, return just it."""
        _write_ac_explicit(tmp_path, "ACD-050", "L0", ["ACD-050a"])
        _write_ac_explicit(tmp_path, "ACD-050a", "L1", ["ACD-050a-1"])
        _write_ac_explicit(tmp_path, "ACD-050a-1", "L2", [])  # leaf L2

        result = traverse_ac_tree("ACD-050a-1", tmp_path)

        assert result == ["ACD-050a-1"], (
            f"A leaf L2 used as scope root should return only itself, got {result}"
        )

    def test_ac1i_composite_l1_root_with_no_leaves_returns_empty(self, tmp_path: Path) -> None:
        # covers: ACS-1000
        """ACS-1000: An L1 scope root with no L2/L3 descendants returns []."""
        _write_ac_explicit(tmp_path, "ACD-050", "L0", ["ACD-050a"])
        _write_ac_explicit(tmp_path, "ACD-050a", "L1", [])  # composite, no leaves

        result = traverse_ac_tree("ACD-050a", tmp_path)

        assert result == [], (
            f"A composite L1 root with no L2/L3 descendants should return [], got {result}"
        )


# ---------------------------------------------------------------------------
# ACD-1200a-9-i: deduplication — leaf reachable by multiple covered_by paths
# ---------------------------------------------------------------------------


class TestTraverseDeduplication:
    """ACD-1200a-9-i: traverse_ac_tree must emit each leaf id exactly once
    even when that leaf is reachable by multiple covered_by paths.

    Bug symptom: _dfs_collect_leaves has no visited/seen guard, so a leaf
    whose id appears in covered_by at multiple levels is appended to the
    result list once per visit, producing duplicates.

    Tree shape that triggers the bug (mirrors ACD-1200a-9-i criteria exactly):
        ROOT-002         L0  covered_by: [ROOT-002a]
        ROOT-002a        L1  covered_by: [ROOT-002a-1, ROOT-002a-1-i, ROOT-002a-2]
                                          ^--- lists the grandchild directly too
        ROOT-002a-1      L2  covered_by: [ROOT-002a-1-i]
        ROOT-002a-1-i    L3  covered_by: []   <-- visited twice in buggy code
        ROOT-002a-2      L2  covered_by: []
    """

    def _build_dedup_tree(self, ac_root: Path) -> None:
        """Populate *ac_root* with the five-node test tree."""
        _write_ac_explicit(ac_root, "ROOT-002", "L0", ["ROOT-002a"])
        _write_ac_explicit(
            ac_root,
            "ROOT-002a",
            "L1",
            # L1 lists grandchild ROOT-002a-1-i directly in addition to its
            # L2 children — this is the redundant path that causes the duplicate.
            ["ROOT-002a-1", "ROOT-002a-1-i", "ROOT-002a-2"],
        )
        _write_ac_explicit(ac_root, "ROOT-002a-1", "L2", ["ROOT-002a-1-i"])
        _write_ac_explicit(ac_root, "ROOT-002a-1-i", "L3", [])
        _write_ac_explicit(ac_root, "ROOT-002a-2", "L2", [])

    def test_ac_acd1200a9i_no_duplicate_leaves(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-9-i
        """ACD-1200a-9-i: result list must contain no duplicate leaf ids.

        The buggy _dfs_collect_leaves emits ROOT-002a-1-i twice because:
          1. ROOT-002a's covered_by lists ROOT-002a-1-i directly (first visit).
          2. ROOT-002a-1's covered_by also lists ROOT-002a-1-i (second visit via L2).
        A visited/seen guard must prevent the second emission.
        """
        self._build_dedup_tree(tmp_path)
        result = traverse_ac_tree("ROOT-002", tmp_path)

        assert len(result) == len(set(result)), (
            f"traverse_ac_tree returned duplicate leaf ids: {result}"
        )

    def test_ac_acd1200a9i_grandchild_appears_once(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-9-i
        """ACD-1200a-9-i: ROOT-002a-1-i (reachable twice) must appear exactly once.

        Without a dedup guard the buggy code returns count == 2 for this leaf.
        """
        self._build_dedup_tree(tmp_path)
        result = traverse_ac_tree("ROOT-002", tmp_path)

        count = result.count("ROOT-002a-1-i")
        assert count == 1, (
            f"ROOT-002a-1-i must appear exactly once in result, "
            f"but count == {count}. Full result: {result}"
        )

    def test_ac_acd1200a9i_correct_leaf_set_and_count(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-9-i
        """ACD-1200a-9-i: the leaf set must be exactly {ROOT-002a-1, ROOT-002a-1-i,
        ROOT-002a-2} and the total count must be 3 (no duplicates).

        Buggy code returns len == 4 because ROOT-002a-1-i is appended twice.
        """
        self._build_dedup_tree(tmp_path)
        result = traverse_ac_tree("ROOT-002", tmp_path)

        expected_leaves = {"ROOT-002a-1", "ROOT-002a-1-i", "ROOT-002a-2"}
        assert set(result) == expected_leaves, (
            f"Expected leaf set {expected_leaves}, got: {set(result)}"
        )
        assert len(result) == 3, (
            f"Expected exactly 3 leaves (no duplicates), got {len(result)}: {result}"
        )
