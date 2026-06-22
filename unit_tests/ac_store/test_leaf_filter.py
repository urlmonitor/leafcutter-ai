"""
MODULE: test_leaf_filter
GOAL: Unit tests for the exclude_done / exclude_superseded parameters added to
      traverse_ac_tree() and _dfs_collect_leaves() in scan_ac_store.py.
TICKET: EPIC-GoalToEpicLeafFilter/01_TICKET-20260622-ACD-1200a-10.md
COVERS: ACD-1200a-10

These tests are intentionally RED until python-coder implements the two new
keyword parameters on traverse_ac_tree() (and propagates them into
_dfs_collect_leaves()).

Tree fixture used throughout (mirrors the Gherkin AC exactly):

    ACD-070          L0/L1  covered_by: [ACD-070a, ACD-070b]
    ACD-070a         L1     covered_by: [ACD-070a-1, ACD-070a-2]
    ACD-070b         L1     covered_by: [ACD-070b-1]
    ACD-070a-1       L2     status: active,      work_status: done
    ACD-070a-2       L2     status: active,      work_status: todo
    ACD-070b-1       L2     status: superseded,  superseded_by: [...],
                                                 covered_by: [ACD-070b-1a, ACD-070b-1b]
    ACD-070b-1a      L2     status: active,      work_status: todo
    ACD-070b-1b      L2     status: active,      work_status: todo

The five leaf nodes are:
    ACD-070a-1, ACD-070a-2, ACD-070b-1, ACD-070b-1a, ACD-070b-1b
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from scan_ac_store import traverse_ac_tree  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_ac(
    ac_root: Path,
    ac_id: str,
    level: str,
    status: str = "active",
    work_status: str = "todo",
    covered_by: list[str] | None = None,
    superseded_by: list[str] | None = None,
) -> Path:
    """Write one AC YAML file into *ac_root* and return its path."""
    parts = ac_id.split("-")
    subdir = ac_root / "-".join(parts[:2]) if len(parts) >= 2 else ac_root
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict = {
        "id": ac_id,
        "title": f"Test AC {ac_id}",
        "level": level,
        "status": status,
        "work_status": work_status,
        "covered_by": covered_by if covered_by is not None else [],
    }
    if superseded_by is not None:
        data["superseded_by"] = superseded_by
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _build_fixture_tree(ac_root: Path) -> None:
    """Populate *ac_root* with the five-leaf ACD-070 tree from the ticket Gherkin."""
    # Composite nodes
    _write_ac(ac_root, "ACD-070", "L0", covered_by=["ACD-070a", "ACD-070b"])
    _write_ac(ac_root, "ACD-070a", "L1", covered_by=["ACD-070a-1", "ACD-070a-2"])
    _write_ac(ac_root, "ACD-070b", "L1", covered_by=["ACD-070b-1"])

    # Leaf: active + done  →  excluded when exclude_done=True
    _write_ac(
        ac_root,
        "ACD-070a-1",
        "L2",
        status="active",
        work_status="done",
    )

    # Leaf: active + todo  →  always included
    _write_ac(
        ac_root,
        "ACD-070a-2",
        "L2",
        status="active",
        work_status="todo",
    )

    # Leaf: superseded  →  excluded from result when exclude_superseded=True,
    # but traversal MUST still recurse into its covered_by children.
    _write_ac(
        ac_root,
        "ACD-070b-1",
        "L2",
        status="superseded_by",
        work_status="todo",
        covered_by=["ACD-070b-1a", "ACD-070b-1b"],
        superseded_by=["ACD-070b-1a", "ACD-070b-1b"],
    )

    # Replacement children of the superseded leaf
    _write_ac(ac_root, "ACD-070b-1a", "L2", status="active", work_status="todo")
    _write_ac(ac_root, "ACD-070b-1b", "L2", status="active", work_status="todo")


# ---------------------------------------------------------------------------
# ACD-1200a-10: default exclusion behaviour
# ---------------------------------------------------------------------------


class TestLeafFilterDefaults:
    """ACD-1200a-10: default flags (exclude_done=True, exclude_superseded=True)."""

    def test_ac1200a10_done_leaf_excluded_by_default(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-10
        """ACD-1200a-10: ACD-070a-1 (work_status: done) must NOT appear in the
        default result because exclude_done defaults to True."""
        _build_fixture_tree(tmp_path)
        result = traverse_ac_tree("ACD-070", tmp_path, exclude_done=True)
        assert "ACD-070a-1" not in result, (
            f"Done AC ACD-070a-1 must be excluded when exclude_done=True. "
            f"Got: {result}"
        )

    def test_ac1200a10_superseded_leaf_excluded_by_default(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-10
        """ACD-1200a-10: ACD-070b-1 (status: superseded_by) must NOT appear
        in the default result because exclude_superseded defaults to True."""
        _build_fixture_tree(tmp_path)
        result = traverse_ac_tree("ACD-070", tmp_path, exclude_superseded=True)
        assert "ACD-070b-1" not in result, (
            f"Superseded AC ACD-070b-1 must be excluded when exclude_superseded=True. "
            f"Got: {result}"
        )

    def test_ac1200a10_active_todo_leaf_always_included(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-10
        """ACD-1200a-10: ACD-070a-2 (active + todo) must be in the result when
        both default exclusion flags are active (exclude_done=True,
        exclude_superseded=True).  This requires the new keyword arguments to
        exist — the call fails with TypeError until python-coder implements them."""
        _build_fixture_tree(tmp_path)
        result = traverse_ac_tree(
            "ACD-070", tmp_path, exclude_done=True, exclude_superseded=True
        )
        assert "ACD-070a-2" in result, (
            f"Active todo AC ACD-070a-2 must be in the result. Got: {result}"
        )

    def test_ac1200a10_superseded_replacement_children_collected(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-10
        """ACD-1200a-10: Even though ACD-070b-1 is excluded (exclude_superseded=True),
        traversal MUST recurse into its covered_by children so ACD-070b-1a and
        ACD-070b-1b are collected.  Requires the new keyword arguments — fails
        with TypeError until implemented."""
        _build_fixture_tree(tmp_path)
        result = traverse_ac_tree(
            "ACD-070", tmp_path, exclude_done=True, exclude_superseded=True
        )
        assert "ACD-070b-1a" in result, (
            f"Replacement child ACD-070b-1a must be in result even though "
            f"its superseded parent ACD-070b-1 is excluded. Got: {result}"
        )
        assert "ACD-070b-1b" in result, (
            f"Replacement child ACD-070b-1b must be in result even though "
            f"its superseded parent ACD-070b-1 is excluded. Got: {result}"
        )

    def test_ac1200a10_default_result_is_three_leaves(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-10
        """ACD-1200a-10: With default flags the result must contain exactly
        ACD-070a-2, ACD-070b-1a, ACD-070b-1b (3 leaves)."""
        _build_fixture_tree(tmp_path)
        result = traverse_ac_tree("ACD-070", tmp_path)
        expected = {"ACD-070a-2", "ACD-070b-1a", "ACD-070b-1b"}
        assert set(result) == expected, (
            f"Default result must be {expected}. Got: {set(result)}"
        )


# ---------------------------------------------------------------------------
# ACD-1200a-10: both flags False reproduces prior unfiltered behaviour
# ---------------------------------------------------------------------------


class TestLeafFilterBothFlagsOff:
    """ACD-1200a-10: both flags False returns all five leaf ACs."""

    def test_ac1200a10_both_false_returns_all_five(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-10
        """ACD-1200a-10: When exclude_done=False and exclude_superseded=False,
        all five ACs are returned (prior unfiltered behaviour is preserved)."""
        _build_fixture_tree(tmp_path)
        result = traverse_ac_tree(
            "ACD-070", tmp_path, exclude_done=False, exclude_superseded=False
        )
        expected = {
            "ACD-070a-1",
            "ACD-070a-2",
            "ACD-070b-1",
            "ACD-070b-1a",
            "ACD-070b-1b",
        }
        assert set(result) == expected, (
            f"With both flags False the result must contain all five ACs. "
            f"Got: {set(result)}"
        )

    def test_ac1200a10_both_false_count_is_five(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-10
        """ACD-1200a-10: result count with both flags False must be 5 (no
        duplicates, no suppressions)."""
        _build_fixture_tree(tmp_path)
        result = traverse_ac_tree(
            "ACD-070", tmp_path, exclude_done=False, exclude_superseded=False
        )
        assert len(result) == 5, (
            f"Expected 5 leaves when all exclusions off; got {len(result)}: {result}"
        )


# ---------------------------------------------------------------------------
# ACD-1200a-10: individual flag toggling
# ---------------------------------------------------------------------------


class TestLeafFilterIndividualFlags:
    """ACD-1200a-10: flags are independently configurable."""

    def test_ac1200a10_exclude_done_false_keeps_done_ac(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-10
        """ACD-1200a-10: exclude_done=False, exclude_superseded=True —
        done ACs are kept; superseded AC is still excluded."""
        _build_fixture_tree(tmp_path)
        result = traverse_ac_tree(
            "ACD-070", tmp_path, exclude_done=False, exclude_superseded=True
        )
        assert "ACD-070a-1" in result, (
            f"Done AC ACD-070a-1 must be in result when exclude_done=False. "
            f"Got: {result}"
        )
        assert "ACD-070b-1" not in result, (
            f"Superseded AC ACD-070b-1 must still be excluded when "
            f"exclude_superseded=True. Got: {result}"
        )

    def test_ac1200a10_exclude_superseded_false_keeps_superseded_ac(
        self, tmp_path: Path
    ) -> None:
        # covers: ACD-1200a-10
        """ACD-1200a-10: exclude_superseded=False, exclude_done=True —
        superseded AC is kept in result; done AC is still excluded."""
        _build_fixture_tree(tmp_path)
        result = traverse_ac_tree(
            "ACD-070", tmp_path, exclude_done=True, exclude_superseded=False
        )
        assert "ACD-070b-1" in result, (
            f"Superseded AC ACD-070b-1 must be in result when "
            f"exclude_superseded=False. Got: {result}"
        )
        assert "ACD-070a-1" not in result, (
            f"Done AC ACD-070a-1 must still be excluded when "
            f"exclude_done=True. Got: {result}"
        )

    def test_ac1200a10_no_arg_uses_true_defaults(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-10
        """ACD-1200a-10: calling traverse_ac_tree with NO flag arguments must
        behave identically to exclude_done=True, exclude_superseded=True
        (the parameters default to True)."""
        _build_fixture_tree(tmp_path)
        result_no_args = traverse_ac_tree("ACD-070", tmp_path)
        result_explicit = traverse_ac_tree(
            "ACD-070", tmp_path, exclude_done=True, exclude_superseded=True
        )
        assert result_no_args == result_explicit, (
            f"Default call and explicit-True call must produce identical results. "
            f"no_args={result_no_args}, explicit={result_explicit}"
        )
