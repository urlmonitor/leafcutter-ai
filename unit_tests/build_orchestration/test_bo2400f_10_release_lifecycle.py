"""
MODULE: unit_tests/build_orchestration/test_bo2400f_10_release_lifecycle.py
GOAL: Coverage for the L2 parent AC BO-2400f-10 — "On failure or abort,
      release the claim: in_progress -> todo so work is never stuck". This
      L2 is enforced by its two L3 children:

        - BO-2400f-10-i  (the release actually releases, on every halting
          path — see test_bo2400f_10i_release_real_artifact.py and
          test_bo2400f_10i_release_wiring.py)
        - BO-2400f-10-ii (a release that did not release is read and named
          in the halt — see test_bo2400f_10ii_release_reporting.py)

This file's job is narrower: prove the parent-level, store-visible OUTCOME —
"no AC is left permanently stuck in in_progress" and "the release is a
status-only change landed the same way the claim was" — directly against a
real on-disk AC store, independent of which workflow-layer mechanism (JS
persona, direct invocation, etc.) eventually performs it. It is deliberately
CLI-level (per the underlying-mechanism note below) rather than
harness-driven, so it stays true regardless of how BO-2400f-10-i/-ii's fix
is shaped (the open product question about mainline vs. workspace-only is
carried by those children, not resolved here).
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
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "build_orchestration" / "fast_lane.py"


def _write_ac(ac_root: Path, ac_id: str, work_status: str) -> Path:
    """Write a minimal, valid AC YAML via yaml.safe_dump (fixture-authenticity)."""
    subdir = ac_root / "build-orchestration"
    subdir.mkdir(parents=True, exist_ok=True)
    data = {
        "id": ac_id,
        "title": f"Synthetic parent-lifecycle fixture {ac_id}",
        "component": "build-orchestration",
        "level": "L3",
        "status": "active",
        "work_status": work_status,
        "readiness": "approved",
        "priority": "medium",
        "estimated_complexity": "S",
        "depends_on": [],
        "covered_by": [],
    }
    path = subdir / f"{ac_id}.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _read_ac(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _run_cli(args: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH)] + args,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


class TestParentReleaseLifecycle(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "docs" / "acceptance-criteria"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_failed_run_releases_claim_to_todo(self) -> None:
        # covers: BO-2400f-10
        """A claimed-but-not-done AC, after the release invocation the
        workflow is supposed to have an executor run, reads back todo from
        the real on-disk YAML store."""
        path_a = _write_ac(self.ac_root, "FLT-9100a", "todo")

        rc, out, err = _run_cli(
            ["claim", "--ac-ids", "FLT-9100a", "--ac-root", str(self.ac_root)]
        )
        self.assertEqual(rc, 0, f"claim CLI must exit 0. stderr={err!r}")
        self.assertEqual(_read_ac(path_a)["work_status"], "in_progress")

        rc, out, err = _run_cli(
            ["release", "--ac-ids", "FLT-9100a", "--ac-root", str(self.ac_root)]
        )
        self.assertEqual(rc, 0, f"release CLI must exit 0. stderr={err!r}")
        payload = json.loads(out)
        self.assertIn("FLT-9100a", payload.get("released", []))
        self.assertEqual(
            _read_ac(path_a)["work_status"],
            "todo",
            "the on-disk record must read work_status: todo after release — "
            "no AC may be left permanently stuck in in_progress.",
        )

    def test_release_lands_as_status_only_change_on_mainline(self) -> None:
        # covers: BO-2400f-10
        """The release is landed 'the same way the claim was' — a
        status-only change touching only work_status, with every other
        field byte-identical before and after."""
        path_a = _write_ac(self.ac_root, "FLT-9100b", "in_progress")
        before = _read_ac(path_a)

        rc, _out, err = _run_cli(
            ["release", "--ac-ids", "FLT-9100b", "--ac-root", str(self.ac_root)]
        )
        self.assertEqual(rc, 0, f"release CLI must exit 0. stderr={err!r}")
        after = _read_ac(path_a)

        changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
        self.assertEqual(changed, {"work_status"})

    def test_release_targets_only_own_claim_not_done_acs(self) -> None:
        # covers: BO-2400f-10
        """Release targets only THIS run's own claimed-but-not-done ACs,
        leaving an already-done AC and an AC claimed by another run
        untouched."""
        own_claim = _write_ac(self.ac_root, "FLT-9100c", "in_progress")
        already_done = _write_ac(self.ac_root, "FLT-9100d", "done")
        other_runs_claim = _write_ac(self.ac_root, "FLT-9100e", "in_progress")

        rc, _out, err = _run_cli(
            ["release", "--ac-ids", "FLT-9100c", "--ac-root", str(self.ac_root)]
        )
        self.assertEqual(rc, 0, f"release CLI must exit 0. stderr={err!r}")

        self.assertEqual(_read_ac(own_claim)["work_status"], "todo")
        self.assertEqual(
            _read_ac(already_done)["work_status"],
            "done",
            "a done AC must never be regressed by a release call that did "
            "not name it",
        )
        self.assertEqual(
            _read_ac(other_runs_claim)["work_status"],
            "in_progress",
            "an AC claimed by ANOTHER run (not in --ac-ids) must be left "
            "untouched",
        )


if __name__ == "__main__":
    unittest.main()
