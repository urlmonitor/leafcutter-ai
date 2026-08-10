"""
MODULE: unit_tests/build_orchestration/test_fast_lane_connected.py
GOAL: RED test stubs for BO-2400f-1 (resolve connected build set) and
      BO-2400f-2 (readiness-agnostic selection; empty set is a clean no-op).

=== Interface contract defined by these tests (for python-coder to implement) ===

Location: scripts/build_orchestration/fast_lane.py

    resolve_connected_build_set(
        ac_id: str,
        *,
        ac_root: Path,
    ) -> list[str]

        Resolve the connected build set for *ac_id* and return leaf AC ids in
        dependency order.

        The connected build set is defined as:
            subtree(ac_id)  UNION  transitive_unmet_depends_on_closure(ac_id)

        Where:
        - subtree(ac_id): all L2/L3 ACs that are descendants of ac_id via
          the covered_by links, plus ac_id itself when it is a leaf (L2/L3).
        - transitive_unmet_depends_on_closure: all L2/L3 ACs that are direct
          or transitive prerequisites (via depends_on) for any AC in the set
          and that are not yet work_status: done.

        Rules:
        - ONLY L2/L3 ACs with work_status != 'done' are included.
        - Readiness is NOT a filter: not-done leaves with readiness 'draft' or
          'reviewed' ARE included (unlike select_batch which requires 'approved').
        - Result is in dependency order: a prerequisite leaf appears BEFORE any
          leaf that (transitively) depends on it.
        - Dependency cycles are broken deterministically (no infinite loop).
        - If the whole connected set is already done, returns [].
        - If *ac_id* does not exist in the store, raises a clear exception whose
          message names the missing id (does NOT return an empty list silently).
        - Same store state => identical ordered list on every call (deterministic).

CLI contract:

    python fast_lane.py select_connected \\
        --ac <id>       # target AC id to resolve
        --ac-root <dir> # root of the AC YAML store

    Output: one JSON-encoded line to stdout — a list of AC id strings.
    Exit code: 0 on success; non-zero when *ac_id* is not found in the store.

=== Fixture-authenticity mandate ===

All AC YAML fixtures are written with yaml.safe_dump (not hand-typed YAML
literals), following the same pattern as test_bo2400a_fast_lane.py and
test_fast_lane_cli.py.

=== Red baseline ===

All tests are RED until python-coder implements resolve_connected_build_set()
in scripts/build_orchestration/fast_lane.py and adds the select_connected CLI
subcommand. The ImportError produced by the missing function IS the intended
red state for the unit tests. The JSONDecodeError / non-zero exit IS the
intended red state for the CLI tests.
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
# Repo path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_MODULE_DIR = _REPO_ROOT / "scripts" / "build_orchestration"
if str(_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULE_DIR))

_SCRIPT_PATH = _MODULE_DIR / "fast_lane.py"

# ---------------------------------------------------------------------------
# Import resolve_connected_build_set — not yet implemented.
# ImportError IS the intended red state for unit tests.
# ---------------------------------------------------------------------------

_FUNC_IMPORT_OK = False
_FUNC_IMPORT_ERR = ""
resolve_connected_build_set = None  # type: ignore[assignment]

try:
    from fast_lane import resolve_connected_build_set  # noqa: E402
    _FUNC_IMPORT_OK = True
except (ImportError, AttributeError) as _exc:
    _FUNC_IMPORT_ERR = str(_exc)


# ---------------------------------------------------------------------------
# Fixture helpers
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
    """Write a minimal AC YAML file using yaml.safe_dump (fixture-authenticity mandate).

    Mirrors the helpers in test_bo2400a_fast_lane.py and test_fast_lane_cli.py:
    no hand-typed YAML, always serialised via yaml.safe_dump.

    Args:
        ac_root: Root of the synthetic AC store.
        ac_id: AC identifier (e.g. "BO-TST-A01").
        level: "L0", "L1", "L2", or "L3".
        work_status: "todo" or "done".
        readiness: "approved", "draft", or "reviewed" (default: "approved").
        depends_on: List of AC ids this AC depends on.
        covered_by: List of child AC ids (for parent nodes).

    Returns:
        Path to the written YAML file.
    """
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
    # Fixture-authenticity mandate: use yaml.safe_dump, not a hand-typed literal.
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _run_cli(args: list[str]) -> tuple[int, str, str]:
    """Run fast_lane.py as a CLI via subprocess.

    Args:
        args: CLI args after the script name.

    Returns:
        Tuple (returncode, stdout, stderr).
    """
    result = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH)] + args,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


# ---------------------------------------------------------------------------
# Unit tests — resolve_connected_build_set() Python function
# ---------------------------------------------------------------------------


class TestResolveConnectedBuildSetUnit(unittest.TestCase):
    """Unit tests for resolve_connected_build_set() — BO-2400f-1, BO-2400f-2.

    All tests are RED until python-coder implements the function. The ImportError
    from the missing implementation IS the intended red state.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.ac_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _require_impl(self) -> None:
        """Fail with a descriptive message when the function is not yet implemented."""
        if not _FUNC_IMPORT_OK:
            self.fail(
                f"resolve_connected_build_set not importable from fast_lane — "
                f"ImportError is the intended red state; python-coder must implement it. "
                f"Import error: {_FUNC_IMPORT_ERR}"
            )

    def test_ac1_connected_set_includes_subtree_leaves(self) -> None:
        # covers: BO-2400f-1
        """The connected set includes all not-done L2/L3 descendants via covered_by.

        A parent L0 with two L2 leaf children.  Both leaves must appear in the result.

        To make this green, resolve_connected_build_set must:
        1. Traverse covered_by links from the root AC to collect all L2/L3 descendants.
        2. Return them (excluding done leaves) as part of the connected set.
        """
        _write_ac(
            self.ac_root,
            "BO-TST-A00",
            level="L0",
            work_status="todo",
            covered_by=["BO-TST-A01", "BO-TST-A02"],
        )
        _write_ac(self.ac_root, "BO-TST-A01", level="L2", work_status="todo")
        _write_ac(self.ac_root, "BO-TST-A02", level="L2", work_status="todo")

        self._require_impl()

        result = resolve_connected_build_set("BO-TST-A00", ac_root=self.ac_root)

        self.assertIsInstance(result, list, "resolve_connected_build_set must return a list.")
        self.assertIn(
            "BO-TST-A01",
            result,
            "Subtree leaf BO-TST-A01 must be in the connected set (BO-2400f-1).",
        )
        self.assertIn(
            "BO-TST-A02",
            result,
            "Subtree leaf BO-TST-A02 must be in the connected set (BO-2400f-1).",
        )

    def test_ac1_cross_tree_dep_is_included(self) -> None:
        # covers: BO-2400f-1
        """An unmet depends_on prerequisite from another tree is included in the set.

        BO-TST-A01 depends_on BO-TST-B01 which lives in a different sub-tree.
        BO-TST-B01 is not done.  The connected set for BO-TST-A00 must include
        BO-TST-B01 (the cross-tree dependency).

        To make this green, resolve_connected_build_set must:
        1. Collect subtree leaves for BO-TST-A00: [BO-TST-A01]
        2. For BO-TST-A01.depends_on = [BO-TST-B01] (not done): add BO-TST-B01
        3. Include BO-TST-B01 in the result.
        """
        _write_ac(
            self.ac_root,
            "BO-TST-A00",
            level="L0",
            work_status="todo",
            covered_by=["BO-TST-A01"],
        )
        _write_ac(
            self.ac_root,
            "BO-TST-A01",
            level="L2",
            work_status="todo",
            depends_on=["BO-TST-B01"],
        )
        _write_ac(
            self.ac_root,
            "BO-TST-B00",
            level="L0",
            work_status="todo",
            covered_by=["BO-TST-B01"],
        )
        _write_ac(self.ac_root, "BO-TST-B01", level="L2", work_status="todo")

        self._require_impl()

        result = resolve_connected_build_set("BO-TST-A00", ac_root=self.ac_root)

        self.assertIn(
            "BO-TST-B01",
            result,
            "Cross-tree prerequisite BO-TST-B01 must be in the connected set "
            "(BO-TST-A01 depends_on BO-TST-B01 which is not done — BO-2400f-1). "
            "The set is subtree UNION transitive unmet depends_on closure.",
        )

    def test_ac1_dependency_order_prerequisite_appears_first(self) -> None:
        # covers: BO-2400f-1
        """A prerequisite leaf appears BEFORE the leaf that (transitively) depends on it.

        BO-TST-A01 depends_on BO-TST-B01.  In the ordered result, index(BO-TST-B01)
        must be less than index(BO-TST-A01).

        To make this green, resolve_connected_build_set must return results in
        topological (dependency) order: every prerequisite before its dependents.
        """
        _write_ac(
            self.ac_root,
            "BO-TST-A00",
            level="L0",
            work_status="todo",
            covered_by=["BO-TST-A01"],
        )
        _write_ac(
            self.ac_root,
            "BO-TST-A01",
            level="L2",
            work_status="todo",
            depends_on=["BO-TST-B01"],
        )
        _write_ac(
            self.ac_root,
            "BO-TST-B00",
            level="L0",
            work_status="todo",
            covered_by=["BO-TST-B01"],
        )
        _write_ac(self.ac_root, "BO-TST-B01", level="L2", work_status="todo")

        self._require_impl()

        result = resolve_connected_build_set("BO-TST-A00", ac_root=self.ac_root)

        self.assertIn("BO-TST-B01", result, "Prerequisite BO-TST-B01 must be in the result.")
        self.assertIn("BO-TST-A01", result, "Dependent BO-TST-A01 must be in the result.")

        idx_prereq = result.index("BO-TST-B01")
        idx_dep = result.index("BO-TST-A01")

        self.assertLess(
            idx_prereq,
            idx_dep,
            f"BO-TST-B01 (prerequisite) must appear BEFORE BO-TST-A01 (dependent) "
            f"in dependency order (BO-2400f-1). "
            f"Got: BO-TST-B01 at index {idx_prereq}, BO-TST-A01 at index {idx_dep}.",
        )

    def test_ac2_draft_readiness_leaf_is_included(self) -> None:
        # covers: BO-2400f-2
        """A not-done leaf with readiness: draft IS included — readiness-agnostic.

        Pointing at the AC is the operator's go-ahead; readiness does not filter
        the connected set (unlike select_batch which requires readiness: approved).

        To make this green, resolve_connected_build_set must NOT apply any
        readiness filter — every not-done L2/L3 leaf is in scope regardless of
        its readiness field.
        """
        _write_ac(
            self.ac_root,
            "BO-TST-E00",
            level="L0",
            work_status="todo",
            covered_by=["BO-TST-E01"],
        )
        _write_ac(
            self.ac_root,
            "BO-TST-E01",
            level="L2",
            work_status="todo",
            readiness="draft",  # NOT approved — but must still be included
        )

        self._require_impl()

        result = resolve_connected_build_set("BO-TST-E00", ac_root=self.ac_root)

        self.assertIn(
            "BO-TST-E01",
            result,
            "A not-done leaf with readiness: draft must be included in the connected "
            "set (readiness-agnostic — BO-2400f-2). "
            "resolve_connected_build_set differs from select_batch: it must include "
            "draft and reviewed leaves.",
        )

    def test_ac2_reviewed_readiness_leaf_is_included(self) -> None:
        # covers: BO-2400f-2
        """A not-done leaf with readiness: reviewed IS included — readiness-agnostic.

        Same as draft test: reviewed readiness must not exclude a not-done leaf.
        """
        _write_ac(
            self.ac_root,
            "BO-TST-G00",
            level="L0",
            work_status="todo",
            covered_by=["BO-TST-G01"],
        )
        _write_ac(
            self.ac_root,
            "BO-TST-G01",
            level="L2",
            work_status="todo",
            readiness="reviewed",  # NOT approved — but must still be included
        )

        self._require_impl()

        result = resolve_connected_build_set("BO-TST-G00", ac_root=self.ac_root)

        self.assertIn(
            "BO-TST-G01",
            result,
            "A not-done leaf with readiness: reviewed must be included "
            "(readiness-agnostic — BO-2400f-2).",
        )

    def test_ac2_done_leaf_is_excluded(self) -> None:
        # covers: BO-2400f-2
        """Already-done leaves (work_status: done) are NOT included in the connected set.

        BO-TST-C01 is done — must be excluded.
        BO-TST-C02 is todo — must be included.

        To make this green, resolve_connected_build_set must exclude any leaf
        whose work_status is 'done' from the result.
        """
        _write_ac(
            self.ac_root,
            "BO-TST-C00",
            level="L0",
            work_status="todo",
            covered_by=["BO-TST-C01", "BO-TST-C02"],
        )
        _write_ac(self.ac_root, "BO-TST-C01", level="L2", work_status="done")
        _write_ac(self.ac_root, "BO-TST-C02", level="L2", work_status="todo")

        self._require_impl()

        result = resolve_connected_build_set("BO-TST-C00", ac_root=self.ac_root)

        self.assertNotIn(
            "BO-TST-C01",
            result,
            "A done leaf (work_status: done) must NOT be in the connected set (BO-2400f-2).",
        )
        self.assertIn(
            "BO-TST-C02",
            result,
            "A not-done leaf must be in the connected set (BO-2400f-2).",
        )

    def test_ac2_all_done_returns_empty_list(self) -> None:
        # covers: BO-2400f-2
        """When the whole connected set is done, resolve_connected_build_set returns [].

        No error, no exception — just an empty list (clean no-op).

        To make this green, resolve_connected_build_set must return [] when every
        leaf in the subtree (and their prerequisites) is work_status: done.
        """
        _write_ac(
            self.ac_root,
            "BO-TST-D00",
            level="L0",
            work_status="done",
            covered_by=["BO-TST-D01", "BO-TST-D02"],
        )
        _write_ac(self.ac_root, "BO-TST-D01", level="L2", work_status="done")
        _write_ac(self.ac_root, "BO-TST-D02", level="L2", work_status="done")

        self._require_impl()

        result = resolve_connected_build_set("BO-TST-D00", ac_root=self.ac_root)

        self.assertEqual(
            result,
            [],
            "resolve_connected_build_set must return [] when all connected leaves "
            "are already done (clean no-op — BO-2400f-2). "
            f"Got: {result!r}",
        )

    def test_ac1_done_dependency_is_not_pulled_in(self) -> None:
        # covers: BO-2400f-1
        """An already-done prerequisite is NOT added to the connected set.

        If a leaf's depends_on points to an AC that is already done, the
        dependency is already met and the done AC must not appear in the result.

        To make this green, resolve_connected_build_set must only add a
        prerequisite to the set when it is work_status != 'done'.
        """
        _write_ac(
            self.ac_root,
            "BO-TST-H00",
            level="L0",
            work_status="todo",
            covered_by=["BO-TST-H01"],
        )
        _write_ac(
            self.ac_root,
            "BO-TST-H01",
            level="L2",
            work_status="todo",
            depends_on=["BO-TST-H02"],
        )
        _write_ac(
            self.ac_root,
            "BO-TST-H02",
            level="L2",
            work_status="done",  # already done — must NOT be pulled in
        )

        self._require_impl()

        result = resolve_connected_build_set("BO-TST-H00", ac_root=self.ac_root)

        self.assertIn("BO-TST-H01", result, "The not-done leaf BO-TST-H01 must be included.")
        self.assertNotIn(
            "BO-TST-H02",
            result,
            "An already-done dependency must NOT be included in the connected set "
            "(BO-2400f-1: restricted to not-done leaves).",
        )

    def test_ac1_nonexistent_ac_id_raises_with_id_in_message(self) -> None:
        # covers: BO-2400f-1
        """resolve_connected_build_set raises a clear exception for an unknown ac_id.

        The exception message must name the missing id.  It must NOT return an
        empty list silently (that would mask typos and wrong ids from the operator).

        To make this green, resolve_connected_build_set must raise an exception
        (e.g. ValueError, KeyError, or LookupError) whose str() contains the
        missing id.
        """
        missing_id = "BO-NONEXISTENT-99999"

        self._require_impl()

        with self.assertRaises(Exception) as ctx:
            resolve_connected_build_set(missing_id, ac_root=self.ac_root)

        self.assertIn(
            missing_id,
            str(ctx.exception),
            f"The exception message must name the missing id '{missing_id}' "
            f"(BO-2400f-1: fails with a clear error naming the missing id). "
            f"Got exception: {ctx.exception!r}",
        )

    def test_ac1_deterministic_on_repeat_calls(self) -> None:
        # covers: BO-2400f-1
        """resolve_connected_build_set returns the identical ordered list on repeat calls.

        Same store state must always produce the same result in the same order —
        the function is deterministic and does NOT modify the store.
        """
        _write_ac(
            self.ac_root,
            "BO-TST-I00",
            level="L0",
            work_status="todo",
            covered_by=["BO-TST-I01", "BO-TST-I02"],
        )
        _write_ac(
            self.ac_root,
            "BO-TST-I01",
            level="L2",
            work_status="todo",
            depends_on=["BO-TST-I03"],
        )
        _write_ac(self.ac_root, "BO-TST-I02", level="L2", work_status="todo")
        _write_ac(self.ac_root, "BO-TST-I03", level="L2", work_status="todo")

        self._require_impl()

        first = resolve_connected_build_set("BO-TST-I00", ac_root=self.ac_root)
        second = resolve_connected_build_set("BO-TST-I00", ac_root=self.ac_root)

        self.assertEqual(
            first,
            second,
            "resolve_connected_build_set must return the identical ordered list on "
            "consecutive calls against an unchanged store (deterministic — BO-2400f-1).",
        )

    def test_ac1_leaf_target_includes_self_and_unmet_deps(self) -> None:
        # covers: BO-2400f-1
        """When the target AC is itself a leaf (L2), it is included plus its unmet deps.

        Calling resolve_connected_build_set on a leaf directly returns that leaf
        and its transitive unmet prerequisites, in dependency order.

        To make this green, resolve_connected_build_set must handle the case where
        ac_id is a leaf (subtree = [ac_id] + its unmet transitive deps).
        """
        _write_ac(
            self.ac_root,
            "BO-TST-J01",
            level="L2",
            work_status="todo",
            depends_on=["BO-TST-J02"],
        )
        _write_ac(self.ac_root, "BO-TST-J02", level="L2", work_status="todo")

        self._require_impl()

        result = resolve_connected_build_set("BO-TST-J01", ac_root=self.ac_root)

        self.assertIn("BO-TST-J01", result, "The leaf itself must be in the result.")
        self.assertIn("BO-TST-J02", result, "The unmet prerequisite must be in the result.")
        self.assertLess(
            result.index("BO-TST-J02"),
            result.index("BO-TST-J01"),
            "The prerequisite (J02) must appear before the dependent (J01) "
            "(dependency order — BO-2400f-1).",
        )

    def test_ac1_transitive_dep_ordering_three_levels(self) -> None:
        # covers: BO-2400f-1
        """Transitive prerequisites (A depends B depends C) are all included in order.

        Three-level chain: BO-TST-K01 depends_on BO-TST-K02 depends_on BO-TST-K03.
        All are not done.  The result must list K03 before K02 before K01.

        To make this green, resolve_connected_build_set must follow the transitive
        closure of depends_on chains (not just direct deps).
        """
        _write_ac(
            self.ac_root,
            "BO-TST-K01",
            level="L2",
            work_status="todo",
            depends_on=["BO-TST-K02"],
        )
        _write_ac(
            self.ac_root,
            "BO-TST-K02",
            level="L2",
            work_status="todo",
            depends_on=["BO-TST-K03"],
        )
        _write_ac(self.ac_root, "BO-TST-K03", level="L2", work_status="todo")

        self._require_impl()

        result = resolve_connected_build_set("BO-TST-K01", ac_root=self.ac_root)

        self.assertIn("BO-TST-K01", result)
        self.assertIn("BO-TST-K02", result)
        self.assertIn("BO-TST-K03", result)

        # K03 → K02 → K01 (deepest prereq first)
        self.assertLess(
            result.index("BO-TST-K03"),
            result.index("BO-TST-K02"),
            "BO-TST-K03 must appear before BO-TST-K02 (transitive prereq — BO-2400f-1).",
        )
        self.assertLess(
            result.index("BO-TST-K02"),
            result.index("BO-TST-K01"),
            "BO-TST-K02 must appear before BO-TST-K01 (BO-2400f-1).",
        )


