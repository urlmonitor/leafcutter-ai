"""
MODULE: test_tree_traversal
GOAL: Unit tests for traverse_ac_tree() in scan_ac_store.py.
TICKET: EPIC-GoalToEpic/01_tree-traversal-ticket-generation.md
COVERS: ACD-1200a-1, ACD-1200a-1-i
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

import pytest
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


# ---------------------------------------------------------------------------
# ACD-1200a-1: leaf collection from mixed tree
# ---------------------------------------------------------------------------


class TestTraverseAcTreeLeafCollection:
    """AC-1: tree traversal returns only leaf ACs from a mixed tree."""

    def test_ac1_leaf_only_returned_from_mixed_tree(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-1
        """AC-1: Given a goal AC with L0->L1s->L2s->L3s, traversal returns only leaves."""
        # Build tree: L0 -> L1a, L1b; L1a -> L2a, L2b; L2a -> L3a
        _write_ac(tmp_path, "ACD-050", covered_by=["ACD-050a", "ACD-050b"])
        _write_ac(tmp_path, "ACD-050a", covered_by=["ACD-050a-1", "ACD-050a-2"])
        _write_ac(tmp_path, "ACD-050b", covered_by=["ACD-050b-1"])
        _write_ac(tmp_path, "ACD-050a-1", covered_by=["ACD-050a-1-i"])
        _write_ac(tmp_path, "ACD-050a-2", covered_by=[])  # leaf
        _write_ac(tmp_path, "ACD-050a-1-i", covered_by=[])  # leaf
        _write_ac(tmp_path, "ACD-050b-1", covered_by=[])  # leaf

        result = traverse_ac_tree("ACD-050", tmp_path)

        # Only leaves should be returned
        assert set(result) == {"ACD-050a-1-i", "ACD-050a-2", "ACD-050b-1"}, (
            f"Expected only leaf ACs, got: {result}"
        )

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
        # covers: ACD-1200a-1
        """AC-1: Leaves returned in depth-first, alphabetical-sibling order."""
        _write_ac(tmp_path, "ACD-050", covered_by=["ACD-050b", "ACD-050a"])
        _write_ac(tmp_path, "ACD-050a", covered_by=["ACD-050a-2", "ACD-050a-1"])
        _write_ac(tmp_path, "ACD-050b", covered_by=[])  # leaf
        _write_ac(tmp_path, "ACD-050a-1", covered_by=[])  # leaf
        _write_ac(tmp_path, "ACD-050a-2", covered_by=[])  # leaf

        result = traverse_ac_tree("ACD-050", tmp_path)

        # depth-first alphabetical: ACD-050a (alpha first) -> ACD-050a-1, ACD-050a-2, then ACD-050b
        assert result == ["ACD-050a-1", "ACD-050a-2", "ACD-050b"], (
            f"Expected depth-first alphabetical order, got: {result}"
        )

    def test_ac1_performance_200_nodes(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-1
        """AC-1: Traversal completes in under 200ms for trees up to 200 nodes."""
        # Build a wide tree: root -> 10 L1s -> 19 L2 leaves each = 200 nodes
        root_children = [f"ACD-PERF-{i:03d}" for i in range(10)]
        _write_ac(tmp_path, "ACD-PERF", covered_by=root_children)
        for child in root_children:
            grandchildren = [f"{child}-{j:03d}" for j in range(19)]
            _write_ac(tmp_path, child, covered_by=grandchildren)
            for gc in grandchildren:
                _write_ac(tmp_path, gc, covered_by=[])

        start = time.perf_counter()
        result = traverse_ac_tree("ACD-PERF", tmp_path)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert len(result) == 190, f"Expected 190 leaf ACs, got {len(result)}"
        assert elapsed_ms < 200, f"Traversal took {elapsed_ms:.1f}ms — exceeded 200ms budget"

    def test_ac1_absent_covered_by_treated_as_leaf(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-1
        """AC-1: ACs without a covered_by field are treated as leaves."""
        _write_ac(tmp_path, "ACD-050", covered_by=["ACD-050a"])
        # Write ACD-050a WITHOUT covered_by field (absent, not empty list)
        subdir = tmp_path / "ACD-050"
        subdir.mkdir(parents=True, exist_ok=True)
        yaml_path = subdir / "ACD-050a.yaml"
        data = {"id": "ACD-050a", "title": "AC ACD-050a", "level": "L1", "status": "active", "work_status": "todo"}
        # Note: no covered_by key at all
        yaml_path.write_text(yaml.dump(data), encoding="utf-8")

        result = traverse_ac_tree("ACD-050", tmp_path)
        assert "ACD-050a" in result, "AC with absent covered_by should be treated as leaf"


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

    def test_ac1i_leaf_l1_returns_itself(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-1-i
        """ACD-1200a-1-i: When the scoped root is itself a leaf, return just it."""
        _write_ac(tmp_path, "ACD-050", covered_by=["ACD-050a"])
        _write_ac(tmp_path, "ACD-050a", covered_by=[])  # leaf L1

        result = traverse_ac_tree("ACD-050a", tmp_path)

        assert result == ["ACD-050a"], (
            f"A leaf L1 used as scope root should return only itself, got {result}"
        )
