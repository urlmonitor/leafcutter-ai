"""
MODULE: unit_tests/ac_store/test_tkt_016_epic_backref_is_relative.py
GOAL: The epic-folder back-reference goal_to_epic.py records in an AC must be a
      repo-relative path, not an absolute one carrying the author's home dir.
COVERS: TKT-016

WHY THIS RUNS THE REAL ASSEMBLY RATHER THAN CALLING THE HELPER

The defect is not in `_replace_implemented_by_entry` -- that function faithfully
writes whatever path it is handed. It is not in `_derive_worktree_from_inbox`
either; called with the exact argument that triggered the bug, it returns the
correct worktree root. The defect is that ONE of the two call sites hands it an
absolute value while its sibling relativises first.

So a test that calls either helper directly passes on the broken code. Only
driving the assembly end to end -- with an ABSOLUTE inbox directory, the form
this repository's shell convention requires -- reaches the asymmetric call site.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GOAL_TO_EPIC = _REPO_ROOT / "scripts" / "goal_to_epic.py"

_GOAL_ID = "ZZBR-900"
_LEAF_IDS = ("ZZBR-900a", "ZZBR-900b")


def _leaf(ac_id: str) -> dict:
    """A minimal leaf AC the generator will accept."""
    return {
        "id": ac_id,
        "title": f"Fixture leaf {ac_id} for the back-reference path test",
        "component": "ticket-creation",
        "components": ["ticket_creation_pipeline"],
        "level": "L2",
        "status": "active",
        "req_status": "draft",
        "work_status": "todo",
        "readiness": "approved",
        "priority": "medium",
        "criteria": (
            "Given a fixture AC\n"
            "When a ticket is generated from it\n"
            "Then the ticket exists\n"
        ),
        "assigned_agent": "python-coder",
        "estimated_complexity": "S",
        "change_target": "pipeline",
        "risk_surface": "internal",
        "origin_agent": "human user",
        "doc_links": [],
        "covered_by": [],
        "implemented_by": [],
        "amended_by": [],
        "superseded_by": None,
    }


class TestEpicBackReferenceIsRepoRelative(unittest.TestCase):
    """TKT-016 — the recorded back-reference must be portable."""

    def test_epic_backref_recorded_relative_with_absolute_inbox_dir(self) -> None:
        # covers: TKT-016
        # angle: real_artifact
        """Drive the REAL assembly with an absolute --inbox-dir and read the
        back-reference the run actually wrote into the AC on disk.

        RED on the current code: goal_to_epic.py's second rewrite call site
        relativises the old path but passes the epic path through absolute, so
        every leaf comes back with a `/home/...` prefix.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = root / "docs" / "acceptance-criteria" / "ticket-creation"
            store.mkdir(parents=True)
            inbox = root / "tickets" / "00_inbox"
            inbox.mkdir(parents=True)

            goal = _leaf(_GOAL_ID)
            goal.update(level="L1", covered_by=list(_LEAF_IDS))
            (store / f"{_GOAL_ID}.yaml").write_text(
                yaml.safe_dump(goal, sort_keys=False), encoding="utf-8"
            )
            for leaf_id in _LEAF_IDS:
                record = _leaf(leaf_id)
                record["depends_on"] = [_GOAL_ID]
                (store / f"{leaf_id}.yaml").write_text(
                    yaml.safe_dump(record, sort_keys=False), encoding="utf-8"
                )

            # Absolute paths on purpose: that is the trigger, and it is the form
            # this repository's own shell convention mandates.
            proc = subprocess.run(  # noqa: S603
                [
                    sys.executable,
                    str(_GOAL_TO_EPIC),
                    "--ac", _GOAL_ID,
                    "--store-root", str(root / "docs" / "acceptance-criteria"),
                    "--inbox-dir", str(inbox),
                    "--approved-only",
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )
            self.assertEqual(
                0,
                proc.returncode,
                f"assembly failed, so the assertion below would be vacuous.\n"
                f"stdout={proc.stdout}\nstderr={proc.stderr}",
            )

            offenders: list[str] = []
            checked = 0
            for leaf_id in _LEAF_IDS:
                data = yaml.safe_load(
                    (store / f"{leaf_id}.yaml").read_text(encoding="utf-8")
                )
                refs = data.get("implemented_by") or []
                self.assertTrue(
                    refs,
                    f"{leaf_id} recorded no back-reference at all, so this test "
                    "cannot tell a relative path from an absolute one. The "
                    "assembly is expected to record one.",
                )
                for ref in refs:
                    checked += 1
                    if Path(str(ref)).is_absolute():
                        offenders.append(f"{leaf_id}: {ref}")

            self.assertEqual(
                0,
                len(offenders),
                "The epic back-reference was recorded as an ABSOLUTE path. It "
                "resolves only on the machine that wrote it, and committing it "
                "puts a developer's home directory into the shared store.\n"
                + "\n".join(offenders),
            )
            self.assertGreater(
                checked, 0, "no back-references were examined — vacuous pass"
            )

    def tearDown(self) -> None:
        """Remove any fixture tickets the assembly wrote outside its temp dir."""
        stray = _REPO_ROOT / "tickets" / "00_inbox"
        if not stray.is_dir():
            return
        for path in stray.glob(f"*{_GOAL_ID}*"):
            path.unlink(missing_ok=True)
        for epic in stray.glob("epics/*ZZBR*"):
            shutil.rmtree(epic, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
