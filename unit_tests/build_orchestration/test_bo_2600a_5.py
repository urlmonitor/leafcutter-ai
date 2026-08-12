"""
MODULE: unit_tests/build_orchestration/test_bo_2600a_5.py
GOAL: RED test stubs for BO-2600a-5 — build_epic_from_ids() id-list entrypoint
      in scripts/goal_to_epic.py.

All 5 tests are RED until python-coder implements build_epic_from_ids() in
scripts/goal_to_epic.py.  The attribute-not-found error (build_epic_from_ids
missing from the module) IS the intended red state for every test in this file.

=== Interface contract defined by these tests (for python-coder to implement) ===

Location: scripts/goal_to_epic.py

    build_epic_from_ids(
        ids: list[str],
        *,
        store_root: Path,
        inbox_dir: Path,
    ) -> Path

Assembles a dependency-ordered EPIC folder from EXACTLY the provided leaf AC
id list, reusing existing internals:
    resolve_leaf_dependencies(ids, store_root)  — restricted to the given set
    topological_sort(dep_graph)
    generate_tickets_for_leaves(topo_order, store_root, inbox_dir)
    assemble_epic_folder(ticket_paths, epic_name, inbox_dir)
    generate_master_plan(...)

Does NOT call traverse_ac_tree() — that is the exact defect this AC closes.
Translates depends_on AC ids to co-located ticket filenames at generation time.
Writes repo-relative (not absolute) paths into AC YAML implemented_by fields.
Preserves the existing run() function unchanged (backward compatible).

=== Fixture authenticity mandate ===

All AC YAML fixtures written via yaml.safe_dump (not hand-typed YAML literals),
following the pattern established in test_fast_lane_connected.py and
test_bo_2600a_1.py.  Ticket markdown frontmatter also produced via yaml.safe_dump.

=== Red baseline ===

All 5 tests fail immediately in _require_impl() because build_epic_from_ids
is not yet an attribute of goal_to_epic:

    AssertionError: build_epic_from_ids not found in goal_to_epic — ...

The AttributeError / AssertionError IS the intended red state.  After python-coder
implements build_epic_from_ids(), the tests describe the exact GREEN contract.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

# ---------------------------------------------------------------------------
# Repo path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# ---------------------------------------------------------------------------
# Import attempt — build_epic_from_ids not yet implemented.
# getattr returns None, making _FUNC_IMPORT_OK = False.
# This IS the intended red state.
# ---------------------------------------------------------------------------

_FUNC_IMPORT_OK = False
_FUNC_IMPORT_ERR = ""
build_epic_from_ids = None
_gte = None  # module-level reference so test_3 can inspect run() and getsource()

try:
    import goal_to_epic as _gte  # noqa: E402
    build_epic_from_ids = getattr(_gte, "build_epic_from_ids", None)
    if build_epic_from_ids is None:
        _FUNC_IMPORT_ERR = (
            "build_epic_from_ids attribute not found in goal_to_epic module — "
            "the function has not been implemented yet"
        )
    else:
        _FUNC_IMPORT_OK = True
except ImportError as exc:
    _FUNC_IMPORT_ERR = f"ImportError loading goal_to_epic: {exc}"


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
    implemented_by: list | None = None,
) -> Path:
    """Write a minimal AC YAML file using yaml.safe_dump (fixture-authenticity mandate).

    Mirrors the helper in test_fast_lane_connected.py and test_bo_2600a_1.py.
    No hand-typed YAML literals — always serialised via yaml.safe_dump.

    Args:
        ac_root: Root of the synthetic AC store.
        ac_id: AC identifier (e.g. "BO-5A1").
        level: "L0", "L1", "L2", or "L3".
        work_status: "todo" or "done".
        readiness: "approved", "draft", or "reviewed" (default: "approved").
        depends_on: List of AC ids this AC depends on.
        covered_by: List of child AC ids (for parent nodes).
        implemented_by: List of ticket paths already written into this AC.

    Returns:
        Path to the written YAML file.
    """
    subdir = ac_root / "test-component"
    subdir.mkdir(parents=True, exist_ok=True)
    data: dict = {
        "id": ac_id,
        "title": f"Test AC {ac_id}",
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
        "implemented_by": implemented_by if implemented_by is not None else [],
        "superseded_by": None,
    }
    path = subdir / f"{ac_id}.yaml"
    # Fixture-authenticity mandate: use yaml.safe_dump, never a hand-typed literal.
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _make_fake_ticket_writer(
    ac_root: Path,
    dep_map: dict[str, list[str]] | None = None,
) -> object:
    """Return a side_effect callable for patching goal_to_epic._call_generate_ticket_from_ac.

    Simulates generate_ticket_from_ac.py by:
    1. Writing a minimal ticket .md file whose frontmatter is produced via yaml.safe_dump
       (fixture-authenticity mandate — no hand-typed YAML strings).
    2. Writing depends_on as raw AC ids (the untranslated state — build_epic_from_ids
       must translate these to ticket filenames in the epic folder).
    3. Writing the AC YAML's implemented_by with a REPO-RELATIVE path, matching what
       generate_ticket_from_ac.py actually writes:
           relative_ticket_path = str(ticket_path.relative_to(worktree))
       where worktree = tickets_root.parent.parent (stripping "tickets/00_inbox").
    4. Returning the absolute ticket path string (matching the "Written: <abs>" stdout line).

    Args:
        ac_root: AC YAML store root (used to update implemented_by in source YAML).
        dep_map: Optional {ac_id: [dep_ac_id, ...]} — raw AC ids to write in depends_on.
                 When absent, depends_on is [] for every ticket.

    Returns:
        Callable matching _call_generate_ticket_from_ac(ac_id, ac_root, tickets_root) -> str.
    """
    dep_map = dep_map or {}

    def _writer(ac_id: str, _ac_root_param: Path, tickets_root: Path) -> str:
        """Write a fake ticket file and update the AC YAML's implemented_by."""
        deps = dep_map.get(ac_id, [])

        # Build frontmatter dict; yaml.safe_dump produces the YAML text.
        fm: dict = {
            "source_ac": ac_id,
            "title": f"Ticket for {ac_id}",
            "depends_on": deps,          # raw AC ids — to be translated by build_epic_from_ids
            "agents": {"python-coder": "needed"},
            "components": ["test-component"],
            "status": "todo",
            "created": "2026-08-11",
        }
        ticket_name = f"TICKET-{ac_id}.md"
        ticket_path = tickets_root / ticket_name
        # Fixture-authenticity: YAML frontmatter produced by yaml.safe_dump, not hand-typed.
        content = f"---\n{yaml.safe_dump(fm, allow_unicode=True)}---\n\n# Ticket for {ac_id}\n"
        ticket_path.write_text(content, encoding="utf-8")

        abs_ticket_path = ticket_path.resolve()

        # Simulate generate_ticket_from_ac.py writing implemented_by as a repo-relative path.
        # tickets_root == <worktree>/tickets/00_inbox, so worktree = tickets_root.parent.parent.
        worktree_root = tickets_root.resolve().parent.parent
        try:
            rel_path = str(abs_ticket_path.relative_to(worktree_root))
        except ValueError:
            rel_path = str(abs_ticket_path)

        # Update the AC YAML's implemented_by (using the closure ac_root for the scan).
        for yaml_path in sorted(ac_root.rglob("*.yaml")):
            try:
                with open(yaml_path, encoding="utf-8") as fh:
                    ac_data = yaml.safe_load(fh)
            except (yaml.YAMLError, OSError):
                continue
            if isinstance(ac_data, dict) and ac_data.get("id") == ac_id:
                ac_data["implemented_by"] = [rel_path]
                yaml_path.write_text(yaml.safe_dump(ac_data, allow_unicode=True), encoding="utf-8")
                break

        return str(abs_ticket_path)

    return _writer


