"""
MODULE: unit_tests/build_orchestration/test_build_dataflow.py
GOAL: Behavioral tests for BO-2400f-6 — export the build backlog as a JSON
      dataflow of the acceptance criteria that still need building.

=== Interface contract these tests define ===

Location: scripts/build_orchestration/build_dataflow.py

    build_dataflow(*, ac_root: Path, ac: str | None = None) -> dict

        Return the build-backlog dataflow document.

        Store scope (ac is None): every leaf (L2/L3) AC with work_status != done.
        Connected scope (ac is an id): the connected build set of that id
            (subtree + unmet-deps closure), readiness-agnostic.

        Shape:
            {
              "schema_version": int,
              "scope": {"mode": "store"|"connected", "ac": str|None, "ac_root": str},
              "totals": {"todo_leaves": int, "ready": int, "blocked": int},
              "build_order": [ac_id, ...],   # dependency order, deps first
              "nodes": {
                 ac_id: {
                    "id", "title", "component", "level", "work_status",
                    "readiness", "test_required", "parent", "depends_on",
                    "unmet_deps", "ready", "path"
                 }, ...
              },
            }

CLI:

    python build_dataflow.py --ac-root <dir> [--ac <id>] [--out <file>]

    Writes the JSON document to --out (default docs/build-dataflow.json),
    prints the out path, exits 0. A non-existent --ac exits non-zero and names
    the missing id.

=== Fixture-authenticity mandate ===
All AC YAML fixtures are written with yaml.safe_dump, never hand-typed literals.

=== Red baseline ===
RED until python-coder implements build_dataflow.py. ImportError is the
intended red state for the unit tests; JSONDecodeError / non-zero exit is the
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

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_MODULE_DIR = _REPO_ROOT / "scripts" / "build_orchestration"
if str(_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULE_DIR))

_SCRIPT_PATH = _MODULE_DIR / "build_dataflow.py"

_FUNC_IMPORT_OK = False
_FUNC_IMPORT_ERR = ""
build_dataflow = None  # type: ignore[assignment]

try:
    from build_dataflow import build_dataflow  # noqa: E402
    _FUNC_IMPORT_OK = True
except (ImportError, AttributeError) as _exc:
    _FUNC_IMPORT_ERR = str(_exc)


def _write_ac(
    ac_root: Path,
    ac_id: str,
    *,
    level: str,
    work_status: str,
    readiness: str = "approved",
    depends_on: list | None = None,
    covered_by: list | None = None,
    test_required: bool | None = None,
) -> Path:
    """Write a minimal AC YAML file via yaml.safe_dump (fixture-authenticity mandate)."""
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
    if test_required is not None:
        data["test_required"] = test_required
    path = subdir / f"{ac_id}.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _run_cli(args: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH)] + args,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


class TestBuildDataflowStore(unittest.TestCase):
    """Store-scope dataflow export — BO-2400f-6."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.ac_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _require_impl(self) -> None:
        if not _FUNC_IMPORT_OK:
            self.fail(
                "build_dataflow not importable — ImportError is the intended red "
                f"state; python-coder must implement it. Error: {_FUNC_IMPORT_ERR}"
            )

    def test_store_lists_todo_leaves_excludes_done(self) -> None:
        # covers: BO-2400f-6
        """Store scope lists not-done leaves in nodes and excludes done leaves."""
        _write_ac(self.ac_root, "BO-DF-A00", level="L0", work_status="todo",
                  covered_by=["BO-DF-A01", "BO-DF-A02"])
        _write_ac(self.ac_root, "BO-DF-A01", level="L2", work_status="todo")
        _write_ac(self.ac_root, "BO-DF-A02", level="L2", work_status="done")

        self._require_impl()
        doc = build_dataflow(ac_root=self.ac_root)

        self.assertIn("BO-DF-A01", doc["nodes"], "Not-done leaf must be a node.")
        self.assertNotIn("BO-DF-A02", doc["nodes"], "Done leaf must be excluded.")
        self.assertNotIn("BO-DF-A00", doc["nodes"], "Composite (L0) must not be a leaf node.")
        self.assertEqual(doc["scope"]["mode"], "store")

    def test_node_carries_required_fields(self) -> None:
        # covers: BO-2400f-6
        """Each node carries title, depends_on, unmet_deps, ready, test_required, parent."""
        _write_ac(self.ac_root, "BO-DF-B00", level="L0", work_status="todo",
                  covered_by=["BO-DF-B01"])
        _write_ac(self.ac_root, "BO-DF-B01", level="L2", work_status="todo",
                  depends_on=["BO-DF-B02"], test_required=False)
        _write_ac(self.ac_root, "BO-DF-B02", level="L2", work_status="todo")

        self._require_impl()
        doc = build_dataflow(ac_root=self.ac_root)

        node = doc["nodes"]["BO-DF-B01"]
        for field in ("id", "title", "level", "work_status", "readiness",
                      "test_required", "parent", "depends_on", "unmet_deps", "ready"):
            self.assertIn(field, node, f"Node must carry '{field}'.")
        self.assertEqual(node["test_required"], False)
        self.assertEqual(node["parent"], "BO-DF-B00", "parent derived from covered_by.")
        self.assertIn("BO-DF-B02", node["unmet_deps"], "B02 (todo) is an unmet dep.")
        self.assertFalse(node["ready"], "B01 has an unmet dep so it is not ready.")

    def test_build_order_is_dependency_ordered(self) -> None:
        # covers: BO-2400f-6
        """build_order lists a prerequisite before its dependent."""
        _write_ac(self.ac_root, "BO-DF-C01", level="L2", work_status="todo",
                  depends_on=["BO-DF-C02"])
        _write_ac(self.ac_root, "BO-DF-C02", level="L2", work_status="todo")

        self._require_impl()
        doc = build_dataflow(ac_root=self.ac_root)

        order = doc["build_order"]
        self.assertIn("BO-DF-C01", order)
        self.assertIn("BO-DF-C02", order)
        self.assertLess(order.index("BO-DF-C02"), order.index("BO-DF-C01"),
                        "Prerequisite C02 must appear before dependent C01.")

    def test_totals_count_ready_and_blocked(self) -> None:
        # covers: BO-2400f-6
        """totals reports todo_leaves, ready, and blocked counts consistently."""
        _write_ac(self.ac_root, "BO-DF-D01", level="L2", work_status="todo")  # ready
        _write_ac(self.ac_root, "BO-DF-D02", level="L2", work_status="todo",
                  depends_on=["BO-DF-D03"])  # blocked (dep todo)
        _write_ac(self.ac_root, "BO-DF-D03", level="L2", work_status="todo")  # ready

        self._require_impl()
        doc = build_dataflow(ac_root=self.ac_root)

        totals = doc["totals"]
        self.assertEqual(totals["todo_leaves"], 3)
        self.assertEqual(totals["ready"] + totals["blocked"], totals["todo_leaves"])
        self.assertEqual(totals["blocked"], 1, "Only D02 is blocked.")

    def test_deterministic_identical_json(self) -> None:
        # covers: BO-2400f-6
        """Same store state yields byte-identical serialised JSON (clean-diff artifact)."""
        _write_ac(self.ac_root, "BO-DF-E01", level="L2", work_status="todo",
                  depends_on=["BO-DF-E02"])
        _write_ac(self.ac_root, "BO-DF-E02", level="L2", work_status="todo")
        _write_ac(self.ac_root, "BO-DF-E03", level="L2", work_status="todo")

        self._require_impl()
        first = build_dataflow(ac_root=self.ac_root)
        second = build_dataflow(ac_root=self.ac_root)
        self.assertEqual(
            json.dumps(first, sort_keys=True, indent=2),
            json.dumps(second, sort_keys=True, indent=2),
            "Dataflow export must be deterministic for an unchanged store.",
        )