# ---------------------------------------------------------------------------
# CLI tests — select_connected subcommand
# ---------------------------------------------------------------------------


class TestResolveConnectedBuildSetCli(unittest.TestCase):
    """CLI tests for the select_connected subcommand — BO-2400f-1, BO-2400f-2.

    All tests are RED until python-coder adds the select_connected subcommand
    to fast_lane.py.  The non-zero exit / JSONDecodeError IS the intended red state.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.ac_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_ac1_cli_select_connected_prints_json_list(self) -> None:
        # covers: BO-2400f-1
        """CLI select_connected must print a JSON list to stdout and exit 0.

        python fast_lane.py select_connected --ac <id> --ac-root <dir>
        must print a JSON-encoded list (e.g. ["BO-TST-A01"]) and exit 0.

        DEFECT: select_connected subcommand does not yet exist — the CLI will
        exit non-zero with an argparse error.  JSONDecodeError on the output or
        non-zero exit IS the intended red state.

        To make this green, add a select_connected subcommand that:
        1. Accepts --ac <id> and --ac-root <dir>
        2. Calls resolve_connected_build_set(ac_id, ac_root=...)
        3. Prints json.dumps(result) to stdout
        4. Exits 0 on success
        """
        _write_ac(
            self.ac_root,
            "BO-TST-CLI-A00",
            level="L0",
            work_status="todo",
            covered_by=["BO-TST-CLI-A01"],
        )
        _write_ac(self.ac_root, "BO-TST-CLI-A01", level="L2", work_status="todo")

        returncode, stdout, stderr = _run_cli([
            "select_connected",
            "--ac", "BO-TST-CLI-A00",
            "--ac-root", str(self.ac_root),
        ])

        self.assertEqual(
            returncode,
            0,
            f"select_connected CLI must exit 0 on success. Got {returncode}. "
            f"stdout={stdout!r}\nstderr={stderr!r}\n"
            "DEFECT: select_connected subcommand not yet registered in fast_lane.py.",
        )
        try:
            result = json.loads(stdout.strip())
        except json.JSONDecodeError as exc:
            self.fail(
                f"select_connected CLI must print a JSON list to stdout. "
                f"Not valid JSON: {exc!r}\n"
                f"stdout={stdout!r}\nstderr={stderr!r}\n"
                "DEFECT: resolve_connected_build_set and select_connected CLI "
                "are not yet implemented."
            )
        self.assertIsInstance(result, list, "Output must be a JSON list of AC ids.")
        self.assertIn(
            "BO-TST-CLI-A01",
            result,
            "The not-done subtree leaf must appear in the JSON output.",
        )

    def test_ac1_cli_nonexistent_ac_id_exits_nonzero(self) -> None:
        # covers: BO-2400f-1
        """CLI must exit non-zero and name the missing id for an unknown ac_id.

        python fast_lane.py select_connected --ac BO-NONEXISTENT --ac-root <dir>
        must NOT exit 0 or print an empty JSON list silently.
        The output (stdout or stderr) must name the missing id.

        To make this green, the CLI must call resolve_connected_build_set and
        propagate its exception as a non-zero exit with the id in the error message.
        """
        missing_id = "BO-NONEXISTENT-CLI-001"

        returncode, stdout, stderr = _run_cli([
            "select_connected",
            "--ac", missing_id,
            "--ac-root", str(self.ac_root),
        ])

        self.assertNotEqual(
            returncode,
            0,
            f"select_connected CLI must exit non-zero for an unknown ac_id. "
            f"Got exit code 0.\nstdout={stdout!r}\nstderr={stderr!r}",
        )
        combined = stdout + stderr
        self.assertIn(
            missing_id,
            combined,
            f"The output must name the missing id '{missing_id}'. "
            f"Got combined output: {combined!r}",
        )

    def test_ac2_cli_draft_readiness_leaf_in_output(self) -> None:
        # covers: BO-2400f-2
        """CLI select_connected includes not-done draft-readiness leaves (readiness-agnostic).

        A leaf with readiness: draft and work_status: todo must appear in the
        JSON output list.  This is the key readiness-agnostic guarantee of
        resolve_connected_build_set vs select_batch.

        To make this green, the CLI must forward to resolve_connected_build_set
        which applies NO readiness filter.
        """
        _write_ac(
            self.ac_root,
            "BO-TST-CLI-E00",
            level="L0",
            work_status="todo",
            covered_by=["BO-TST-CLI-E01"],
        )
        _write_ac(
            self.ac_root,
            "BO-TST-CLI-E01",
            level="L2",
            work_status="todo",
            readiness="draft",
        )

        returncode, stdout, stderr = _run_cli([
            "select_connected",
            "--ac", "BO-TST-CLI-E00",
            "--ac-root", str(self.ac_root),
        ])

        self.assertEqual(
            returncode,
            0,
            f"CLI must exit 0 for a draft-readiness leaf. "
            f"Got {returncode}.\nstderr={stderr!r}",
        )
        try:
            result = json.loads(stdout.strip())
        except json.JSONDecodeError as exc:
            self.fail(f"CLI output must be valid JSON: {exc!r}\nstdout={stdout!r}")

        self.assertIn(
            "BO-TST-CLI-E01",
            result,
            "A draft-readiness not-done leaf must be included by select_connected "
            "(readiness-agnostic — BO-2400f-2).",
        )

    def test_ac2_cli_all_done_prints_empty_list_exits_0(self) -> None:
        # covers: BO-2400f-2
        """CLI prints [] and exits 0 (clean no-op) when the whole connected set is done.

        "Reports nothing to build and exits cleanly" (BO-2400f-2).
        Must NOT exit non-zero or raise — just print [] and return 0.

        To make this green, resolve_connected_build_set must return [] for an
        all-done set, and the CLI must print json.dumps([]) and exit 0.
        """
        _write_ac(
            self.ac_root,
            "BO-TST-CLI-D00",
            level="L0",
            work_status="done",
            covered_by=["BO-TST-CLI-D01"],
        )
        _write_ac(self.ac_root, "BO-TST-CLI-D01", level="L2", work_status="done")

        returncode, stdout, stderr = _run_cli([
            "select_connected",
            "--ac", "BO-TST-CLI-D00",
            "--ac-root", str(self.ac_root),
        ])

        self.assertEqual(
            returncode,
            0,
            "CLI must exit 0 (clean no-op) when the whole connected set is done "
            f"(BO-2400f-2). Got exit code {returncode}.\nstderr={stderr!r}",
        )
        try:
            result = json.loads(stdout.strip())
        except json.JSONDecodeError as exc:
            self.fail(f"CLI output must be valid JSON: {exc!r}\nstdout={stdout!r}")

        self.assertEqual(
            result,
            [],
            "CLI must print [] when all connected ACs are already done (BO-2400f-2). "
            f"Got: {result!r}",
        )

    def test_ac1_cli_cross_tree_dep_in_output(self) -> None:
        # covers: BO-2400f-1
        """CLI output includes the cross-tree prerequisite leaf.

        Scenario mirrors the unit test: BO-TST-CLI-B01 depends_on BO-TST-CLI-C01
        from a different sub-tree.  The CLI output for BO-TST-CLI-B00 must include
        both BO-TST-CLI-B01 and BO-TST-CLI-C01.
        """
        _write_ac(
            self.ac_root,
            "BO-TST-CLI-B00",
            level="L0",
            work_status="todo",
            covered_by=["BO-TST-CLI-B01"],
        )
        _write_ac(
            self.ac_root,
            "BO-TST-CLI-B01",
            level="L2",
            work_status="todo",
            depends_on=["BO-TST-CLI-C01"],
        )
        _write_ac(
            self.ac_root,
            "BO-TST-CLI-C00",
            level="L0",
            work_status="todo",
            covered_by=["BO-TST-CLI-C01"],
        )
        _write_ac(self.ac_root, "BO-TST-CLI-C01", level="L2", work_status="todo")

        returncode, stdout, stderr = _run_cli([
            "select_connected",
            "--ac", "BO-TST-CLI-B00",
            "--ac-root", str(self.ac_root),
        ])

        self.assertEqual(returncode, 0, f"CLI must exit 0.\nstderr={stderr!r}")
        try:
            result = json.loads(stdout.strip())
        except json.JSONDecodeError as exc:
            self.fail(f"CLI output must be valid JSON: {exc!r}\nstdout={stdout!r}")

        self.assertIn(
            "BO-TST-CLI-C01",
            result,
            "Cross-tree prerequisite must be in the CLI output list (BO-2400f-1).",
        )
        self.assertIn(
            "BO-TST-CLI-B01",
            result,
            "The target subtree leaf must be in the CLI output list (BO-2400f-1).",
        )
        # Prerequisite must come first
        self.assertLess(
            result.index("BO-TST-CLI-C01"),
            result.index("BO-TST-CLI-B01"),
            "Cross-tree prereq must appear before its dependent in the CLI output "
            "(dependency order — BO-2400f-1).",
        )


if __name__ == "__main__":
    unittest.main()
