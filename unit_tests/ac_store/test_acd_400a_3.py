"""
MODULE: test_acd_400a_3
GOAL: Regression tests for ACD-400a-3 — the scanner must NOT treat an AC's own
      transitive ancestor as a build-order blocker.

When an L2 leaf AC's only depends_on entry is its own L1 parent (the standard
hierarchy-linking convention used by the authoring agents), the scanner must
classify the leaf as ready, not blocked.

Against current code these tests FAIL because _classify_ac in scan_ac_store.py
treats every depends_on entry as a blocking dependency without excluding ancestors.
An ancestor link must never gate readiness; only genuine non-ancestor deps may do so.

COVERS: ACD-400a-3
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

# ---------------------------------------------------------------------------
# Path setup — import from the worktree's scripts/ac_store/ directory
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_AC_STORE_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_AC_STORE_SCRIPTS_DIR))

from scan_ac_store import main as scan_main  # noqa: E402
from ac_prioritizer import merge_and_prioritize  # noqa: E402

# Absolute path to the real scan_ac_store.py script (used by test 3 via subprocess)
_SCAN_SCRIPT = _AC_STORE_SCRIPTS_DIR / "scan_ac_store.py"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_ac(
    ac_root: Path,
    ac_id: str,
    *,
    level: str = "L2",
    depends_on: list[str] | None = None,
    covered_by: list[str] | None = None,
    work_status: str = "todo",
    status: str = "active",
    readiness: str = "approved",
) -> Path:
    """Write a minimal AC YAML into *ac_root* using the real yaml.dump serializer.

    Files are written into a subdirectory derived from the first two dash-
    separated components of *ac_id* (e.g. X-100a-1 → ac_root/X-100a/).
    This matches the layout the authoring agents produce in the live store.

    Using yaml.dump (not a hand-typed literal) ensures the serialized format
    matches what the real store produces — the same column-0 block-style lists
    that the scanner parser expects.
    """
    parts = ac_id.split("-")
    subdir = ac_root / "-".join(parts[:2]) if len(parts) >= 2 else ac_root
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict[str, Any] = {
        "id": ac_id,
        "title": f"AC {ac_id}",
        "level": level,
        "status": status,
        "readiness": readiness,
        "work_status": work_status,
        "covered_by": covered_by if covered_by is not None else [],
        "estimated_complexity": "M",
        "priority": "medium",
        "assigned_agent": "python-coder",
    }
    if depends_on is not None:
        data["depends_on"] = depends_on
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _make_ancestor_fixture(ac_root: Path) -> None:
    """Write the minimal ancestor-dep fixture tree into *ac_root*.

    Tree:
      X-100a   — L1 composite, work_status=todo (not done), status=active
      X-100a-1 — L2 leaf, readiness=approved, work_status=todo,
                 depends_on=[X-100a]  (only dep is its own parent)

    This is the exact scenario from the ACD-400a-3 criteria: a leaf whose
    only depends_on entry is its own transitive ancestor.
    """
    # L1 composite parent — work_status NOT done.
    # L1 composites are never picked up by the leaf filter; readiness: reviewed
    # is intentional (they are never submitted as individual work items).
    _write_ac(
        ac_root,
        "X-100a",
        level="L1",
        work_status="todo",
        status="active",
        readiness="reviewed",
        covered_by=["X-100a-1"],
        depends_on=[],
    )
    # L2 leaf — only dep is its own parent (the ancestor-dep bug scenario)
    _write_ac(
        ac_root,
        "X-100a-1",
        level="L2",
        work_status="todo",
        status="active",
        readiness="approved",
        depends_on=["X-100a"],
    )


def _write_stub_prioritize(directory: Path) -> Path:
    """Write a minimal stub prioritize.py to *directory*.

    The stub always exits 0 and emits an empty ready/blocked JSON object,
    simulating a ticket prioritizer that finds no ready tickets.  This lets
    test 3 call merge_and_prioritize() in isolation without needing the real
    ticket store on disk.

    Args:
        directory: Where to write stub_prioritize.py.

    Returns:
        Absolute path to the stub script.
    """
    stub_path = directory / "stub_prioritize.py"
    # Written as a list of lines to avoid any shell-escaping concerns;
    # no heredoc or echo — this is pure Python string concat.
    lines = [
        "#!/usr/bin/env python3\n",
        "import json\n",
        "import sys\n",
        "print(json.dumps({'ready': [], 'blocked': []}))\n",
        "sys.exit(0)\n",
    ]
    stub_path.write_text("".join(lines), encoding="utf-8")
    return stub_path


# ---------------------------------------------------------------------------
# Tests — all three must be RED against the current unmodified scanner
# ---------------------------------------------------------------------------


def test_leaf_with_only_parent_dep_is_ready_not_blocked(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # covers: ACD-400a-3
    """X-100a-1 must appear in the ready list and NOT in the blocked list.

    X-100a-1's only depends_on entry is its own L1 parent X-100a.
    X-100a has work_status: todo (not done — an L1 composite never reaches done
    because it is never submitted as a work item). An ancestor link must never
    gate readiness: X-100a-1 must therefore be classified ready.

    What must be implemented (python-coder) to make this test green:
      _classify_ac() must compute the transitive ancestor set for the AC
      under classification (using derive_parent_id() applied iteratively) and
      exclude any depends_on entry that is a transitive ancestor from the
      blocking set. A leaf whose only depends_on entries are its own ancestors
      must classify as ('ready', []).

    Against current code: _classify_ac treats X-100a as a blocking dep because
    _is_dep_done("X-100a") returns False (work_status=todo ≠ done).
    X-100a-1 is classified blocked → assertion fails → RED.
    """
    _make_ancestor_fixture(tmp_path)

    exit_code = scan_main(
        ["--ac-root", str(tmp_path), "--json", "--level", "leaf", "--work-status", "todo"]
    )

    assert exit_code == 0, f"scan_main exited with non-zero code: {exit_code}"

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    ready_ids = [entry["ac_id"] for entry in output.get("ready", [])]
    blocked_ids = [entry["ac_id"] for entry in output.get("blocked", [])]

    assert "X-100a-1" in ready_ids, (
        "X-100a-1 must be in the ready list — an ancestor-only dep must not gate readiness. "
        f"ready={ready_ids!r}, blocked={blocked_ids!r}"
    )
    assert "X-100a-1" not in blocked_ids, (
        f"X-100a-1 must NOT be in the blocked list. blocked={blocked_ids!r}"
    )


def test_ancestor_never_named_as_blocker(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # covers: ACD-400a-3
    """No blocked entry must list X-100a as a blocker of X-100a-1.

    X-100a is a transitive ancestor of X-100a-1.  Even when X-100a has
    work_status: todo (not done), it must never appear in the blocked_by
    field of any blocked entry for X-100a-1 — ancestors are excluded from
    the gating dependency set by definition.

    What must be implemented (python-coder) to make this test green:
      The ancestor-exclusion logic in _classify_ac() must prevent X-100a from
      being named as a blocker in the blocked_by list of X-100a-1 even when
      _is_dep_done("X-100a") returns False.

    Against current code: the blocked entry for X-100a-1 contains
    blocked_by=["X-100a"] → assertion fires → RED.
    After the fix: X-100a-1 is classified ready, no blocked entry exists
    for it, X-100a is not named as a blocker → GREEN.
    """
    _make_ancestor_fixture(tmp_path)

    exit_code = scan_main(
        ["--ac-root", str(tmp_path), "--json", "--level", "leaf", "--work-status", "todo"]
    )

    assert exit_code == 0, f"scan_main exited with non-zero code: {exit_code}"

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    blocked_entries = output.get("blocked", [])

    # Collect all ACs that the scanner claims are blocked BY X-100a.
    # X-100a is an ancestor of X-100a-1 and must never appear in any blocked_by list
    # for that descendant.
    acs_blocked_by_x100a = [
        entry["ac_id"]
        for entry in blocked_entries
        if "X-100a" in entry.get("blocked_by", [])
    ]

    assert "X-100a-1" not in acs_blocked_by_x100a, (
        "Ancestor X-100a must never appear as a blocker of its descendant X-100a-1. "
        f"ACs currently blocked by X-100a: {acs_blocked_by_x100a!r}"
    )


def test_prioritizer_consistent_with_scanner_on_ancestor_dep(
    tmp_path: Path,
) -> None:
    # covers: ACD-400a-3
    """ac_prioritizer must agree with the scanner: X-100a-1 is ready, not blocked.

    ac_prioritizer delegates to scan_ac_store via subprocess and mirrors its
    ready/blocked classification for AC entries. Once the scanner excludes
    ancestor-only deps from the blocking set, the prioritizer's merged output
    must also classify X-100a-1 as ready (not blocked).

    What must be implemented (python-coder) to make this test green:
      The scanner fix (ancestor-aware _classify_ac) must propagate through the
      subprocess call in ac_prioritizer._run_json_script(). No additional change
      to ac_prioritizer.py is needed — this test verifies the end-to-end
      consistency guarantee.

    Against current code: the scanner classifies X-100a-1 as blocked, and
    merge_and_prioritize() propagates that into its blocked list. The assertion
    that X-100a-1 is in prio_ready_ac_ids fails → RED.
    After the fix: scanner returns X-100a-1 as ready; prioritizer merges it
    into the ready list → GREEN.
    """
    _make_ancestor_fixture(tmp_path)

    # Write a stub prioritize.py that returns an empty ready/blocked JSON.
    # This isolates the test to the AC-store classification path only (no real
    # ticket store needed). The stub is a .py file; the scanner's rglob("*.yaml")
    # will not pick it up.
    stub_prioritize = _write_stub_prioritize(tmp_path)

    result = merge_and_prioritize(
        scan_script=_SCAN_SCRIPT,
        prioritize_script=stub_prioritize,
        scan_extra_args=[
            "--ac-root", str(tmp_path),
            "--level", "leaf",
            "--work-status", "todo",
        ],
    )

    # Extract only the AC-sourced entries from the prioritizer result
    prio_ready_ac_ids = [
        entry["ac_id"]
        for entry in result.get("ready", [])
        if entry.get("source") == "ac"
    ]
    prio_blocked_ac_ids = [
        entry["ac_id"]
        for entry in result.get("blocked", [])
        if entry.get("source") == "ac"
    ]

    assert "X-100a-1" in prio_ready_ac_ids, (
        "ac_prioritizer must classify X-100a-1 as ready — ancestor-only dep must not block. "
        f"prio_ready_ac_ids={prio_ready_ac_ids!r}, prio_blocked_ac_ids={prio_blocked_ac_ids!r}"
    )
    assert "X-100a-1" not in prio_blocked_ac_ids, (
        "ac_prioritizer must not classify X-100a-1 as blocked. "
        f"prio_blocked_ac_ids={prio_blocked_ac_ids!r}"
    )


def test_genuine_non_ancestor_dep_still_blocks(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # covers: ACD-400a-3
    """Over-exclusion guard: a real non-ancestor dep must still gate readiness.

    The ancestor-exclusion fix must be surgical — it must drop ONLY an AC's own
    transitive ancestors from the blocking set, never a genuine cross-feature
    dependency. Here X-100a-1 depends on both its own parent X-100a (ancestor,
    excluded) and W-400b-2 (a different feature's L2, NOT an ancestor, work_status
    todo). The leaf must be classified blocked, its blocked_by must name the real
    blocker W-400b-2, and it must NOT name the excluded ancestor X-100a.

    This guards against a future regression that broadens the exclusion predicate
    and silently stops gating real dependencies.
    """
    # Ancestor parent (excluded from gating) + the leaf with a mixed dep list.
    _write_ac(
        tmp_path,
        "X-100a",
        level="L1",
        work_status="todo",
        status="active",
        readiness="reviewed",
        covered_by=["X-100a-1"],
        depends_on=[],
    )
    # Genuine non-ancestor dependency from a different feature — not done.
    _write_ac(
        tmp_path,
        "W-400b-2",
        level="L2",
        work_status="todo",
        status="active",
        readiness="approved",
        depends_on=[],
    )
    _write_ac(
        tmp_path,
        "X-100a-1",
        level="L2",
        work_status="todo",
        status="active",
        readiness="approved",
        depends_on=["X-100a", "W-400b-2"],
    )

    exit_code = scan_main(
        ["--ac-root", str(tmp_path), "--json", "--level", "leaf", "--work-status", "todo"]
    )
    assert exit_code == 0, f"scan_main exited with non-zero code: {exit_code}"

    output = json.loads(capsys.readouterr().out)
    ready_ids = [entry["ac_id"] for entry in output.get("ready", [])]
    blocked_by_map = {
        entry["ac_id"]: entry.get("blocked_by", []) for entry in output.get("blocked", [])
    }

    assert "X-100a-1" not in ready_ids, (
        "X-100a-1 has an unsatisfied non-ancestor dep and must NOT be ready. "
        f"ready={ready_ids!r}"
    )
    assert "X-100a-1" in blocked_by_map, (
        f"X-100a-1 must be blocked by its genuine dep. blocked={list(blocked_by_map)!r}"
    )
    blockers = blocked_by_map["X-100a-1"]
    assert "W-400b-2" in blockers, (
        f"The real non-ancestor blocker W-400b-2 must be named. blocked_by={blockers!r}"
    )
    assert "X-100a" not in blockers, (
        f"The excluded ancestor X-100a must NOT be named as a blocker. blocked_by={blockers!r}"
    )


# ---------------------------------------------------------------------------
# ACD-400a-3-i — no transitive ancestor at ANY depth gates a leaf's readiness
# ---------------------------------------------------------------------------


def _make_three_level_fixture(ac_root: Path) -> None:
    """Write an L1 -> L2 -> L3 lineage where only the L3 is a leaf.

    Y-200a   (L1 composite, not done) -> Y-200a-1 (L2 composite, not done,
    depends_on [Y-200a]) -> Y-200a-1-i (L3 leaf, approved/active/todo,
    depends_on [Y-200a-1]). Neither the parent L2 nor the grandparent L1 must
    gate the L3 leaf.
    """
    _write_ac(
        ac_root, "Y-200a", level="L1", work_status="todo", status="active",
        readiness="reviewed", covered_by=["Y-200a-1"], depends_on=[],
    )
    _write_ac(
        ac_root, "Y-200a-1", level="L2", work_status="todo", status="active",
        readiness="approved", covered_by=["Y-200a-1-i"], depends_on=["Y-200a"],
    )
    _write_ac(
        ac_root, "Y-200a-1-i", level="L3", work_status="todo", status="active",
        readiness="approved", depends_on=["Y-200a-1"],
    )


def _scan_json(
    ac_root: Path, capsys: pytest.CaptureFixture[str]
) -> dict[str, Any]:
    """Run the scanner (leaf+todo, json) over *ac_root* and return parsed output."""
    exit_code = scan_main(
        ["--ac-root", str(ac_root), "--json", "--level", "leaf", "--work-status", "todo"]
    )
    assert exit_code == 0, f"scan_main exited with non-zero code: {exit_code}"
    return json.loads(capsys.readouterr().out)


def test_grandparent_ancestor_does_not_block_leaf(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # covers: ACD-400a-3-i
    """An L3 leaf whose ancestors (parent L2, grandparent L1) are all not-done is ready."""
    _make_three_level_fixture(tmp_path)
    output = _scan_json(tmp_path, capsys)
    ready_ids = [e["ac_id"] for e in output.get("ready", [])]
    blocked_ids = [e["ac_id"] for e in output.get("blocked", [])]
    assert "Y-200a-1-i" in ready_ids, (
        "L3 leaf must be ready — no ancestor at any depth may gate it. "
        f"ready={ready_ids!r}, blocked={blocked_ids!r}"
    )
    assert "Y-200a-1-i" not in blocked_ids, (
        f"L3 leaf must NOT be blocked. blocked={blocked_ids!r}"
    )


def test_no_transitive_ancestor_named_as_blocker(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # covers: ACD-400a-3-i
    """Neither the parent L2 nor the grandparent L1 may be named as a blocker."""
    _make_three_level_fixture(tmp_path)
    output = _scan_json(tmp_path, capsys)
    blocked_by = {
        e["ac_id"]: e.get("blocked_by", []) for e in output.get("blocked", [])
    }.get("Y-200a-1-i", [])
    assert "Y-200a-1" not in blocked_by, (
        f"Parent L2 must not be a blocker of the L3 leaf. blocked_by={blocked_by!r}"
    )
    assert "Y-200a" not in blocked_by, (
        f"Grandparent L1 must not be a blocker of the L3 leaf. blocked_by={blocked_by!r}"
    )


# ---------------------------------------------------------------------------
# ACD-400a-3-ii — a genuine non-ancestor dep still gates readiness on done
# ---------------------------------------------------------------------------


def _make_mixed_dep_fixture(ac_root: Path, *, cross_feature_done: bool) -> None:
    """Z-300a-1 depends on its own parent (ancestor) + a cross-feature L2.

    Z-300a  (L1 composite, not done) — ancestor of Z-300a-1.
    W-400b-2 (L2, different feature) — work_status done|todo per *cross_feature_done*.
    Z-300a-1 (L2 leaf, approved/active/todo) depends_on [Z-300a, W-400b-2].
    """
    _write_ac(
        ac_root, "Z-300a", level="L1", work_status="todo", status="active",
        readiness="reviewed", covered_by=["Z-300a-1"], depends_on=[],
    )
    _write_ac(
        ac_root, "W-400b-2", level="L2",
        work_status="done" if cross_feature_done else "todo",
        status="active", readiness="approved", depends_on=[],
    )
    _write_ac(
        ac_root, "Z-300a-1", level="L2", work_status="todo", status="active",
        readiness="approved", depends_on=["Z-300a", "W-400b-2"],
    )


def test_satisfied_non_ancestor_dep_clears_to_ready(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # covers: ACD-400a-3-ii
    """Ancestor excluded + satisfied (done) cross-feature dep -> leaf is ready."""
    _make_mixed_dep_fixture(tmp_path, cross_feature_done=True)
    output = _scan_json(tmp_path, capsys)
    ready_ids = [e["ac_id"] for e in output.get("ready", [])]
    blocked_ids = [e["ac_id"] for e in output.get("blocked", [])]
    assert "Z-300a-1" in ready_ids, (
        "Ancestor excluded and cross-feature dep done -> leaf must be ready. "
        f"ready={ready_ids!r}, blocked={blocked_ids!r}"
    )
    assert "Z-300a-1" not in blocked_ids, f"blocked={blocked_ids!r}"


def test_unsatisfied_non_ancestor_dep_blocks_naming_real_blocker(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # covers: ACD-400a-3-ii
    """Unsatisfied (todo) cross-feature dep gates; blocker named is the real dep, not the ancestor."""
    _make_mixed_dep_fixture(tmp_path, cross_feature_done=False)
    output = _scan_json(tmp_path, capsys)
    ready_ids = [e["ac_id"] for e in output.get("ready", [])]
    blocked_by = {
        e["ac_id"]: e.get("blocked_by", []) for e in output.get("blocked", [])
    }
    assert "Z-300a-1" not in ready_ids, f"ready={ready_ids!r}"
    assert "Z-300a-1" in blocked_by, f"blocked={list(blocked_by)!r}"
    blockers = blocked_by["Z-300a-1"]
    assert "W-400b-2" in blockers, f"real blocker must be named: {blockers!r}"
    assert "Z-300a" not in blockers, f"ancestor must NOT be named: {blockers!r}"


def test_done_to_ready_todo_to_blocked_transition(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # covers: ACD-400a-3-ii
    """Flipping the cross-feature dep done<->todo flips leaf ready<->blocked; ancestor never blocks."""
    # Run 1 — cross-feature dep done -> ready.
    _make_mixed_dep_fixture(tmp_path, cross_feature_done=True)
    out_done = _scan_json(tmp_path, capsys)
    ready_done = [e["ac_id"] for e in out_done.get("ready", [])]
    blocked_by_done = {
        e["ac_id"]: e.get("blocked_by", []) for e in out_done.get("blocked", [])
    }
    assert "Z-300a-1" in ready_done, f"done-run ready={ready_done!r}"
    assert "Z-300a" not in blocked_by_done.get("Z-300a-1", []), "ancestor blocked in done-run"

    # Run 2 — same store, cross-feature dep now todo -> blocked.
    _make_mixed_dep_fixture(tmp_path, cross_feature_done=False)
    out_todo = _scan_json(tmp_path, capsys)
    ready_todo = [e["ac_id"] for e in out_todo.get("ready", [])]
    blocked_by_todo = {
        e["ac_id"]: e.get("blocked_by", []) for e in out_todo.get("blocked", [])
    }
    assert "Z-300a-1" not in ready_todo, f"todo-run ready={ready_todo!r}"
    assert "W-400b-2" in blocked_by_todo.get("Z-300a-1", []), "real blocker missing in todo-run"
    assert "Z-300a" not in blocked_by_todo.get("Z-300a-1", []), "ancestor blocked in todo-run"


# ---------------------------------------------------------------------------
# ACD-400a-4 — a freshly-authored approved tree yields a non-empty ready list
# ---------------------------------------------------------------------------


def _make_fresh_tree_fixture(ac_root: Path) -> list[str]:
    """L1 composite + three approved/active/todo leaves each depending only on their parent.

    Returns the list of the three leaf ids.
    """
    _write_ac(
        ac_root, "P-500a", level="L1", work_status="todo", status="active",
        readiness="reviewed", covered_by=["P-500a-1", "P-500a-2", "P-500a-3"],
        depends_on=[],
    )
    leaves = ["P-500a-1", "P-500a-2", "P-500a-3"]
    for leaf in leaves:
        _write_ac(
            ac_root, leaf, level="L2", work_status="todo", status="active",
            readiness="approved", depends_on=["P-500a"],
        )
    return leaves


def test_freshly_authored_tree_yields_non_empty_ready_list(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # covers: ACD-400a-4
    """A normally-authored backlog (parent-only hierarchy links) produces ready work."""
    leaves = _make_fresh_tree_fixture(tmp_path)
    output = _scan_json(tmp_path, capsys)
    ready_ids = [e["ac_id"] for e in output.get("ready", [])]
    assert ready_ids, "ready list must be non-empty for a freshly-authored approved tree"
    for leaf in leaves:
        assert leaf in ready_ids, f"{leaf} must be ready. ready={ready_ids!r}"


def test_freshly_authored_tree_no_leaf_self_blocked(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # covers: ACD-400a-4
    """No leaf in a freshly-authored tree is self-blocked by its parent hierarchy link."""
    leaves = _make_fresh_tree_fixture(tmp_path)
    output = _scan_json(tmp_path, capsys)
    blocked_ids = [e["ac_id"] for e in output.get("blocked", [])]
    for leaf in leaves:
        assert leaf not in blocked_ids, (
            f"{leaf} must NOT be self-blocked. blocked={blocked_ids!r}"
        )
