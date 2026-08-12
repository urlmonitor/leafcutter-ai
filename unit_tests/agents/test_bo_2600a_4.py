"""
MODULE: unit_tests/agents/test_bo_2600a_4.py
GOAL: Behavioral integration tests for BO-2600a-4 — build-ac routes a size>1
      connected set to goal_to_epic --ids, emitting a dependency-ordered epic
      containing every connected-set member (incl. cross-tree prerequisites).

These are GREEN coverage tests (not TDD-red stubs) because both CLIs already
exist and work:
  - fast_lane.py select_connected  (BO-2600a-2, green)
  - goal_to_epic.py --ids          (BO-2600a-5, green)

The tests prove the CLI COMPOSITION: selecting the connected set with
fast_lane.select_connected and passing the result to goal_to_epic --ids
produces an epic that (a) has one ticket per connected-set member and
(b) includes cross-tree prerequisites that a plain --ac subtree re-walk
would have dropped.

Fixture-authenticity mandate: all AC YAML files are written via yaml.safe_dump
(never hand-typed YAML literals), following the pattern in test_bo_2600a_5.py.

AC ID naming convention used in fixtures:
  "M1A-100a-1" prefix for test 1 (multi-member)
  "CTP-100a-1" / "CTP-200a-1" prefix for test 2 (cross-tree)
  "DEP-100a-1" / "DEP-200a-1" prefix for test 3 (dep-ordered)

Each test uses a fresh TemporaryDirectory so there is no cross-test
interference with the AC YAML store or the tickets inbox.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Repo-root path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_FAST_LANE_SCRIPT = _REPO_ROOT / "scripts" / "build_orchestration" / "fast_lane.py"
_GOAL_TO_EPIC_SCRIPT = _REPO_ROOT / "scripts" / "goal_to_epic.py"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_ac(
    ac_root: Path,
    ac_id: str,
    *,
    level: str = "L2",
    work_status: str = "todo",
    readiness: str = "approved",
    depends_on: list | None = None,
    covered_by: list | None = None,
) -> Path:
    """Write a minimal AC YAML using yaml.safe_dump (fixture-authenticity mandate).

    Files are placed under ac_root/test-component/ so _walk_ac_yamls finds
    them via rglob("*.yaml"). Never uses hand-typed YAML literals.

    Args:
        ac_root: Root of the temporary AC store.
        ac_id: AC identifier (e.g. "CTP-100a-1").
        level: "L0", "L1", "L2", or "L3".
        work_status: "todo" or "done".
        readiness: "approved" so classify_readiness takes the all-approved
            fast-path and never requires a TTY prompt in run().
        depends_on: List of AC ids this AC depends on (raw ids, not filenames).
        covered_by: List of child AC ids for parent nodes.

    Returns:
        Path to the written YAML file.
    """
    subdir = ac_root / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    data: dict = {
        "id": ac_id,
        "title": f"Test AC {ac_id}",
        "component": "build-orchestration",
        "components": ["build_orchestration"],
        "level": level,
        "status": "active",
        "work_status": work_status,
        "readiness": readiness,
        "priority": "medium",
        "estimated_complexity": "S",
        "assigned_agent": "python-coder",
        "depends_on": depends_on if depends_on is not None else [],
        "covered_by": covered_by if covered_by is not None else [],
        "amended_by": [],
        "implemented_by": [],
        "superseded_by": None,
        "criteria": f"Given {ac_id} is implemented, Then the feature works.",
    }
    path = subdir / f"{ac_id}.yaml"
    # Fixture-authenticity mandate: yaml.safe_dump, never a hand-typed literal.
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _run_select_connected(
    ac_id: str,
    ac_root: Path,
    *,
    exclude_structural_parent: bool = False,
) -> list[str]:
    """Invoke fast_lane.py select_connected and return the parsed JSON id list.

    Args:
        ac_id: Target AC id to resolve.
        ac_root: Root of the AC YAML store.
        exclude_structural_parent: When True, pass --exclude-structural-parent.

    Returns:
        Ordered list of AC ids from the connected build set.

    Raises:
        AssertionError: When the subprocess exits non-zero or output is not JSON.
    """
    cmd = [
        sys.executable,
        str(_FAST_LANE_SCRIPT),
        "select_connected",
        "--ac", ac_id,
        "--ac-root", str(ac_root),
    ]
    if exclude_structural_parent:
        cmd.append("--exclude-structural-parent")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, (
        f"fast_lane.py select_connected exited {result.returncode}.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    return json.loads(result.stdout.strip())


def _run_goal_to_epic_ids(
    ids: list[str],
    ac_root: Path,
    inbox_dir: Path,
) -> Path:
    """Invoke goal_to_epic.py --ids and return the assembled epic folder Path.

    Args:
        ids: Ordered list of AC ids to pass as --ids (comma-joined).
        ac_root: Root of the AC YAML store (--store-root).
        inbox_dir: Inbox directory (--inbox-dir).

    Returns:
        Path to the created epic folder.

    Raises:
        AssertionError: When the subprocess exits non-zero.
    """
    ids_str = ",".join(ids)
    result = subprocess.run(
        [
            sys.executable,
            str(_GOAL_TO_EPIC_SCRIPT),
            "--ids", ids_str,
            "--store-root", str(ac_root),
            "--inbox-dir", str(inbox_dir),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, (
        f"goal_to_epic.py --ids exited {result.returncode}.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    # The last non-empty stdout line is the absolute epic folder path.
    stdout_lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
    assert stdout_lines, (
        f"goal_to_epic.py --ids produced no stdout.\n"
        f"stderr: {result.stderr!r}"
    )
    return Path(stdout_lines[-1])


def _ticket_files(epic_folder: Path) -> list[Path]:
    """Return sorted ticket .md files in epic_folder (excluding Master_Plan.md)."""
    return sorted(
        f for f in epic_folder.iterdir()
        if f.suffix == ".md" and f.name != "Master_Plan.md"
    )


def _read_frontmatter(ticket_path: Path) -> dict:
    """Parse YAML frontmatter from a ticket file; return empty dict on failure."""
    try:
        content = ticket_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBo2600a4Integration(unittest.TestCase):
    """BO-2600a-4 — behavioral integration tests for the CLI composition.

    Proves that fast_lane.py select_connected piped into goal_to_epic.py --ids
    correctly produces a dependency-ordered epic with every connected-set member
    (including cross-tree prerequisites outside the target's subtree).
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        # inbox_dir follows the <worktree>/tickets/00_inbox convention so
        # _derive_worktree_from_inbox(inbox_dir) returns tmp as the worktree
        # root, enabling repo-relative implemented_by path computation.
        self.ac_root = tmp / "ac_store"
        self.inbox_dir = tmp / "tickets" / "00_inbox"
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.ac_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # -----------------------------------------------------------------------
    # Test 1 — multi-member set generates an epic folder
    # -----------------------------------------------------------------------

    def test_multi_member_set_generates_epic_folder(self) -> None:
        # covers: BO-2600a-4
        """A connected build set of size >1 produces an epic folder with one
        ticket per member, not a single ticket.

        Fixture: two L2 leaf ACs in the same sub-tree.
          M1A-100a-1 (L2) depends_on M1A-100a-2
          M1A-100a-2 (L2) no deps

        Connected set of M1A-100a-1 = {M1A-100a-2, M1A-100a-1} (size 2).

        Composition:
          1. fast_lane.py select_connected --ac M1A-100a-1 → ["M1A-100a-2","M1A-100a-1"]
          2. goal_to_epic.py --ids M1A-100a-2,M1A-100a-1 → epic folder with 2 tickets

        This test verifies AC-2 and AC-3 of BO-2600a-4: when the connected set
        has more than one member, the coordinator emits a dependency-ordered epic
        folder (not a single ticket) with every member represented.
        """
        # Fixture: two sibling L2 leaves, one depending on the other.
        _write_ac(self.ac_root, "M1A-100a-2", level="L2", work_status="todo")
        _write_ac(self.ac_root, "M1A-100a-1", level="L2", work_status="todo",
                  depends_on=["M1A-100a-2"])

        # Step 1: Resolve the connected build set.
        connected_set = _run_select_connected("M1A-100a-1", self.ac_root)

        self.assertGreater(
            len(connected_set), 1,
            f"Connected set of M1A-100a-1 must have >1 member "
            f"(M1A-100a-2 is a not-done dep). Got: {connected_set}"
        )
        self.assertIn(
            "M1A-100a-1", connected_set,
            f"Target M1A-100a-1 must appear in its own connected set. Got: {connected_set}"
        )
        self.assertIn(
            "M1A-100a-2", connected_set,
            f"Prerequisite M1A-100a-2 must appear in the connected set. Got: {connected_set}"
        )

        # Step 2: Build the epic from the full connected set.
        epic_folder = _run_goal_to_epic_ids(connected_set, self.ac_root, self.inbox_dir)

        self.assertTrue(
            epic_folder.is_dir(),
            f"goal_to_epic.py --ids must produce an epic folder on disk. "
            f"Got: {epic_folder!r}"
        )

        tickets = _ticket_files(epic_folder)
        self.assertEqual(
            len(tickets), 2,
            f"Epic folder must contain exactly 2 ticket files — one per connected-set member. "
            f"Got {len(tickets)}: {[t.name for t in tickets]}"
        )

        ticket_names = {t.name for t in tickets}
        self.assertTrue(
            any("M1A-100a-1" in n for n in ticket_names),
            f"A ticket for M1A-100a-1 must be in the epic. Got: {sorted(ticket_names)}"
        )
        self.assertTrue(
            any("M1A-100a-2" in n for n in ticket_names),
            f"A ticket for M1A-100a-2 must be in the epic. Got: {sorted(ticket_names)}"
        )

    # -----------------------------------------------------------------------
    # Test 2 — cross-tree prerequisite is included in the epic
    # -----------------------------------------------------------------------

    def test_cross_tree_prerequisite_included_in_epic(self) -> None:
        # covers: BO-2600a-4
        """THE KEY discriminating test for BO-2600a-4.

        A leaf AC (CTP-100a-1) has a genuine OUT-OF-SUBTREE (cross-tree)
        prerequisite (CTP-200a-1). The test asserts that the --ids composition
        INCLUDES CTP-200a-1 as a ticket in the epic.

        Why this is discriminating — the old buggy design would fail here:
          - Old design: goal_to_epic.py --ac CTP-100a-1
            → calls traverse_ac_tree("CTP-100a-1", ac_root)
            → CTP-100a-1 is a leaf (L2, no covered_by children)
            → traverse_ac_tree returns only ["CTP-100a-1"]
            → epic has only 1 ticket (CTP-100a-1); CTP-200a-1 is DROPPED
          - New design (this test): select_connected + goal_to_epic --ids
            → select_connected finds CTP-200a-1 as an unmet depends_on dep
            → fast_lane returns ["CTP-200a-1", "CTP-100a-1"] (both members)
            → goal_to_epic --ids takes the full list as authoritative
            → epic has 2 tickets, CTP-200a-1 IS present

        A GE-113c-3-style fixture where connected-set == subtree is INSUFFICIENT
        because it would pass even against the buggy --ac re-walk. This fixture
        uses a genuine out-of-subtree dep (different prefix: CTP-200a-1 is NOT
        under CTP-100a, derive_parent_id("CTP-100a-1") = "CTP-100a" ≠ "CTP-200a-1").

        Fixture:
          CTP-100a-1 (L2) depends_on ["CTP-200a-1"]  ← target, A-subtree
          CTP-200a-1 (L2) no deps                     ← cross-tree prerequisite

        derive_parent_id("CTP-100a-1") = "CTP-100a"
        Since "CTP-200a-1" ≠ "CTP-100a", --exclude-structural-parent still
        includes CTP-200a-1 in the connected set (it is a genuine cross-tree dep,
        not a structural-parent pseudo-dep).
        """
        # Fixture: A-subtree leaf depends on B-subtree leaf (genuine cross-tree dep).
        _write_ac(self.ac_root, "CTP-200a-1", level="L2", work_status="todo")
        _write_ac(self.ac_root, "CTP-100a-1", level="L2", work_status="todo",
                  depends_on=["CTP-200a-1"])

        # Step 1: Resolve the connected build set with structural-parent exclusion.
        connected_set = _run_select_connected(
            "CTP-100a-1",
            self.ac_root,
            exclude_structural_parent=True,
        )

        # Cross-tree prerequisite must appear in the connected set.
        self.assertIn(
            "CTP-200a-1", connected_set,
            f"Cross-tree prerequisite CTP-200a-1 must be in the connected set. "
            f"Got: {connected_set}. "
            f"(BO-2600a-4: the connected set must include all unmet deps, not "
            f"just the subtree leaves.)"
        )
        self.assertIn(
            "CTP-100a-1", connected_set,
            f"Target CTP-100a-1 must be in its own connected set. Got: {connected_set}"
        )
        self.assertGreater(
            len(connected_set), 1,
            f"Connected set must have >1 member. Got: {connected_set}"
        )

        # Step 2: Build the epic from the full connected set (--ids composition).
        epic_folder = _run_goal_to_epic_ids(connected_set, self.ac_root, self.inbox_dir)

        self.assertTrue(
            epic_folder.is_dir(),
            f"goal_to_epic.py --ids must produce an epic folder. Got: {epic_folder!r}"
        )

        tickets = _ticket_files(epic_folder)
        ticket_names = {t.name for t in tickets}

        # KEY assertion: cross-tree prerequisite MUST be a ticket in the epic.
        self.assertTrue(
            any("CTP-200a-1" in n for n in ticket_names),
            f"The cross-tree prerequisite CTP-200a-1 MUST appear as a ticket in "
            f"the epic folder. Got tickets: {sorted(ticket_names)}. "
            f"(BO-2600a-4 discriminating assertion: the old goal_to_epic --ac path "
            f"calls traverse_ac_tree which walks only the target's subtree and "
            f"DROPS CTP-200a-1; the --ids composition takes the full select_connected "
            f"result as authoritative and preserves the cross-tree dep.)"
        )
        self.assertTrue(
            any("CTP-100a-1" in n for n in ticket_names),
            f"Target CTP-100a-1 must be a ticket in the epic. Got: {sorted(ticket_names)}"
        )
        self.assertEqual(
            len(tickets), 2,
            f"Epic must have exactly 2 tickets (one per connected-set member). "
            f"Got {len(tickets)}: {sorted(ticket_names)}"
        )

    # -----------------------------------------------------------------------
    # Test 3 — epic tickets are dependency-ordered and depends_on is wired
    # -----------------------------------------------------------------------

    def test_epic_tickets_dependency_ordered_and_wired(self) -> None:
        # covers: BO-2600a-4
        """Generated epic tickets are prerequisites-first and their depends_on
        field references co-located ticket filenames so ticket_frontmatter_guard
        would pass.

        Fixture:
          DEP-200a-1 (L2) no deps              ← prerequisite (must get 01_ prefix)
          DEP-100a-1 (L2) depends_on DEP-200a-1 ← dependent  (must get 02_ prefix)

        After the composition (select_connected → goal_to_epic --ids):
          01_TICKET-DEP-200a-1.md  — no depends_on entries
          02_TICKET-DEP-100a-1.md  — depends_on: ["01_TICKET-DEP-200a-1.md"]
                                         (ticket filename, NOT raw AC id "DEP-200a-1")

        Assertions (BO-2600a-4 AC-1 and AC-2):
          1. DEP-200a-1 ticket has a LOWER numeric prefix than DEP-100a-1.
          2. DEP-100a-1's depends_on in the epic folder ends with ".md"
             (references a co-located ticket filename, not a raw AC id).
          3. DEP-100a-1's depends_on contains "DEP-200a-1" (identifies the right ticket).

        This mirrors what ticket_frontmatter_guard requires: depends_on must
        reference co-located .md files, not raw AC ids.
        """
        # Fixture: linear dependency chain.
        _write_ac(self.ac_root, "DEP-200a-1", level="L2", work_status="todo")
        _write_ac(self.ac_root, "DEP-100a-1", level="L2", work_status="todo",
                  depends_on=["DEP-200a-1"])

        # Step 1: Resolve connected set.
        connected_set = _run_select_connected(
            "DEP-100a-1",
            self.ac_root,
            exclude_structural_parent=True,
        )

        self.assertIn("DEP-200a-1", connected_set,
                      f"Prerequisite DEP-200a-1 must be in connected set. Got: {connected_set}")
        self.assertIn("DEP-100a-1", connected_set,
                      f"Target DEP-100a-1 must be in connected set. Got: {connected_set}")

        # Dependency order from select_connected: prerequisite must come first.
        dep200_idx = connected_set.index("DEP-200a-1")
        dep100_idx = connected_set.index("DEP-100a-1")
        self.assertLess(
            dep200_idx, dep100_idx,
            f"select_connected must list prerequisite DEP-200a-1 BEFORE its "
            f"dependent DEP-100a-1 (topological order). "
            f"Got order: {connected_set}"
        )

        # Step 2: Build the epic from the connected set.
        epic_folder = _run_goal_to_epic_ids(connected_set, self.ac_root, self.inbox_dir)

        tickets = _ticket_files(epic_folder)
        self.assertEqual(
            len(tickets), 2,
            f"Epic must contain exactly 2 ticket files. Got: {[t.name for t in tickets]}"
        )

        # Assert numeric-prefix order: DEP-200a-1 (prerequisite) must have a
        # lower prefix (e.g. 01_) than DEP-100a-1 (dependent, e.g. 02_).
        dep200_ticket = next((t for t in tickets if "DEP-200a-1" in t.name), None)
        dep100_ticket = next((t for t in tickets if "DEP-100a-1" in t.name), None)

        self.assertIsNotNone(
            dep200_ticket,
            f"Ticket for DEP-200a-1 must be in the epic folder. "
            f"Got: {[t.name for t in tickets]}"
        )
        self.assertIsNotNone(
            dep100_ticket,
            f"Ticket for DEP-100a-1 must be in the epic folder. "
            f"Got: {[t.name for t in tickets]}"
        )

        # Lower prefix on prerequisite: dep200 filename < dep100 filename
        # (lexicographic on "01_..." vs "02_..." works for up to 99 tickets).
        self.assertLess(
            dep200_ticket.name,
            dep100_ticket.name,
            f"Prerequisite DEP-200a-1 ticket must have a lower numeric prefix "
            f"(e.g. 01_) than dependent DEP-100a-1 (e.g. 02_). "
            f"Got: {dep200_ticket.name!r} vs {dep100_ticket.name!r}. "
            f"(BO-2600a-4: tickets must be dependency-ordered — prerequisites first.)"
        )

        # Assert depends_on wiring: DEP-100a-1's ticket must reference the
        # DEP-200a-1 TICKET FILE (not the raw AC id) in its depends_on field.
        fm = _read_frontmatter(dep100_ticket)
        depends_on: list = fm.get("depends_on") or []

        self.assertGreater(
            len(depends_on), 0,
            f"DEP-100a-1's epic ticket must have non-empty depends_on (it depends "
            f"on DEP-200a-1). Frontmatter: {fm!r}"
        )

        dep_entry = str(depends_on[0])
        self.assertTrue(
            dep_entry.endswith(".md"),
            f"depends_on entry must be a ticket filename ending in .md, not a raw "
            f"AC id. Got: {dep_entry!r}. "
            f"(BO-2600a-4: AC-id → ticket-file translation must happen so "
            f"ticket_frontmatter_guard passes on the assembled epic.)"
        )
        self.assertIn(
            "DEP-200a-1", dep_entry,
            f"The ticket filename in depends_on must reference the DEP-200a-1 ticket. "
            f"Got: {dep_entry!r}."
        )
        self.assertNotEqual(
            dep_entry, "DEP-200a-1",
            f"depends_on must NOT be the raw AC id 'DEP-200a-1' — it must be "
            f"a co-located ticket filename ending in .md. Got: {dep_entry!r}."
        )


if __name__ == "__main__":
    unittest.main()
