"""
MODULE: unit_tests/build_orchestration/test_bo_2400c_6_ii.py
GOAL: Prove the standalone (no-caller-supplied-index) command surface that
      walks the AC tree stays reachable and correct once traverse_ac_tree()
      grows the optional id_index parameter (BO-2400c-6, BO-2400c-6-ii).
COVERS: BO-2400c-6-ii

=== Why goal_to_epic.py --ac --dry-run is "the standalone command surface" ===

scripts/goal_to_epic.py's run() (the --ac mode of its CLI) calls
``traverse_ac_tree(ac_id, ac_store_root)`` directly (goal_to_epic.py ~2228)
with NO id_index — it is exactly the "standalone command-line ... caller"
BO-2400c-6-ii names as one of the two callers that must keep working when it
supplies nothing. --dry-run makes this a cheap, read-only, real subprocess
invocation: it prints the plan and returns without writing any ticket or
epic files.

=== Verified ground truth (test-writer pre-flight, 2026-08-25) ===

Ran live against the pre-fix implementation:

    python goal_to_epic.py --ac BO-TST-GTE-T00 \\
        --store-root <fixture> --inbox-dir <fixture> --dry-run

    exit code: 0
    stdout:
        Dry-run: would create EPIC-SyntheticBoTstGteT00 with 1 ticket(s):
          BO-TST-GTE-T01
        stderr: (empty)

=== Why this test PASSES immediately ===

DELIBERATE REGRESSION GUARD, not a red-today test. The no-index path is
exactly today's existing behaviour — BO-2400c-6-ii requires it be preserved,
not changed. It is the "reusing a caller-supplied record set is an option
... never an obligation" half of the criterion. This test exists to catch a
future change that accidentally makes the new ``id_index`` parameter
effectively required (which would break this real subprocess call while
every in-repo direct caller might still pass, per the AC's own stated
failure mode: "a change that makes the new parameter effectively required
... the in-repo suite would not catch [it] once every in-repo caller
supplies one, while the standalone command surface breaks").
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GOAL_TO_EPIC_SCRIPT = _REPO_ROOT / "scripts" / "goal_to_epic.py"


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
    """Write a minimal AC YAML file using yaml.safe_dump (fixture-authenticity mandate)."""
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
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


class TestStandaloneCommandSurfaceStillResolves(unittest.TestCase):
    """BO-2400c-6-ii: goal_to_epic.py --ac --dry-run (a real caller holding no
    record index of its own) must still resolve the tree correctly.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "acs"
        self.inbox_dir = Path(self._tmp.name) / "inbox"
        self.ac_root.mkdir(parents=True, exist_ok=True)
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        _write_ac(
            self.ac_root,
            "BO-TST-GTE-T00",
            level="L0",
            work_status="todo",
            covered_by=["BO-TST-GTE-T01"],
        )
        _write_ac(self.ac_root, "BO-TST-GTE-T01", level="L2", work_status="todo")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_standalone_command_surface_still_resolves(self) -> None:
        # covers: BO-2400c-6-ii
        """Run as a real subprocess with no caller-supplied index in play, the
        command surface that walks the tree returns its expected answer —
        proving the optional path is reachable from outside the resolver.
        """
        result = subprocess.run(
            [
                sys.executable,
                str(_GOAL_TO_EPIC_SCRIPT),
                "--ac", "BO-TST-GTE-T00",
                "--store-root", str(self.ac_root),
                "--inbox-dir", str(self.inbox_dir),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        self.assertEqual(
            result.returncode,
            0,
            "goal_to_epic.py --ac --dry-run (the standalone, no-index tree-walk "
            f"caller) must exit 0 (BO-2400c-6-ii). Got {result.returncode}.\n"
            f"stdout={result.stdout!r}\nstderr={result.stderr!r}",
        )
        self.assertIn(
            "BO-TST-GTE-T01",
            result.stdout,
            "The standalone command surface must still resolve the correct leaf id "
            f"with no id_index supplied (BO-2400c-6-ii). stdout={result.stdout!r}",
        )


if __name__ == "__main__":
    unittest.main()