def _read_ticket_frontmatter(ticket_path: Path) -> dict:
    """Parse YAML frontmatter from a ticket markdown file.

    Mirrors _read_ticket_frontmatter() in goal_to_epic.py (read-only copy
    for test assertions — does not import from production code).

    Args:
        ticket_path: Path to a ticket markdown file.

    Returns:
        Parsed frontmatter dict, or empty dict on failure.
    """
    try:
        content = ticket_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return {}
    yaml_text = "\n".join(lines[1:end_idx])
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Tests for BO-2600a-5
# ---------------------------------------------------------------------------


class TestBuildEpicFromIds(unittest.TestCase):
    """BO-2600a-5 — build_epic_from_ids() id-list entrypoint in goal_to_epic.

    All tests are RED until python-coder implements build_epic_from_ids() in
    scripts/goal_to_epic.py.  _require_impl() fails immediately with the
    "build_epic_from_ids not found" error IS the intended red state.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        # inbox_dir follows the conventional <worktree>/tickets/00_inbox shape so
        # _derive_worktree_from_inbox(inbox_dir) == tmp (the "worktree root").
        # This is required for the repo-relative implemented_by path logic to work.
        self.ac_root = tmp / "ac_store"
        self.inbox_dir = tmp / "tickets" / "00_inbox"
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.ac_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _require_impl(self) -> None:
        """Fail with a clear message when build_epic_from_ids is not yet implemented."""
        if not _FUNC_IMPORT_OK:
            self.fail(
                f"build_epic_from_ids not found in goal_to_epic — "
                f"AttributeError/ImportError is the intended red state; "
                f"python-coder must implement it in scripts/goal_to_epic.py. "
                f"Error: {_FUNC_IMPORT_ERR}"
            )

    # -----------------------------------------------------------------------
    # Test 1
    # -----------------------------------------------------------------------

    def test_build_epic_from_ids_uses_exact_set(self) -> None:
        # covers: BO-2600a-5
        """AC-1/AC-2/AC-3: build_epic_from_ids builds tickets for EXACTLY the provided ids.

        Scenario: two separate AC subtrees.
          BO-5A0 (L0) → BO-5A1 (L2)   ← A-tree leaf; depends_on BO-5B1 (cross-tree)
          BO-5B0 (L0) → BO-5B1 (L2)   ← B-tree leaf; standalone

        Provided id list: ["BO-5B1", "BO-5A1"]

        Expected: epic folder contains exactly 2 ticket files — one per id.

        The root defect this AC closes: the existing run() calls traverse_ac_tree()
        which walks only A-tree from a single root AC, so BO-5B1 (cross-tree
        prerequisite) gets dropped.  build_epic_from_ids() MUST include BO-5B1
        because it was explicitly provided in the id list.

        To make this green: implement build_epic_from_ids() that:
            1. Takes the id list as authoritative — no traverse_ac_tree() call.
            2. Calls resolve_leaf_dependencies(ids, store_root) restricted to the set.
            3. topological_sort → generate_tickets_for_leaves → assemble_epic_folder.
            4. Returns the assembled epic folder Path.
        """
        self._require_impl()

        # Fixture: A-tree leaf depends on B-tree leaf (cross-tree prerequisite).
        _write_ac(self.ac_root, "BO-5A0", level="L0", work_status="todo",
                  covered_by=["BO-5A1"])
        _write_ac(self.ac_root, "BO-5A1", level="L2", work_status="todo",
                  depends_on=["BO-5B1"])
        _write_ac(self.ac_root, "BO-5B0", level="L0", work_status="todo",
                  covered_by=["BO-5B1"])
        _write_ac(self.ac_root, "BO-5B1", level="L2", work_status="todo")

        writer = _make_fake_ticket_writer(self.ac_root)
        with patch("goal_to_epic._call_generate_ticket_from_ac", side_effect=writer):
            epic_folder = build_epic_from_ids(
                ["BO-5B1", "BO-5A1"],   # B first (it is A's prereq)
                store_root=self.ac_root,
                inbox_dir=self.inbox_dir,
            )

        self.assertIsNotNone(epic_folder, "build_epic_from_ids must return a path.")
        epic_path = Path(epic_folder)
        self.assertTrue(epic_path.exists(), "The returned epic folder must exist on disk.")

        # Count ticket files (exclude Master_Plan.md).
        ticket_files = [
            f for f in epic_path.iterdir()
            if f.suffix == ".md" and f.name != "Master_Plan.md"
        ]
        self.assertEqual(
            len(ticket_files),
            2,
            f"Epic folder must contain exactly 2 ticket files — one per provided id. "
            f"Got {len(ticket_files)}: {sorted(f.name for f in ticket_files)}. "
            f"(BO-2600a-5: EXACTLY the provided ids, no more, no less.)"
        )

        names = {f.name for f in ticket_files}
        self.assertTrue(
            any("BO-5A1" in n for n in names),
            f"A ticket for BO-5A1 must be in the epic folder. Got: {sorted(names)}"
        )
        self.assertTrue(
            any("BO-5B1" in n for n in names),
            f"A ticket for BO-5B1 (cross-tree prerequisite) must be in the epic folder "
            f"— it must NOT be dropped because it was explicitly provided in the id list. "
            f"(BO-2600a-5 AC-3: does NOT re-derive the set by walking a single AC's subtree.) "
            f"Got: {sorted(names)}"
        )

    # -----------------------------------------------------------------------
    # Test 2
    # -----------------------------------------------------------------------

    def test_build_epic_from_ids_dependency_ordered_and_wired(self) -> None:
        # covers: BO-2600a-5
        """AC-4: generated tickets are prerequisites-first and depends_on references
        co-located ticket FILES (not raw AC ids) so ticket_frontmatter_guard passes.

        Scenario:
          BO-5C1 (L2) — no dependencies
          BO-5C2 (L2) — depends_on: ["BO-5C1"]

        Expected epic folder layout (prerequisite-first order):
          01_TICKET-BO-5C1.md  — no depends_on
          02_TICKET-BO-5C2.md  — depends_on: ["01_TICKET-BO-5C1.md"]
                                     (ticket filename, not raw AC id "BO-5C1")

        To make this green: implement build_epic_from_ids() that:
            1. Calls topological_sort so prerequisites receive lower numeric prefixes.
            2. After assembling the epic folder, translates each ticket's depends_on
               from raw AC ids to co-located ticket filenames.
        """
        self._require_impl()

        _write_ac(self.ac_root, "BO-5C1", level="L2", work_status="todo")
        _write_ac(self.ac_root, "BO-5C2", level="L2", work_status="todo",
                  depends_on=["BO-5C1"])

        dep_map = {
            "BO-5C1": [],             # no deps
            "BO-5C2": ["BO-5C1"],    # raw AC id — build_epic_from_ids must translate to ticket file
        }
        writer = _make_fake_ticket_writer(self.ac_root, dep_map=dep_map)
        with patch("goal_to_epic._call_generate_ticket_from_ac", side_effect=writer):
            epic_folder = build_epic_from_ids(
                ["BO-5C1", "BO-5C2"],
                store_root=self.ac_root,
                inbox_dir=self.inbox_dir,
            )

        epic_path = Path(epic_folder)
        ticket_files = sorted(
            f for f in epic_path.iterdir()
            if f.suffix == ".md" and f.name != "Master_Plan.md"
        )

        self.assertEqual(
            len(ticket_files), 2,
            f"Expected 2 ticket files. Got: {[f.name for f in ticket_files]}"
        )

        # First file (lowest prefix) must be BO-5C1 (the prerequisite).
        first = ticket_files[0]
        self.assertIn(
            "BO-5C1",
            first.name,
            f"First ticket (lowest prefix) must be BO-5C1 — the prerequisite must "
            f"appear before its dependent (dependency order). Got: {first.name}. "
            f"(BO-2600a-5 AC-4: topological sort ensures prerequisites come first.)"
        )

        # Second file must be BO-5C2; its depends_on must reference a ticket FILE.
        second = ticket_files[1]
        self.assertIn(
            "BO-5C2",
            second.name,
            f"Second ticket must be BO-5C2. Got: {second.name}."
        )

        fm = _read_ticket_frontmatter(second)
        depends_on: list = fm.get("depends_on") or []
        self.assertGreater(
            len(depends_on),
            0,
            f"BO-5C2's ticket must have a non-empty depends_on list in the epic folder. "
            f"Frontmatter: {fm!r}"
        )

        dep_entry = str(depends_on[0])
        self.assertTrue(
            dep_entry.endswith(".md"),
            f"depends_on entry must be a ticket filename (ending in .md), not a raw AC id. "
            f"Got: {dep_entry!r}. "
            f"(BO-2600a-5 AC-4: AC-id → ticket-file translation must happen at generation "
            f"time so ticket_frontmatter_guard passes without a downstream hook auto-fix.)"
        )
        self.assertNotEqual(
            dep_entry,
            "BO-5C1",
            f"depends_on must NOT contain the raw AC id 'BO-5C1'. "
            f"Got: {dep_entry!r}. "
            f"(BO-2600a-5: translate to the co-located ticket filename.)"
        )
        self.assertIn(
            "BO-5C1",
            dep_entry,
            f"The ticket filename in depends_on must reference the BO-5C1 ticket. "
            f"Got: {dep_entry!r}."
        )

    # -----------------------------------------------------------------------
    # Test 3
    # -----------------------------------------------------------------------

    def test_ac_mode_preserved_backward_compatible(self) -> None:
        # covers: BO-2600a-5
        """AC-5: the existing single-AC --ac mode (run()) is unchanged after adding
        build_epic_from_ids.

        Verifies three backward-compatibility properties:

        1. Both build_epic_from_ids and run() are callable in goal_to_epic
           (the new function is additive — it does not replace run()).

        2. run() still has its original key parameters (ac_id, ac_store_root,
           inbox_dir) — adding build_epic_from_ids must not alter run()'s signature.

        3. build_epic_from_ids does NOT call traverse_ac_tree — the function must
           use the provided id set directly, never re-walk a subtree.  This is the
           exact defect this AC closes: traverse_ac_tree drops cross-tree
           prerequisites by re-deriving the set from a single AC's subtree.

        These three properties together guarantee that callers of the existing --ac
        path are completely unaffected by the new --ids path.

        To make this green: implement build_epic_from_ids() WITHOUT calling
        traverse_ac_tree, and do NOT modify run()'s signature or behaviour.
        """
        self._require_impl()

        import inspect

        # 1. Both functions must be callable in goal_to_epic.
        self.assertTrue(
            callable(build_epic_from_ids),
            "build_epic_from_ids must be callable in goal_to_epic. (BO-2600a-5 AC-1)"
        )
        self.assertIsNotNone(
            _gte,
            "goal_to_epic module must be importable."
        )
        self.assertTrue(
            callable(getattr(_gte, "run", None)),
            "run() must still be callable in goal_to_epic after adding build_epic_from_ids. "
            "(BO-2600a-5 AC-5: backward compatible — existing callers unaffected.)"
        )

        # 2. run() signature must still include its original key parameters.
        run_sig = inspect.signature(_gte.run)
        run_params = list(run_sig.parameters)
        for expected_param in ("ac_id", "ac_store_root", "inbox_dir"):
            self.assertIn(
                expected_param,
                run_params,
                f"run() must still accept '{expected_param}' parameter (unchanged signature). "
                f"Got params: {run_params}. "
                f"(BO-2600a-5 AC-5: --ac mode backward compatible.)"
            )

        # 3. build_epic_from_ids must NOT call traverse_ac_tree.
        #    Inspecting source code is the definitive check: the root defect is exactly
        #    that traverse_ac_tree re-walks a subtree and drops cross-tree prerequisites.
        src = inspect.getsource(build_epic_from_ids)
        self.assertNotIn(
            "traverse_ac_tree",
            src,
            "build_epic_from_ids must NOT call traverse_ac_tree. "
            "The function must operate only on the provided id set. "
            "(BO-2600a-5 AC-3: the defect this AC closes — traverse_ac_tree re-derives "
            "the set from a single AC's subtree and drops cross-tree prerequisites.)"
        )

    # -----------------------------------------------------------------------
    # Test 4
    # -----------------------------------------------------------------------

    def test_implemented_by_written_repo_relative(self) -> None:
        # covers: BO-2600a-5
        """Hygiene fix: implemented_by back-refs written into source AC YAMLs must be
        repo-relative (start with "tickets/"), never absolute worktree paths.

        Reproduces the observed defect from the BO-2600 three-angle review:
        goal_to_epic wrote a full /home/.../worktrees/... path into
        BO-2600a-4.implemented_by.

        Test setup uses inbox_dir = <tmp>/tickets/00_inbox (conventional shape) so
        _derive_worktree_from_inbox(inbox_dir) == <tmp>, enabling the repo-relative
        path computation inside build_epic_from_ids.

        The fake ticket writer simulates generate_ticket_from_ac.py by writing a
        repo-relative (not absolute) path into implemented_by initially — matching
        the actual subprocess behaviour. build_epic_from_ids then replaces the loose
        ticket path with the assembled epic-folder path, which must also be
        repo-relative.

        To make this green: build_epic_from_ids must relativise the epic-folder ticket
        path against the worktree root (derived from inbox_dir by path math) before
        calling _replace_implemented_by_entry.
        """
        self._require_impl()

        _write_ac(self.ac_root, "BO-5D1", level="L2", work_status="todo")

        writer = _make_fake_ticket_writer(self.ac_root)
        with patch("goal_to_epic._call_generate_ticket_from_ac", side_effect=writer):
            build_epic_from_ids(
                ["BO-5D1"],
                store_root=self.ac_root,
                inbox_dir=self.inbox_dir,
            )

        # Read back the AC YAML and inspect implemented_by after the run.
        ac_yaml_path = next(self.ac_root.rglob("BO-5D1.yaml"), None)
        self.assertIsNotNone(
            ac_yaml_path,
            "BO-5D1.yaml must exist in the AC store."
        )
        with open(ac_yaml_path, encoding="utf-8") as fh:
            ac_data = yaml.safe_load(fh)

        implemented_by: list = ac_data.get("implemented_by") or []
        self.assertGreater(
            len(implemented_by),
            0,
            f"AC BO-5D1 must have at least one implemented_by entry after "
            f"build_epic_from_ids runs. Got: {implemented_by!r}"
        )

        for entry in implemented_by:
            entry_str = str(entry)
            self.assertFalse(
                entry_str.startswith("/"),
                f"implemented_by must NOT be an absolute path. Got: {entry_str!r}. "
                f"(BO-2600a-5 hygiene fix: observed defect — goal_to_epic wrote a "
                f"full /home/.../worktrees/... path into BO-2600a-4.implemented_by.)"
            )
            self.assertTrue(
                entry_str.startswith("tickets/"),
                f"implemented_by entry must be repo-relative (start with 'tickets/'). "
                f"Got: {entry_str!r}. "
                f"(BO-2600a-5: repo-relative paths like 'tickets/00_inbox/epics/...'"
                f" must be written, not absolute worktree paths.)"
            )

    # -----------------------------------------------------------------------
    # Test 5
    # -----------------------------------------------------------------------

    def test_generated_ticket_depends_on_are_ticket_files(self) -> None:
        # covers: BO-2600a-5
        """AC-4 (explicit): generated ticket depends_on entries in the assembled epic
        folder must reference co-located ticket FILENAMES (AC-id → ticket-file
        translation at generation time), not raw AC ids.

        Scenario:
          BO-5E1 (L2) — standalone
          BO-5E2 (L2) — depends_on: ["BO-5E1"] in both the AC YAML and the loose ticket

        After build_epic_from_ids(["BO-5E1", "BO-5E2"], ...):
          01_TICKET-BO-5E1.md — depends_on: []
          02_TICKET-BO-5E2.md — depends_on: ["01_TICKET-BO-5E1.md"]  ← ticket filename
                                NOT: depends_on: ["BO-5E1"]            ← raw AC id (wrong)

        This is the hygiene fix described in the implementation notes:
        the current --ac path relies on a downstream check-doc-frontmatter hook to
        auto-fix depends_on.  build_epic_from_ids must do the translation at generation
        time so the epic folder is self-consistent from the start.

        To make this green: after assembling the epic folder, build_epic_from_ids must
        rewrite each ticket's depends_on entries from raw AC ids to the corresponding
        co-located ticket filename (using the ac_id → ticket_path mapping from
        generate_tickets_for_leaves).
        """
        self._require_impl()

        _write_ac(self.ac_root, "BO-5E1", level="L2", work_status="todo")
        _write_ac(self.ac_root, "BO-5E2", level="L2", work_status="todo",
                  depends_on=["BO-5E1"])

        dep_map = {
            "BO-5E1": [],
            "BO-5E2": ["BO-5E1"],   # raw AC id written by the (fake) ticket generator
        }
        writer = _make_fake_ticket_writer(self.ac_root, dep_map=dep_map)
        with patch("goal_to_epic._call_generate_ticket_from_ac", side_effect=writer):
            epic_folder = build_epic_from_ids(
                ["BO-5E1", "BO-5E2"],
                store_root=self.ac_root,
                inbox_dir=self.inbox_dir,
            )

        epic_path = Path(epic_folder)

        # Find the BO-5E2 ticket in the epic folder.
        e2_ticket = next(
            (f for f in epic_path.iterdir()
             if "BO-5E2" in f.name and f.suffix == ".md"),
            None,
        )
        self.assertIsNotNone(
            e2_ticket,
            f"A ticket for BO-5E2 must exist in the epic folder. "
            f"Files: {sorted(f.name for f in epic_path.iterdir())}"
        )

        fm = _read_ticket_frontmatter(e2_ticket)
        depends_on: list = fm.get("depends_on") or []

        self.assertGreater(
            len(depends_on),
            0,
            f"BO-5E2's ticket in the epic folder must have depends_on entries "
            f"(it depends on BO-5E1). Frontmatter: {fm!r}"
        )

        for dep in depends_on:
            dep_str = str(dep)
            self.assertTrue(
                dep_str.endswith(".md"),
                f"Each depends_on entry must be a ticket filename ending in .md, "
                f"not a raw AC id. Got: {dep_str!r}. "
                f"(BO-2600a-5 AC-4: AC-id → ticket-file translation must occur at "
                f"generation time so ticket_frontmatter_guard passes on the assembled "
                f"epic without needing a downstream hook auto-fix.)"
            )
            self.assertNotEqual(
                dep_str,
                "BO-5E1",
                f"depends_on must NOT contain the raw AC id 'BO-5E1'. "
                f"Got: {dep_str!r}. "
                f"(BO-2600a-5: translate AC ids to co-located ticket filenames.)"
            )
            # Must reference the BO-5E1 ticket by name.
            self.assertIn(
                "BO-5E1",
                dep_str,
                f"The depends_on ticket filename must reference the BO-5E1 ticket. "
                f"Got: {dep_str!r}."
            )


    # -----------------------------------------------------------------------
    # Test 6 — CLI --ids mode (subprocess, real temp AC store)
    # -----------------------------------------------------------------------

    def test_ids_cli_invokes_build_epic_from_ids(self) -> None:
        # covers: BO-2600a-5
        """CLI: --ids flag routes to build_epic_from_ids; epic folder created and path printed.

        Runs goal_to_epic.py --ids id1,id2 --store-root <tmp> --inbox-dir <tmp>/tickets/00_inbox
        via subprocess against a real temp AC store (yaml.safe_dump fixtures, matching
        the fixture-authenticity mandate) and asserts:

        1. Process exits 0.
        2. The last non-empty stdout line is the absolute path to the assembled epic folder.
        3. The printed epic folder exists on disk.
        4. The epic folder contains exactly one ticket file per provided id (2 tickets total,
           excluding Master_Plan.md).

        This is the end-to-end smoke check for the --ids CLI mode: it exercises
        _build_parser() (mutually exclusive group), the routing block in main(), and
        build_epic_from_ids() through the real generate_ticket_from_ac.py subprocess.
        No mocking — runs the full pipeline against real fixtures.
        """
        import subprocess as _subprocess

        # Fixture: two independent leaf ACs with no inter-dependencies.
        # Use yaml.safe_dump (fixture-authenticity mandate — no hand-typed literals).
        _write_ac(self.ac_root, "BO-CLI1", level="L2", work_status="todo")
        _write_ac(self.ac_root, "BO-CLI2", level="L2", work_status="todo")

        script_path = _REPO_ROOT / "scripts" / "goal_to_epic.py"

        result = _subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--ids", "BO-CLI1,BO-CLI2",
                "--store-root", str(self.ac_root),
                "--inbox-dir", str(self.inbox_dir),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertEqual(
            result.returncode, 0,
            f"goal_to_epic.py --ids must exit 0. Got {result.returncode}.\n"
            f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )

        # Assert: the last non-empty stdout line is the epic folder path.
        stdout_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        self.assertTrue(
            stdout_lines,
            f"Expected at least one line of stdout. Got empty. "
            f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )
        epic_folder_str = stdout_lines[-1]
        epic_path = Path(epic_folder_str)

        self.assertTrue(
            epic_path.is_dir(),
            f"The path printed on the last stdout line must be an existing directory. "
            f"Got: {epic_folder_str!r}. "
            f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )

        # Assert: exactly one ticket file per provided id (2 total, no Master_Plan.md).
        ticket_files = [
            f for f in epic_path.iterdir()
            if f.suffix == ".md" and f.name != "Master_Plan.md"
        ]
        self.assertEqual(
            len(ticket_files), 2,
            f"Epic folder must contain exactly 2 ticket files (one per id), excluding "
            f"Master_Plan.md. Got {len(ticket_files)}: {sorted(f.name for f in ticket_files)}. "
            f"Epic folder contents: {sorted(f.name for f in epic_path.iterdir())}. "
            f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )


if __name__ == "__main__":
    unittest.main()
