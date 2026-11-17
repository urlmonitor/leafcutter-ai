"""
MODULE: unit_tests/build_orchestration/test_bo_4300f_3_i.py
AC: BO-4300f-3-i -- Running the cut-over again changes nothing further (L3); plus the ticket's
    reachability proof for BO-4300f-3 (the real CLI door, `--preview` then the real run).
TICKET: 12_TICKET-20260928-BO-4300-legacy-cut-over.md

Report contract and fixtures: see test_bo_4300f_3.py (MigrateCase). Real subprocess against the
DEPLOYED maker; no mock of git; no import of the maker module.

DEPENDS ON (not yet built -- expected RED): `migrate-legacy` in templates/scripts/worktree_migrate.py.

DECISION HISTORY
====================================================================
- 2026-10-12 19:00 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/12,
  BO-4300f-3-i]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/12)
====================================================================
"""
from __future__ import annotations

import unittest
from typing import Any

from unit_tests.build_orchestration.test_bo_4300f_3 import MigrateCase, norm, paths_of


def _stable(answer: dict[str, Any]) -> dict[str, Any]:
    """The report minus time-like fields (the AC excludes timestamps from byte-stability)."""
    return {k: v for k, v in answer.items() if "time" not in k.lower() and not k.endswith("_at")}


class TestSecondRun(MigrateCase):
    def state(self) -> dict[str, Any]:
        return {
            "worktrees": sorted(self.registered_paths()),
            "admin": sorted(self.admin_names()),
            "refs": self.refs(),
            "config": self.config_lines(),
            "gc": (self.git_config_get("gc.auto"), self.git_config_get("maintenance.auto")),
            "landing": sorted(p.relative_to(self.landing).as_posix() for p in self.landing.glob("*/*")),
            "marker": self.snap(self.landing / "epic" / "alpha" / ".leafcutter")
            if (self.landing / "epic" / "alpha" / ".leafcutter").is_dir() else {},
            "legacy": {p.name: self.snap(p) for p in (self.project.parent / "worktrees").iterdir()},
        }

    def test_second_cutover_run_changes_nothing(self):
        # covers: BO-4300f-3-i
        # angle: criterion
        """AC-1: after one completed run (which really did retire, bring over and list), a second run
        leaves worktree registrations, folders, refs and config identical."""
        self.make_world()
        first = self.migrate_ok()
        self.assertTrue(first["retired"] and first["brought_over"] and first["needs_decision"],
                        msg=f"first run must have done all three things: {first}")
        before = self.state()
        self.migrate_ok()
        self.assertEqual(self.state(), before)

    def test_second_run_report_says_nothing_left_but_listed_decisions(self):
        # covers: BO-4300f-3-i
        # angle: boundary
        """AC-1: the second report lists no retired or brought_over entries and repeats the same
        needs_decision entries; a third report is identical to the second (excluding timestamps)."""
        self.make_world()
        first = self.migrate_ok()
        second = self.migrate_ok()
        self.assertEqual(second["retired"], [], msg=f"{second}")
        self.assertEqual(second["brought_over"], [], msg=f"{second}")
        self.assertEqual(paths_of(second["needs_decision"]), paths_of(first["needs_decision"]))
        self.assertEqual(len(second["needs_decision"]), 1, msg=f"{second}")
        third = self.migrate_ok()
        self.assertEqual(_stable(third), _stable(second))


class TestReachableThroughTheRealDoor(MigrateCase):
    def test_ticket_12_reachable_from_entry_point(self):
        # covers: BO-4300f-3
        # angle: reachability
        """Invokes `python <install-root>/.leafcutter/scripts/worktree.py migrate-legacy [--preview]
        --repo-root <project>` as a subprocess: preview changes nothing and previews what the real run
        then does; the real run's effect (folders gone, workspace landed) is observed on disk."""
        world = self.make_world()
        admin_before, refs_before = self.admin_names(), self.refs()
        legacy_before = {k: self.snap(world[k]) for k in ("beta", "gamma", "alpha", "hotfix")}

        preview = self.migrate_ok(preview=True)
        self.assertEqual(self.admin_names(), admin_before)
        self.assertEqual(self.refs(), refs_before)
        self.assertEqual({k: self.snap(world[k]) for k in legacy_before}, legacy_before)
        self.assertFalse((self.landing / "epic" / "alpha").exists())

        real = self.migrate_ok()
        for key in ("retired", "brought_over", "needs_decision"):
            self.assertEqual(paths_of(real[key]), paths_of(preview[key]), msg=f"{key}: {preview} vs {real}")
        self.assertFalse(world["beta"].exists())
        self.assertTrue((self.landing / "epic" / "alpha" / ".leafcutter" / "workspace.json").is_file())
        self.assertEqual(norm(real["brought_over"][0]["workspace_path"]), norm(self.landing / "epic" / "alpha"))


if __name__ == "__main__":
    unittest.main()