class TestBuildDataflowConnected(unittest.TestCase):
    """Connected-scope dataflow export — BO-2400f-6."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.ac_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _require_impl(self) -> None:
        if not _FUNC_IMPORT_OK:
            self.fail(f"build_dataflow not importable. Error: {_FUNC_IMPORT_ERR}")

    def test_connected_scope_restricts_to_connected_set(self) -> None:
        # covers: BO-2400f-6
        """Connected scope restricts nodes to the target AC's connected set."""
        # Tree A (the target) and an unrelated tree Z that must NOT appear.
        _write_ac(self.ac_root, "BO-DF-F00", level="L0", work_status="todo",
                  covered_by=["BO-DF-F01"])
        _write_ac(self.ac_root, "BO-DF-F01", level="L2", work_status="todo")
        _write_ac(self.ac_root, "BO-DF-Z00", level="L0", work_status="todo",
                  covered_by=["BO-DF-Z01"])
        _write_ac(self.ac_root, "BO-DF-Z01", level="L2", work_status="todo")

        self._require_impl()
        doc = build_dataflow(ac_root=self.ac_root, ac="BO-DF-F00")

        self.assertIn("BO-DF-F01", doc["nodes"])
        self.assertNotIn("BO-DF-Z01", doc["nodes"],
                         "Unrelated tree must be excluded in connected scope.")
        self.assertEqual(doc["scope"]["mode"], "connected")
        self.assertEqual(doc["scope"]["ac"], "BO-DF-F00")

    def test_connected_nonexistent_id_raises_with_id(self) -> None:
        # covers: BO-2400f-6
        """A non-existent id in connected scope raises naming the id."""
        self._require_impl()
        with self.assertRaises(Exception) as ctx:
            build_dataflow(ac_root=self.ac_root, ac="BO-DF-NOPE-999")
        self.assertIn("BO-DF-NOPE-999", str(ctx.exception))


class TestBuildDataflowCli(unittest.TestCase):
    """CLI surface — BO-2400f-6."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.ac_root.mkdir(parents=True, exist_ok=True)
        self.out = Path(self._tmp.name) / "build-dataflow.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_cli_writes_json_file_and_exits_0(self) -> None:
        # covers: BO-2400f-6
        """CLI writes the JSON artifact to --out and exits 0."""
        _write_ac(self.ac_root, "BO-DF-G01", level="L2", work_status="todo")

        rc, out, err = _run_cli([
            "--ac-root", str(self.ac_root),
            "--out", str(self.out),
        ])
        self.assertEqual(rc, 0, f"CLI must exit 0. stdout={out!r} stderr={err!r}")
        self.assertTrue(self.out.exists(), "CLI must write the --out file.")
        doc = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertIn("BO-DF-G01", doc["nodes"])

    def test_cli_nonexistent_ac_exits_nonzero(self) -> None:
        # covers: BO-2400f-6
        """CLI --ac with a missing id exits non-zero and names the id."""
        rc, out, err = _run_cli([
            "--ac-root", str(self.ac_root),
            "--ac", "BO-DF-MISSING-42",
            "--out", str(self.out),
        ])
        self.assertNotEqual(rc, 0, "CLI must exit non-zero for a missing --ac id.")
        self.assertIn("BO-DF-MISSING-42", out + err)


if __name__ == "__main__":
    unittest.main()
