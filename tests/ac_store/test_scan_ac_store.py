"""
MODULE: tests/ac_store/test_scan_ac_store.py
GOAL: Verify that scan_ac_store.py correctly filters, resolves dependencies,
      sorts, and outputs AC records in both human-readable and JSON formats.
BUSINESS CONTEXT: Tickets 01 AC-1 and AC-5. The scanner is the first step of
    the AC-driven build pipeline. It must return only leaf-level (L2/L3), active,
    todo, unblocked ACs, sorted by estimated_complexity then id. JSON output must
    conform to the schema defined in AC-5.
ARCHITECTURE: Integration tests using temporary fixture directories. Each test
    creates a minimal YAML store in a tmp_path, invokes scan_ac_store.py via
    subprocess, and asserts on stdout/exit-code.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
SCAN_SCRIPT = WORKTREE_ROOT / "scripts" / "ac_store" / "scan_ac_store.py"


def _write_ac(directory: Path, filename: str, data: dict) -> Path:
    """Write a YAML AC file and return the path.

    Automatically injects readiness: approved and priority: medium if not
    present, so test fixtures work correctly with the readiness gate introduced
    in ticket 00 (scanner ignores ACs without readiness: approved).
    """
    merged = {"readiness": "approved", "priority": "medium"}
    merged.update(data)
    p = directory / filename
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(p, "w", encoding="utf-8") as fh:
            yaml.dump(merged, fh, default_flow_style=False, allow_unicode=True)
    except OSError as exc:
        raise RuntimeError(f"Failed to write AC fixture {p}: {exc}") from exc
    return p


def _run_scan(ac_root: Path, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    """Invoke scan_ac_store.py with --level leaf --work-status todo."""
    cmd = [
        sys.executable,
        str(SCAN_SCRIPT),
        "--level", "leaf",
        "--work-status", "todo",
        "--ac-root", str(ac_root),
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30)


class TestScanAcStoreLeafFilter:
    """AC-1: Leaf scanner identifies todo, unblocked L2/L3 ACs."""

    def test_leaf_filter_excludes_l0_l1(self, tmp_path: Path) -> None:
        """test_leaf_filter_excludes_l0_l1: Only L2/L3 ACs appear in the READY list."""
        ac_dir = tmp_path / "ac_store"
        _write_ac(ac_dir, "L0-root.yaml", {
            "id": "L0-001", "title": "Root", "component": "test", "level": "L0",
            "status": "active", "work_status": "todo", "criteria": "Given x",
            "assigned_agent": "python-coder", "estimated_complexity": "S",
            "depends_on": [],
        })
        _write_ac(ac_dir, "L1-parent.yaml", {
            "id": "L1-001", "title": "Parent", "component": "test", "level": "L1",
            "status": "active", "work_status": "todo", "criteria": "Given y",
            "assigned_agent": "python-coder", "estimated_complexity": "S",
            "depends_on": [],
        })
        _write_ac(ac_dir, "L2-leaf.yaml", {
            "id": "L2-001", "title": "Leaf", "component": "test", "level": "L2",
            "status": "active", "work_status": "todo", "criteria": "Given z",
            "assigned_agent": "python-coder", "estimated_complexity": "S",
            "depends_on": [],
        })

        result = _run_scan(ac_dir, ["--json"])
        assert result.returncode == 0, f"Scanner exited non-zero: {result.stderr}"
        output = json.loads(result.stdout)
        ready_ids = [ac["ac_id"] for ac in output["ready"]]
        assert "L2-001" in ready_ids, "L2 AC should appear in ready list"
        assert "L0-001" not in ready_ids, "L0 AC must be excluded"
        assert "L1-001" not in ready_ids, "L1 AC must be excluded"

    def test_l3_leaf_included(self, tmp_path: Path) -> None:
        """L3 ACs are also leaf-level and must appear in READY."""
        ac_dir = tmp_path / "ac_store"
        _write_ac(ac_dir, "L3-leaf.yaml", {
            "id": "L3-001", "title": "L3 Leaf", "component": "test", "level": "L3",
            "status": "active", "work_status": "todo", "criteria": "Given a",
            "assigned_agent": "python-coder", "estimated_complexity": "S",
            "depends_on": [],
        })
        result = _run_scan(ac_dir, ["--json"])
        assert result.returncode == 0, f"Scanner failed: {result.stderr}"
        output = json.loads(result.stdout)
        ready_ids = [ac["ac_id"] for ac in output["ready"]]
        assert "L3-001" in ready_ids

    def test_inactive_ac_excluded(self, tmp_path: Path) -> None:
        """ACs with status != active are excluded from output."""
        ac_dir = tmp_path / "ac_store"
        _write_ac(ac_dir, "inactive.yaml", {
            "id": "L2-002", "title": "Inactive", "component": "test", "level": "L2",
            "status": "draft", "work_status": "todo", "criteria": "Given b",
            "assigned_agent": "python-coder", "estimated_complexity": "S",
            "depends_on": [],
        })
        result = _run_scan(ac_dir, ["--json"])
        assert result.returncode == 0, f"Scanner failed: {result.stderr}"
        output = json.loads(result.stdout)
        ready_ids = [ac["ac_id"] for ac in output["ready"]]
        assert "L2-002" not in ready_ids, "Inactive ACs must not appear in ready list"

    def test_done_ac_excluded(self, tmp_path: Path) -> None:
        """ACs with work_status: done are excluded (not todo)."""
        ac_dir = tmp_path / "ac_store"
        _write_ac(ac_dir, "done.yaml", {
            "id": "L2-003", "title": "Done", "component": "test", "level": "L2",
            "status": "active", "work_status": "done", "criteria": "Given c",
            "assigned_agent": "python-coder", "estimated_complexity": "S",
            "depends_on": [],
        })
        result = _run_scan(ac_dir, ["--json"])
        assert result.returncode == 0, f"Scanner failed: {result.stderr}"
        output = json.loads(result.stdout)
        ready_ids = [ac["ac_id"] for ac in output["ready"]]
        assert "L2-003" not in ready_ids, "Done ACs must not appear in ready list"


class TestScanAcStoreDependencyResolution:
    """AC-1: Dependency-blocked ACs appear in the blocked list, not ready."""

    def test_blocked_ac_excluded_when_dep_not_done(self, tmp_path: Path) -> None:
        """test_blocked_ac_excluded_when_dep_not_done: AC with a todo dep is blocked."""
        ac_dir = tmp_path / "ac_store"
        _write_ac(ac_dir, "dep.yaml", {
            "id": "L2-DEP", "title": "Dep", "component": "test", "level": "L2",
            "status": "active", "work_status": "todo", "criteria": "Given dep",
            "assigned_agent": "python-coder", "estimated_complexity": "S",
            "depends_on": [],
        })
        _write_ac(ac_dir, "blocked.yaml", {
            "id": "L2-BLOCKED", "title": "Blocked", "component": "test", "level": "L2",
            "status": "active", "work_status": "todo", "criteria": "Given blocked",
            "assigned_agent": "python-coder", "estimated_complexity": "S",
            "depends_on": ["L2-DEP"],
        })

        result = _run_scan(ac_dir, ["--json"])
        assert result.returncode == 0, f"Scanner failed: {result.stderr}"
        output = json.loads(result.stdout)
        ready_ids = [ac["ac_id"] for ac in output["ready"]]
        blocked_ids = [ac["ac_id"] for ac in output["blocked"]]
        assert "L2-BLOCKED" not in ready_ids, "AC with unresolved dep must not be ready"
        assert "L2-BLOCKED" in blocked_ids, "AC with unresolved dep must appear in blocked"

    def test_unblocked_ac_included_when_dep_done(self, tmp_path: Path) -> None:
        """test_unblocked_ac_included_when_dep_done: AC with all deps done is ready."""
        ac_dir = tmp_path / "ac_store"
        _write_ac(ac_dir, "done_dep.yaml", {
            "id": "L2-DONE-DEP", "title": "Done Dep", "component": "test", "level": "L2",
            "status": "active", "work_status": "done", "criteria": "Given done-dep",
            "assigned_agent": "python-coder", "estimated_complexity": "S",
            "depends_on": [],
        })
        _write_ac(ac_dir, "ready.yaml", {
            "id": "L2-READY", "title": "Ready", "component": "test", "level": "L2",
            "status": "active", "work_status": "todo", "criteria": "Given ready",
            "assigned_agent": "python-coder", "estimated_complexity": "S",
            "depends_on": ["L2-DONE-DEP"],
        })

        result = _run_scan(ac_dir, ["--json"])
        assert result.returncode == 0, f"Scanner failed: {result.stderr}"
        output = json.loads(result.stdout)
        ready_ids = [ac["ac_id"] for ac in output["ready"]]
        assert "L2-READY" in ready_ids, "AC with all deps done must appear in ready"

    def test_blocked_by_list_contains_dep_id(self, tmp_path: Path) -> None:
        """blocked[*].blocked_by must list the id of the blocking dependency."""
        ac_dir = tmp_path / "ac_store"
        _write_ac(ac_dir, "dep.yaml", {
            "id": "L2-BK-DEP", "title": "Blocker", "component": "test", "level": "L2",
            "status": "active", "work_status": "todo", "criteria": "Given bk-dep",
            "assigned_agent": "python-coder", "estimated_complexity": "S",
            "depends_on": [],
        })
        _write_ac(ac_dir, "blocked.yaml", {
            "id": "L2-BK-CHILD", "title": "Blocked Child", "component": "test", "level": "L2",
            "status": "active", "work_status": "todo", "criteria": "Given bk-child",
            "assigned_agent": "python-coder", "estimated_complexity": "S",
            "depends_on": ["L2-BK-DEP"],
        })

        result = _run_scan(ac_dir, ["--json"])
        assert result.returncode == 0, f"Scanner failed: {result.stderr}"
        output = json.loads(result.stdout)
        blocked_entry = next(
            (ac for ac in output["blocked"] if ac["ac_id"] == "L2-BK-CHILD"), None
        )
        assert blocked_entry is not None, "L2-BK-CHILD must appear in blocked list"
        assert "L2-BK-DEP" in blocked_entry.get("blocked_by", []), (
            "blocked_by must contain the id of the blocking dep"
        )


class TestScanAcStoreSorting:
    """AC-1: Output is sorted by estimated_complexity ascending then ac_id ascending."""

    def test_sort_by_complexity_ascending(self, tmp_path: Path) -> None:
        """Ready list is sorted: S < M < L < XL, then id ascending within each tier."""
        ac_dir = tmp_path / "ac_store"
        _write_ac(ac_dir, "xl.yaml", {
            "id": "L2-XL", "title": "XL task", "component": "test", "level": "L2",
            "status": "active", "work_status": "todo", "criteria": "Given xl",
            "assigned_agent": "python-coder", "estimated_complexity": "XL",
            "depends_on": [],
        })
        _write_ac(ac_dir, "m.yaml", {
            "id": "L2-M", "title": "M task", "component": "test", "level": "L2",
            "status": "active", "work_status": "todo", "criteria": "Given m",
            "assigned_agent": "python-coder", "estimated_complexity": "M",
            "depends_on": [],
        })
        _write_ac(ac_dir, "s.yaml", {
            "id": "L2-S", "title": "S task", "component": "test", "level": "L2",
            "status": "active", "work_status": "todo", "criteria": "Given s",
            "assigned_agent": "python-coder", "estimated_complexity": "S",
            "depends_on": [],
        })

        result = _run_scan(ac_dir, ["--json"])
        assert result.returncode == 0, f"Scanner failed: {result.stderr}"
        output = json.loads(result.stdout)
        ready_ids = [ac["ac_id"] for ac in output["ready"]]
        assert ready_ids.index("L2-S") < ready_ids.index("L2-M"), "S must come before M"
        assert ready_ids.index("L2-M") < ready_ids.index("L2-XL"), "M must come before XL"


class TestScanAcStoreJsonOutput:
    """AC-5: JSON output conforms to the defined schema."""

    def test_json_output_schema(self, tmp_path: Path) -> None:
        """test_json_output_schema: JSON output has ready and blocked arrays with correct fields."""
        ac_dir = tmp_path / "ac_store"
        _write_ac(ac_dir, "item.yaml", {
            "id": "L2-JSON", "title": "JSON test", "component": "test", "level": "L2",
            "status": "active", "work_status": "todo", "criteria": "Given json",
            "assigned_agent": "python-coder", "estimated_complexity": "S",
            "depends_on": [],
        })

        result = _run_scan(ac_dir, ["--json"])
        assert result.returncode == 0, f"Scanner failed: {result.stderr}"

        output = json.loads(result.stdout)
        assert "ready" in output, "JSON output must have 'ready' key"
        assert "blocked" in output, "JSON output must have 'blocked' key"
        assert isinstance(output["ready"], list), "'ready' must be a list"
        assert isinstance(output["blocked"], list), "'blocked' must be a list"

        for item in output["ready"]:
            for required_field in ("ac_id", "title", "assigned_agent", "estimated_complexity", "path"):
                assert required_field in item, (
                    f"ready item missing required field '{required_field}': {item}"
                )

        for item in output["blocked"]:
            assert "ac_id" in item, f"blocked item missing 'ac_id': {item}"
            assert "blocked_by" in item, f"blocked item missing 'blocked_by': {item}"
            assert isinstance(item["blocked_by"], list), "'blocked_by' must be a list"

    def test_json_ac_id_resolves_to_existing_file(self, tmp_path: Path) -> None:
        """Every ac_id in ready must resolve to an existing YAML file."""
        ac_dir = tmp_path / "ac_store"
        _write_ac(ac_dir, "resolve.yaml", {
            "id": "L2-RESOLVE", "title": "Resolve test", "component": "test", "level": "L2",
            "status": "active", "work_status": "todo", "criteria": "Given resolve",
            "assigned_agent": "python-coder", "estimated_complexity": "S",
            "depends_on": [],
        })

        result = _run_scan(ac_dir, ["--json"])
        assert result.returncode == 0, f"Scanner failed: {result.stderr}"
        output = json.loads(result.stdout)

        for item in output["ready"]:
            file_path = Path(item["path"])
            assert file_path.exists(), (
                f"ac_id '{item['ac_id']}' path '{item['path']}' does not exist"
            )


class TestScanAcStoreEdgeCases:
    """Edge cases: empty store, unreadable YAML."""

    def test_empty_store_returns_empty_ready(self, tmp_path: Path) -> None:
        """test_empty_store_returns_empty_ready: An empty AC root returns empty ready list."""
        ac_dir = tmp_path / "empty_store"
        ac_dir.mkdir()

        result = _run_scan(ac_dir, ["--json"])
        assert result.returncode == 0, f"Scanner failed on empty store: {result.stderr}"
        output = json.loads(result.stdout)
        assert output["ready"] == [], "Empty store must return empty ready list"

    def test_unreadable_yaml_exits_nonzero(self, tmp_path: Path) -> None:
        """Malformed YAML file causes exit code 1 with per-file diagnostic on stderr."""
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        bad_file = ac_dir / "bad.yaml"
        bad_file.write_text("id: [\n  unclosed bracket\n", encoding="utf-8")

        result = _run_scan(ac_dir, ["--json"])
        assert result.returncode == 1, (
            f"Scanner must exit 1 on malformed YAML, got {result.returncode}"
        )
        assert "bad.yaml" in result.stderr or "bad.yaml" in result.stdout, (
            "Error output must reference the bad file"
        )


# ---------------------------------------------------------------------------
# Regression tests for ACD-1200a-9: level-based leaf detection in
# _dfs_collect_leaves().
#
# BUG (current code): _dfs_collect_leaves() uses `if not children:` as its
# sole leaf signal — any node with a non-empty covered_by is treated as a
# pure composite pass-through, even if its level is L2 or L3.  This means
# an L2 AC with L3 edge-case children is silently dropped from the result.
#
# FIX (expected after python-coder): check `level in _LEAF_LEVELS` first.
# L2/L3 nodes are emitted as leaves AND their children are also recursed.
# L0/L1 nodes are pure composites (never emitted as leaves themselves).
#
# All four tests below MUST FAIL against the current buggy code and PASS
# after the fix.
# ---------------------------------------------------------------------------

# Ensure the scripts package is importable from the worktree root.
if str(WORKTREE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKTREE_ROOT))

from scripts.ac_store.scan_ac_store import traverse_ac_tree  # noqa: E402


class TestDfsCollectLeavesLevelBased:
    """ACD-1200a-9: _dfs_collect_leaves must use level-based leaf detection."""

    # ------------------------------------------------------------------
    # Shared fixture builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_tree(ac_dir: Path) -> None:
        """Write a canonical 4-node tree used by tests 1 and 2.

        Tree shape:
            ROOT-001 (L0, covered_by: [ROOT-001a])
              ROOT-001a (L1, covered_by: [ROOT-001a-1, ROOT-001a-2])
                ROOT-001a-1 (L2, covered_by: [])
                ROOT-001a-2 (L2, covered_by: [ROOT-001a-2-i])
                  ROOT-001a-2-i (L3, covered_by: [])
        """
        _write_ac(ac_dir, "root.yaml", {
            "id": "ROOT-001",
            "title": "Root L0",
            "component": "test",
            "level": "L0",
            "status": "active",
            "work_status": "todo",
            "criteria": "Given root",
            "assigned_agent": "python-coder",
            "estimated_complexity": "S",
            "depends_on": [],
            "covered_by": ["ROOT-001a"],
        })
        _write_ac(ac_dir, "l1.yaml", {
            "id": "ROOT-001a",
            "title": "L1 child",
            "component": "test",
            "level": "L1",
            "status": "active",
            "work_status": "todo",
            "criteria": "Given l1",
            "assigned_agent": "python-coder",
            "estimated_complexity": "S",
            "depends_on": [],
            "covered_by": ["ROOT-001a-1", "ROOT-001a-2"],
        })
        _write_ac(ac_dir, "l2a.yaml", {
            "id": "ROOT-001a-1",
            "title": "L2 simple leaf",
            "component": "test",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "criteria": "Given l2a",
            "assigned_agent": "python-coder",
            "estimated_complexity": "S",
            "depends_on": [],
            "covered_by": [],
        })
        _write_ac(ac_dir, "l2b.yaml", {
            "id": "ROOT-001a-2",
            "title": "L2 with L3 child",
            "component": "test",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "criteria": "Given l2b",
            "assigned_agent": "python-coder",
            "estimated_complexity": "S",
            "depends_on": [],
            "covered_by": ["ROOT-001a-2-i"],
        })
        _write_ac(ac_dir, "l3.yaml", {
            "id": "ROOT-001a-2-i",
            "title": "L3 edge case",
            "component": "test",
            "level": "L3",
            "status": "active",
            "work_status": "todo",
            "criteria": "Given l3",
            "assigned_agent": "python-coder",
            "estimated_complexity": "S",
            "depends_on": [],
            "covered_by": [],
        })

    # ------------------------------------------------------------------
    # Test 1 — ACD-1200a-9
    # ------------------------------------------------------------------

    def test_l2_with_covered_by_emitted_as_leaf(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-9
        """An L2 node with non-empty covered_by must still appear in the leaf list.

        Bug (current code): ROOT-001a-2 is L2 but has covered_by=[ROOT-001a-2-i],
        so _dfs_collect_leaves() recurses without emitting it — it never appears in
        the result.  After the fix the L2 node must be emitted before its children.
        """
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        self._build_tree(ac_dir)

        result = traverse_ac_tree("ROOT-001", ac_dir)

        assert "ROOT-001a-2" in result, (
            "L2 node ROOT-001a-2 has covered_by=[ROOT-001a-2-i] but must still be "
            "emitted as a leaf because its level is L2. Current buggy code skips it."
        )

    # ------------------------------------------------------------------
    # Test 2 — ACD-1200a-9
    # ------------------------------------------------------------------

    def test_l3_under_l2_also_collected(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-9
        """Both the L2 and its L3 child must appear when an L2 has covered_by children.

        After the fix traverse_ac_tree("ROOT-001", ...) must return at least:
            ["ROOT-001a-1", "ROOT-001a-2", "ROOT-001a-2-i"]
        i.e. the L2 is emitted AND the recursion continues into the L3.
        """
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()
        self._build_tree(ac_dir)

        result = traverse_ac_tree("ROOT-001", ac_dir)

        assert "ROOT-001a-2" in result, (
            "L2 node ROOT-001a-2 must be in result (level-based leaf detection)"
        )
        assert "ROOT-001a-2-i" in result, (
            "L3 node ROOT-001a-2-i must be in result (recursion into L2 children)"
        )
        assert result == ["ROOT-001a-1", "ROOT-001a-2", "ROOT-001a-2-i"], (
            "Expected exactly [ROOT-001a-1, ROOT-001a-2, ROOT-001a-2-i] in DFS order"
        )

    # ------------------------------------------------------------------
    # Test 3 — ACD-1200a-9
    # ------------------------------------------------------------------

    def test_l0_l1_never_emitted_as_leaf(self, tmp_path: Path) -> None:
        # covers: ACD-1200a-9
        """L0 and L1 nodes with empty covered_by must NOT be emitted as leaves.

        Current buggy code returns [node_id] for any node whose covered_by is
        empty, regardless of level.  After the fix, L0/L1 nodes must never
        appear in the leaf list even when they have no children.
        """
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()

        _write_ac(ac_dir, "l0_bare.yaml", {
            "id": "BARE-L0",
            "title": "Bare L0",
            "component": "test",
            "level": "L0",
            "status": "active",
            "work_status": "todo",
            "criteria": "Given l0",
            "assigned_agent": "python-coder",
            "estimated_complexity": "S",
            "depends_on": [],
            "covered_by": [],
        })
        _write_ac(ac_dir, "l1_bare.yaml", {
            "id": "BARE-L1",
            "title": "Bare L1",
            "component": "test",
            "level": "L1",
            "status": "active",
            "work_status": "todo",
            "criteria": "Given l1",
            "assigned_agent": "python-coder",
            "estimated_complexity": "S",
            "depends_on": [],
            "covered_by": [],
        })

        result_l0 = traverse_ac_tree("BARE-L0", ac_dir)
        result_l1 = traverse_ac_tree("BARE-L1", ac_dir)

        assert "BARE-L0" not in result_l0, (
            "L0 node must never appear as a leaf even when covered_by is empty. "
            "Current buggy code emits it because covered_by==[] passes `if not children`."
        )
        assert "BARE-L1" not in result_l1, (
            "L1 node must never appear as a leaf even when covered_by is empty. "
            "Current buggy code emits it because covered_by==[] passes `if not children`."
        )

    # ------------------------------------------------------------------
    # Test 4 — ACD-1200a-9
    # ------------------------------------------------------------------

    def test_depth_first_order_preserved_with_level_based_detection(
        self, tmp_path: Path
    ) -> None:
        # covers: ACD-1200a-9
        """DFS with alphabetical siblings must be preserved after level-based fix.

        Tree:
            DFS-L0 (L0)
              DFS-L1a (L1) -> DFS-L2-alpha, DFS-L2-beta
                DFS-L2-alpha (L2, covered_by: [])
                DFS-L2-beta  (L2, covered_by: [DFS-L3-gamma])
                  DFS-L3-gamma (L3, covered_by: [])
              DFS-L1b (L1) -> DFS-L2-delta
                DFS-L2-delta (L2, covered_by: [])

        Expected DFS leaf order (alphabetical siblings at each level):
            [DFS-L2-alpha, DFS-L2-beta, DFS-L3-gamma, DFS-L2-delta]
        """
        ac_dir = tmp_path / "ac_store"
        ac_dir.mkdir()

        _write_ac(ac_dir, "dfs_l0.yaml", {
            "id": "DFS-L0",
            "title": "DFS root",
            "component": "test",
            "level": "L0",
            "status": "active",
            "work_status": "todo",
            "criteria": "Given root",
            "assigned_agent": "python-coder",
            "estimated_complexity": "S",
            "depends_on": [],
            "covered_by": ["DFS-L1a", "DFS-L1b"],
        })
        _write_ac(ac_dir, "dfs_l1a.yaml", {
            "id": "DFS-L1a",
            "title": "DFS L1a",
            "component": "test",
            "level": "L1",
            "status": "active",
            "work_status": "todo",
            "criteria": "Given l1a",
            "assigned_agent": "python-coder",
            "estimated_complexity": "S",
            "depends_on": [],
            "covered_by": ["DFS-L2-alpha", "DFS-L2-beta"],
        })
        _write_ac(ac_dir, "dfs_l1b.yaml", {
            "id": "DFS-L1b",
            "title": "DFS L1b",
            "component": "test",
            "level": "L1",
            "status": "active",
            "work_status": "todo",
            "criteria": "Given l1b",
            "assigned_agent": "python-coder",
            "estimated_complexity": "S",
            "depends_on": [],
            "covered_by": ["DFS-L2-delta"],
        })
        _write_ac(ac_dir, "dfs_l2_alpha.yaml", {
            "id": "DFS-L2-alpha",
            "title": "DFS L2 alpha",
            "component": "test",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "criteria": "Given l2-alpha",
            "assigned_agent": "python-coder",
            "estimated_complexity": "S",
            "depends_on": [],
            "covered_by": [],
        })
        _write_ac(ac_dir, "dfs_l2_beta.yaml", {
            "id": "DFS-L2-beta",
            "title": "DFS L2 beta",
            "component": "test",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "criteria": "Given l2-beta",
            "assigned_agent": "python-coder",
            "estimated_complexity": "S",
            "depends_on": [],
            "covered_by": ["DFS-L3-gamma"],
        })
        _write_ac(ac_dir, "dfs_l3_gamma.yaml", {
            "id": "DFS-L3-gamma",
            "title": "DFS L3 gamma",
            "component": "test",
            "level": "L3",
            "status": "active",
            "work_status": "todo",
            "criteria": "Given l3-gamma",
            "assigned_agent": "python-coder",
            "estimated_complexity": "S",
            "depends_on": [],
            "covered_by": [],
        })
        _write_ac(ac_dir, "dfs_l2_delta.yaml", {
            "id": "DFS-L2-delta",
            "title": "DFS L2 delta",
            "component": "test",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "criteria": "Given l2-delta",
            "assigned_agent": "python-coder",
            "estimated_complexity": "S",
            "depends_on": [],
            "covered_by": [],
        })

        result = traverse_ac_tree("DFS-L0", ac_dir)

        expected = ["DFS-L2-alpha", "DFS-L2-beta", "DFS-L3-gamma", "DFS-L2-delta"]
        assert result == expected, (
            f"Expected DFS leaf order {expected!r} but got {result!r}. "
            "After level-based fix: L2-beta must be emitted before recursing into "
            "L3-gamma, and L2-delta comes last under L1b."
        )
