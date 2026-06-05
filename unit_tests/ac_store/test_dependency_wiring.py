"""
MODULE: test_dependency_wiring
GOAL: Unit tests for resolve_leaf_dependencies() and topological_sort() in goal_to_epic.py.
TICKET: EPIC-GoalToEpic/03_dependency-wiring.md
COVERS: ACD-1200c-1, ACD-1200c-1-i, ACD-1200c-2
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from goal_to_epic import resolve_leaf_dependencies, topological_sort  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_ac(
    ac_root: Path,
    ac_id: str,
    depends_on: list[str] | None = None,
    covered_by: list[str] | None = None,
    level: str = "L2",
) -> Path:
    """Write a minimal AC YAML file into *ac_root* and return its path."""
    parts = ac_id.split("-")
    subdir = ac_root / "-".join(parts[:2]) if len(parts) >= 2 else ac_root
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict[str, Any] = {
        "id": ac_id,
        "title": f"AC {ac_id}",
        "level": level,
        "status": "active",
        "work_status": "todo",
        "covered_by": covered_by if covered_by is not None else [],
    }
    if depends_on is not None:
        data["depends_on"] = depends_on
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# ACD-1200c-1: Transitive dependency resolution (leaf-to-leaf edges only)
# ---------------------------------------------------------------------------


class TestResolveLeafDependencies:
    """ACD-1200c-1: resolve_leaf_dependencies produces only leaf-to-leaf edges."""

    def test_ac1_simple_leaf_to_leaf_edge(self, tmp_path: Path) -> None:
        # covers: ACD-1200c-1
        """ACD-1200c-1: Direct leaf-to-leaf dependency is retained as-is."""
        # Leaf B depends on Leaf A (both in generated set)
        _write_ac(tmp_path, "ACD-050a-1", depends_on=[], level="L2")
        _write_ac(tmp_path, "ACD-050a-2", depends_on=["ACD-050a-1"], level="L2")

        leaf_ids = ["ACD-050a-1", "ACD-050a-2"]
        result = resolve_leaf_dependencies(leaf_ids, tmp_path)

        assert result["ACD-050a-2"] == ["ACD-050a-1"], (
            f"ACD-050a-2 should depend on ACD-050a-1 directly, got: {result}"
        )
        assert result["ACD-050a-1"] == [], (
            f"ACD-050a-1 has no leaf deps, got: {result}"
        )

    def test_ac1_transitive_through_composite_ac(self, tmp_path: Path) -> None:
        # covers: ACD-1200c-1
        """ACD-1200c-1: Dependency on composite AC resolves to its leaf descendants."""
        # Composite ACD-050a depends_on leaf ACD-050a-1 transitively
        # Leaf ACD-050a-2-i depends_on composite ACD-050a-2
        # Composite ACD-050a-2 depends_on leaf ACD-050a-1
        # So: ACD-050a-2-i should transitively depend on ACD-050a-1
        _write_ac(tmp_path, "ACD-050a-1", depends_on=[], level="L2")
        _write_ac(
            tmp_path, "ACD-050a-2", depends_on=["ACD-050a-1"],
            covered_by=["ACD-050a-2-i"], level="L1"
        )
        _write_ac(tmp_path, "ACD-050a-2-i", depends_on=["ACD-050a-2"], level="L2")

        leaf_ids = ["ACD-050a-1", "ACD-050a-2-i"]
        result = resolve_leaf_dependencies(leaf_ids, tmp_path)

        assert "ACD-050a-1" in result["ACD-050a-2-i"], (
            f"ACD-050a-2-i should transitively depend on ACD-050a-1 "
            f"through composite ACD-050a-2, got: {result}"
        )

    def test_ac1_composite_dep_not_in_generated_set_is_skipped(self, tmp_path: Path) -> None:
        # covers: ACD-1200c-1
        """ACD-1200c-1: Dependency on a composite AC that has no leaf in the generated set produces no edge."""
        # Leaf ACD-050b-1 depends_on composite ACD-050a (which is NOT a leaf in leaf_ids)
        # And composite ACD-050a doesn't transitively lead to any leaf in leaf_ids
        _write_ac(tmp_path, "ACD-050a", depends_on=[], covered_by=["ACD-050a-1"], level="L1")
        _write_ac(tmp_path, "ACD-050a-1", depends_on=[], level="L2")
        _write_ac(tmp_path, "ACD-050b-1", depends_on=["ACD-050a"], level="L2")

        # Only ACD-050b-1 is in the generated set (ACD-050a-1 is not)
        leaf_ids = ["ACD-050b-1"]
        result = resolve_leaf_dependencies(leaf_ids, tmp_path)

        assert result["ACD-050b-1"] == [], (
            f"No leaf-to-leaf edge should exist when the dep target is not in leaf_ids, got: {result}"
        )

    def test_ac1_only_edges_between_generated_set_members(self, tmp_path: Path) -> None:
        # covers: ACD-1200c-1
        """ACD-1200c-1: Only edges where BOTH endpoints are in leaf_ids are emitted."""
        _write_ac(tmp_path, "ACD-050a-1", depends_on=[], level="L2")
        _write_ac(tmp_path, "ACD-050a-2", depends_on=["ACD-050a-1"], level="L2")
        _write_ac(tmp_path, "ACD-050b-1", depends_on=[], level="L2")

        # Generated set excludes ACD-050a-1 — so ACD-050a-2's dep on it is outside the set
        leaf_ids = ["ACD-050a-2", "ACD-050b-1"]
        result = resolve_leaf_dependencies(leaf_ids, tmp_path)

        # ACD-050a-1 is not in the generated set, so no edge
        assert "ACD-050a-1" not in result.get("ACD-050a-2", []), (
            f"Edge to ACD-050a-1 should be excluded since it's not in leaf_ids, got: {result}"
        )

    def test_ac1_missing_referenced_ac_handled_gracefully(self, tmp_path: Path) -> None:
        # covers: ACD-1200c-1
        """ACD-1200c-1: Unresolvable dependency reference is skipped gracefully."""
        # ACD-050a-2 references a non-existent AC ID in depends_on
        _write_ac(tmp_path, "ACD-050a-1", depends_on=[], level="L2")
        _write_ac(tmp_path, "ACD-050a-2", depends_on=["ACD-NONEXISTENT-999"], level="L2")

        leaf_ids = ["ACD-050a-1", "ACD-050a-2"]
        # Should NOT raise — just skip the unresolvable reference
        result = resolve_leaf_dependencies(leaf_ids, tmp_path)

        assert isinstance(result, dict), "Result must be a dict even with missing deps"
        assert "ACD-050a-1" in result, "ACD-050a-1 must appear in result keys"
        assert "ACD-050a-2" in result, "ACD-050a-2 must appear in result keys"

    def test_ac1_performance_100_leaves_500_edges(self, tmp_path: Path) -> None:
        # covers: ACD-1200c-1
        """ACD-1200c-1: Completes in <500ms for 100 leaves with ~500 dependency edges."""
        # Create 100 leaf ACs where each depends on the previous 5 (500 edges total)
        leaf_ids = [f"ACD-PERF-{i:03d}" for i in range(100)]
        for idx, ac_id in enumerate(leaf_ids):
            # Each leaf depends on the previous min(5, idx) leaves
            deps = leaf_ids[max(0, idx - 5):idx]
            _write_ac(tmp_path, ac_id, depends_on=deps, level="L2")

        start = time.perf_counter()
        result = resolve_leaf_dependencies(leaf_ids, tmp_path)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 500, (
            f"resolve_leaf_dependencies took {elapsed_ms:.1f}ms — exceeded 500ms budget"
        )
        assert len(result) == 100, f"Expected 100 keys, got {len(result)}"

    def test_ac1_result_keys_match_leaf_ids(self, tmp_path: Path) -> None:
        # covers: ACD-1200c-1
        """ACD-1200c-1: The returned dict has exactly one key per leaf_id."""
        _write_ac(tmp_path, "ACD-050a-1", depends_on=[], level="L2")
        _write_ac(tmp_path, "ACD-050b-1", depends_on=[], level="L2")
        _write_ac(tmp_path, "ACD-050c-1", depends_on=["ACD-050a-1"], level="L2")

        leaf_ids = ["ACD-050a-1", "ACD-050b-1", "ACD-050c-1"]
        result = resolve_leaf_dependencies(leaf_ids, tmp_path)

        assert set(result.keys()) == set(leaf_ids), (
            f"Result keys must match leaf_ids exactly, got: {set(result.keys())}"
        )


# ---------------------------------------------------------------------------
# ACD-1200c-1-i: Cycle detection before any file writes
# ---------------------------------------------------------------------------


class TestCycleDetection:
    """ACD-1200c-1-i: Circular dependency detected before any ticket files written."""

    def test_ac1i_simple_cycle_raises(self, tmp_path: Path) -> None:
        # covers: ACD-1200c-1-i
        """ACD-1200c-1-i: Simple 2-node cycle is detected and raises with cycle path."""
        _write_ac(tmp_path, "ACD-050a-1", depends_on=["ACD-050a-2"], level="L2")
        _write_ac(tmp_path, "ACD-050a-2", depends_on=["ACD-050a-1"], level="L2")

        leaf_ids = ["ACD-050a-1", "ACD-050a-2"]
        dep_graph = resolve_leaf_dependencies(leaf_ids, tmp_path)

        with pytest.raises((ValueError, SystemExit)) as exc_info:
            topological_sort(dep_graph)

        exc_str = str(exc_info.value)
        # The error message must contain the cycle path
        assert "ACD-050a-1" in exc_str or "ACD-050a-2" in exc_str, (
            f"Cycle error must name the involved ACs, got: {exc_str}"
        )

    def test_ac1i_three_node_cycle_raises(self, tmp_path: Path) -> None:
        # covers: ACD-1200c-1-i
        """ACD-1200c-1-i: A->B->C->A cycle is detected; error message includes the full path."""
        _write_ac(tmp_path, "ACD-050a-1", depends_on=["ACD-050a-3"], level="L2")
        _write_ac(tmp_path, "ACD-050a-2", depends_on=["ACD-050a-1"], level="L2")
        _write_ac(tmp_path, "ACD-050a-3", depends_on=["ACD-050a-2"], level="L2")

        leaf_ids = ["ACD-050a-1", "ACD-050a-2", "ACD-050a-3"]
        dep_graph = resolve_leaf_dependencies(leaf_ids, tmp_path)

        with pytest.raises((ValueError, SystemExit)) as exc_info:
            topological_sort(dep_graph)

        exc_str = str(exc_info.value)
        # Must mention "Circular dependency" (or similar) and include AC IDs
        assert any(kw in exc_str for kw in ["Circular", "cycle", "circular"]), (
            f"Error must use 'Circular dependency' or 'cycle' language, got: {exc_str!r}"
        )

    def test_ac1i_cycle_message_contains_full_path(self, tmp_path: Path) -> None:
        # covers: ACD-1200c-1-i
        """ACD-1200c-1-i: Cycle error contains the full cycle path (all nodes)."""
        _write_ac(tmp_path, "ACD-050a-1", depends_on=["ACD-050a-3"], level="L2")
        _write_ac(tmp_path, "ACD-050a-2", depends_on=["ACD-050a-1"], level="L2")
        _write_ac(tmp_path, "ACD-050a-3", depends_on=["ACD-050a-2"], level="L2")

        leaf_ids = ["ACD-050a-1", "ACD-050a-2", "ACD-050a-3"]
        dep_graph = resolve_leaf_dependencies(leaf_ids, tmp_path)

        with pytest.raises((ValueError, SystemExit)) as exc_info:
            topological_sort(dep_graph)

        exc_str = str(exc_info.value)
        # All 3 nodes of the cycle should appear in the error message
        cycle_nodes_found = sum(
            1 for ac_id in ["ACD-050a-1", "ACD-050a-2", "ACD-050a-3"]
            if ac_id in exc_str
        )
        assert cycle_nodes_found >= 2, (
            f"At least 2 of the 3 cycle nodes must appear in the error, got: {exc_str!r}"
        )

    def test_ac1i_cycle_detection_before_file_writes(self, tmp_path: Path) -> None:
        # covers: ACD-1200c-1-i
        """ACD-1200c-1-i: Cycle detected without writing any files (pre-write guard)."""
        _write_ac(tmp_path, "ACD-050a-1", depends_on=["ACD-050a-2"], level="L2")
        _write_ac(tmp_path, "ACD-050a-2", depends_on=["ACD-050a-1"], level="L2")

        leaf_ids = ["ACD-050a-1", "ACD-050a-2"]
        dep_graph = resolve_leaf_dependencies(leaf_ids, tmp_path)

        output_dir = tmp_path / "epic_output"

        with pytest.raises((ValueError, SystemExit)):
            topological_sort(dep_graph)

        # No epic folder should be created
        assert not output_dir.exists(), (
            "No epic folder should exist when a cycle is detected"
        )

    def test_ac1i_no_cycle_does_not_raise(self, tmp_path: Path) -> None:
        # covers: ACD-1200c-1-i
        """ACD-1200c-1-i: Acyclic graph does not raise on topological_sort."""
        _write_ac(tmp_path, "ACD-050a-1", depends_on=[], level="L2")
        _write_ac(tmp_path, "ACD-050a-2", depends_on=["ACD-050a-1"], level="L2")
        _write_ac(tmp_path, "ACD-050a-3", depends_on=["ACD-050a-2"], level="L2")

        leaf_ids = ["ACD-050a-1", "ACD-050a-2", "ACD-050a-3"]
        dep_graph = resolve_leaf_dependencies(leaf_ids, tmp_path)

        # Must not raise for an acyclic graph
        result = topological_sort(dep_graph)
        assert isinstance(result, list), "topological_sort must return a list for acyclic input"


# ---------------------------------------------------------------------------
# ACD-1200c-2: Topological ordering — multi-hop chains and diamond deps
# ---------------------------------------------------------------------------


class TestTopologicalSort:
    """ACD-1200c-2: Topological sort produces correct ordering for multi-hop and diamond deps."""

    def test_ac2_linear_chain_ordering(self, tmp_path: Path) -> None:
        # covers: ACD-1200c-2
        """ACD-1200c-2: 4-node chain A<-B<-C<-D produces ordering A,B,C,D."""
        _write_ac(tmp_path, "ACD-050a-1", depends_on=[], level="L2")
        _write_ac(tmp_path, "ACD-050a-2", depends_on=["ACD-050a-1"], level="L2")
        _write_ac(tmp_path, "ACD-050a-3", depends_on=["ACD-050a-2"], level="L2")
        _write_ac(tmp_path, "ACD-050a-4", depends_on=["ACD-050a-3"], level="L2")

        leaf_ids = ["ACD-050a-1", "ACD-050a-2", "ACD-050a-3", "ACD-050a-4"]
        dep_graph = resolve_leaf_dependencies(leaf_ids, tmp_path)
        order = topological_sort(dep_graph)

        # Verify topological correctness: each AC appears before ACs that depend on it
        idx = {ac: i for i, ac in enumerate(order)}
        assert idx["ACD-050a-1"] < idx["ACD-050a-2"], "ACD-050a-1 must come before ACD-050a-2"
        assert idx["ACD-050a-2"] < idx["ACD-050a-3"], "ACD-050a-2 must come before ACD-050a-3"
        assert idx["ACD-050a-3"] < idx["ACD-050a-4"], "ACD-050a-3 must come before ACD-050a-4"

    def test_ac2_monotonically_increasing_prefixes(self, tmp_path: Path) -> None:
        # covers: ACD-1200c-2
        """ACD-1200c-2: Topological order maps to monotonically increasing numeric prefixes."""
        _write_ac(tmp_path, "ACD-050a-1", depends_on=[], level="L2")
        _write_ac(tmp_path, "ACD-050a-2", depends_on=["ACD-050a-1"], level="L2")
        _write_ac(tmp_path, "ACD-050a-3", depends_on=["ACD-050a-2"], level="L2")

        leaf_ids = ["ACD-050a-1", "ACD-050a-2", "ACD-050a-3"]
        dep_graph = resolve_leaf_dependencies(leaf_ids, tmp_path)
        order = topological_sort(dep_graph)

        prefixes = [i + 1 for i in range(len(order))]
        for i in range(len(prefixes) - 1):
            assert prefixes[i] < prefixes[i + 1], (
                f"Numeric prefixes must be monotonically increasing, got: {prefixes}"
            )

    def test_ac2_deterministic_across_repeated_runs(self, tmp_path: Path) -> None:
        # covers: ACD-1200c-2
        """ACD-1200c-2: Same input produces identical ordering on repeated calls."""
        _write_ac(tmp_path, "ACD-050a-1", depends_on=[], level="L2")
        _write_ac(tmp_path, "ACD-050a-2", depends_on=["ACD-050a-1"], level="L2")
        _write_ac(tmp_path, "ACD-050a-3", depends_on=["ACD-050a-1"], level="L2")

        leaf_ids = ["ACD-050a-1", "ACD-050a-2", "ACD-050a-3"]
        dep_graph = resolve_leaf_dependencies(leaf_ids, tmp_path)

        order_1 = topological_sort(dep_graph)
        order_2 = topological_sort(dep_graph)

        assert order_1 == order_2, (
            f"topological_sort must be deterministic; got different results:\n"
            f"  run 1: {order_1}\n  run 2: {order_2}"
        )

    def test_ac2_diamond_dependency_no_duplicates(self, tmp_path: Path) -> None:
        # covers: ACD-1200c-2
        """ACD-1200c-2: Diamond dependency A->B, A->C, B->D, C->D produces no duplicate entries."""
        # Diamond: D depends on B and C; B and C both depend on A
        _write_ac(tmp_path, "ACD-050a-1", depends_on=[], level="L2")           # A
        _write_ac(tmp_path, "ACD-050a-2", depends_on=["ACD-050a-1"], level="L2")  # B
        _write_ac(tmp_path, "ACD-050a-3", depends_on=["ACD-050a-1"], level="L2")  # C
        _write_ac(tmp_path, "ACD-050a-4",
                  depends_on=["ACD-050a-2", "ACD-050a-3"], level="L2")  # D

        leaf_ids = ["ACD-050a-1", "ACD-050a-2", "ACD-050a-3", "ACD-050a-4"]
        dep_graph = resolve_leaf_dependencies(leaf_ids, tmp_path)
        order = topological_sort(dep_graph)

        assert len(order) == len(set(order)), (
            f"topological_sort must not produce duplicates with diamond deps, got: {order}"
        )
        assert len(order) == 4, (
            f"Expected exactly 4 items in the order, got: {order}"
        )

    def test_ac2_diamond_dep_order_constraints(self, tmp_path: Path) -> None:
        # covers: ACD-1200c-2
        """ACD-1200c-2: Diamond dep ordering respects all edge constraints."""
        _write_ac(tmp_path, "ACD-050a-1", depends_on=[], level="L2")
        _write_ac(tmp_path, "ACD-050a-2", depends_on=["ACD-050a-1"], level="L2")
        _write_ac(tmp_path, "ACD-050a-3", depends_on=["ACD-050a-1"], level="L2")
        _write_ac(tmp_path, "ACD-050a-4",
                  depends_on=["ACD-050a-2", "ACD-050a-3"], level="L2")

        leaf_ids = ["ACD-050a-1", "ACD-050a-2", "ACD-050a-3", "ACD-050a-4"]
        dep_graph = resolve_leaf_dependencies(leaf_ids, tmp_path)
        order = topological_sort(dep_graph)
        idx = {ac: i for i, ac in enumerate(order)}

        assert idx["ACD-050a-1"] < idx["ACD-050a-2"], "A must precede B"
        assert idx["ACD-050a-1"] < idx["ACD-050a-3"], "A must precede C"
        assert idx["ACD-050a-2"] < idx["ACD-050a-4"], "B must precede D"
        assert idx["ACD-050a-3"] < idx["ACD-050a-4"], "C must precede D"

    def test_ac2_all_nodes_in_result(self, tmp_path: Path) -> None:
        # covers: ACD-1200c-2
        """ACD-1200c-2: topological_sort returns all nodes in leaf_ids."""
        _write_ac(tmp_path, "ACD-050a-1", depends_on=[], level="L2")
        _write_ac(tmp_path, "ACD-050a-2", depends_on=["ACD-050a-1"], level="L2")

        leaf_ids = ["ACD-050a-1", "ACD-050a-2"]
        dep_graph = resolve_leaf_dependencies(leaf_ids, tmp_path)
        order = topological_sort(dep_graph)

        assert set(order) == set(leaf_ids), (
            f"topological_sort must return all nodes, got: {order}"
        )

    def test_ac2_independent_nodes_all_returned(self, tmp_path: Path) -> None:
        # covers: ACD-1200c-2
        """ACD-1200c-2: When there are no dependencies, all nodes are in the result."""
        _write_ac(tmp_path, "ACD-050a-1", depends_on=[], level="L2")
        _write_ac(tmp_path, "ACD-050b-1", depends_on=[], level="L2")
        _write_ac(tmp_path, "ACD-050c-1", depends_on=[], level="L2")

        leaf_ids = ["ACD-050a-1", "ACD-050b-1", "ACD-050c-1"]
        dep_graph = resolve_leaf_dependencies(leaf_ids, tmp_path)
        order = topological_sort(dep_graph)

        assert set(order) == set(leaf_ids), (
            f"All independent nodes must appear in the result, got: {order}"
        )
        assert len(order) == 3
