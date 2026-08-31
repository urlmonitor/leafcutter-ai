"""
MODULE: unit_tests/build_orchestration/test_bo2400f_10i_release_real_artifact.py
GOAL: Real-artifact behavioral tests for BO-2400f-10-i — prove that
      ``scripts/build_orchestration/fast_lane.py release`` (the command a
      fast-lane run's release step is supposed to have an executor actually
      run) does, when genuinely invoked as a subprocess against a real
      on-disk AC store, flip every claimed-and-not-done record back to
      ``work_status: todo`` as a status-only change, and leaves records
      claimed by another run untouched.

These tests satisfy the Real-Artifact Behavioral Test Mandate (BP-1100f-2):
they run the real CLI as a subprocess (never mock the write call), write to a
real ``tempfile.TemporaryDirectory()``, and read the artifact (the AC YAML)
back off disk afterwards.

=== Why these are expected to be GREEN, not RED, at this baseline ===

BO-2400f-10-i's defect (KI-BO-020) is that NOTHING in production ever
actually invokes this command — every one of the nine release dispatch sites
in fast-lane-ship.js asks a status-checker persona to run it, and
status-checker's own registry entry (config/agent_registry.json,
``permits_shell: false``) means it structurally cannot. The underlying
``fast_lane.py release`` subcommand and ``release_claim()`` function are
already correct in isolation — this file locks in that baseline contract
(the "if only it were actually invoked" half of the fix) as the fixture
the wiring-level tests in test_bo2400f_10i_release_wiring.py build on. Those
sibling tests, plus test_bo2400f_10ii's payload-composition tests, are where
the true RED signal for this defect lives — the persona-mismatch and the
discarded-outcome path are workflow-layer (JavaScript) bugs invisible to a
pure CLI invocation.

Fixture-Authenticity Rule (2h.2): every AC record here is produced with
``yaml.safe_dump`` and re-parsed with ``yaml.safe_load`` -- never a
hand-typed YAML string literal.
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
    """Write a minimal, valid AC YAML via yaml.safe_dump (never a hand-typed literal)."""
    subdir = ac_root / "build-orchestration"
    subdir.mkdir(parents=True, exist_ok=True)
    data = {
        "id": ac_id,
        "title": f"Synthetic release-lifecycle fixture {ac_id}",
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


class TestReleaseRealArtifact(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ac_root = Path(self._tmp.name) / "docs" / "acceptance-criteria"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_release_returns_claimed_not_done_records_to_todo_on_disk(self) -> None:
        # covers: BO-2400f-10-i
        """A real subprocess `release` call flips an in_progress, not-done
        record back to todo, read back from the actual on-disk YAML."""
        path_a = _write_ac(self.ac_root, "FLT-9101a", "in_progress")
        rc, out, err = _run_cli(
            [
                "release",
                "--ac-ids",
                "FLT-9101a",
                "--ac-root",
                str(self.ac_root),
            ]
        )
        self.assertEqual(rc, 0, f"release CLI must exit 0. stderr={err!r}")
        payload = json.loads(out)
        self.assertIn("FLT-9101a", payload.get("released", []))

        on_disk = _read_ac(path_a)
        self.assertEqual(
            on_disk["work_status"],
            "todo",
            "the ON-DISK record (not the command's own stdout) must read "
            "work_status: todo after release.",
        )

    def test_release_leaves_records_claimed_by_another_run_untouched(self) -> None:
        # covers: BO-2400f-10-i
        """A record left in_progress but NOT in this run's claimed-id list
        is untouched by that run's release call."""
        path_mine = _write_ac(self.ac_root, "FLT-9101b", "in_progress")
        path_other = _write_ac(self.ac_root, "FLT-9101c", "in_progress")

        rc, out, err = _run_cli(
            [
                "release",
                "--ac-ids",
                "FLT-9101b",
                "--ac-root",
                str(self.ac_root),
            ]
        )
        self.assertEqual(rc, 0, f"release CLI must exit 0. stderr={err!r}")

        self.assertEqual(_read_ac(path_mine)["work_status"], "todo")
        self.assertEqual(
            _read_ac(path_other)["work_status"],
            "in_progress",
            "a record claimed by a DIFFERENT run (not in --ac-ids) must "
            "stay exactly as it was.",
        )

    def test_release_is_a_status_only_change_to_each_record(self) -> None:
        # covers: BO-2400f-10-i
        """Every non-work_status key of a touched record is byte-identical
        before and after release — this is a status-only change."""
        path_a = _write_ac(self.ac_root, "FLT-9101d", "in_progress")
        before = _read_ac(path_a)

        rc, _out, err = _run_cli(
            [
                "release",
                "--ac-ids",
                "FLT-9101d",
                "--ac-root",
                str(self.ac_root),
            ]
        )
        self.assertEqual(rc, 0, f"release CLI must exit 0. stderr={err!r}")
        after = _read_ac(path_a)

        changed_keys = {
            k
            for k in set(before) | set(after)
            if before.get(k) != after.get(k)
        }
        self.assertEqual(
            changed_keys,
            {"work_status"},
            f"release must change ONLY work_status; also changed: {changed_keys}",
        )

    def test_a_run_that_claimed_and_finished_leaves_no_record_in_progress(self) -> None:
        # covers: BO-2400f-10
        """THE UNDERLYING-MECHANISM LOAD-BEARING TEST for the parent AC: a
        real claim followed by a real release (simulating the sequence a
        working executor would perform on a halting run) leaves NO claimed
        record stuck at in_progress. This proves the underlying claim/release
        primitives are sound; it does NOT prove production ever calls
        release for real (see test_bo2400f_10i_release_wiring.py for that
        RED signal — the persona-mismatch bug this build set exists to fix)."""
        path_a = _write_ac(self.ac_root, "FLT-9101e", "todo")
        path_b = _write_ac(self.ac_root, "FLT-9101f", "todo")

        rc, out, err = _run_cli(
            [
                "claim",
                "--ac-ids",
                "FLT-9101e,FLT-9101f",
                "--ac-root",
                str(self.ac_root),
            ]
        )
        self.assertEqual(rc, 0, f"claim CLI must exit 0. stderr={err!r}")
        claim_payload = json.loads(out)
        claimed_csv = ",".join(claim_payload["claimed"])
        self.assertEqual(_read_ac(path_a)["work_status"], "in_progress")
        self.assertEqual(_read_ac(path_b)["work_status"], "in_progress")

        # Simulate the run halting before either AC reaches done, and an
        # executor actually running the release invocation the workflow
        # composes (this is the invocation string production is supposed to
        # get run, but currently never does — KI-BO-020).
        rc, _out, err = _run_cli(
            ["release", "--ac-ids", claimed_csv, "--ac-root", str(self.ac_root)]
        )
        self.assertEqual(rc, 0, f"release CLI must exit 0. stderr={err!r}")

        self.assertEqual(_read_ac(path_a)["work_status"], "todo")
        self.assertEqual(_read_ac(path_b)["work_status"], "todo")


if __name__ == "__main__":
    unittest.main()
