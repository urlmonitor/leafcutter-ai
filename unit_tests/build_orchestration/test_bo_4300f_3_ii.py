"""
MODULE: unit_tests/build_orchestration/test_bo_4300f_3_ii.py
AC: BO-4300f-3-ii -- Until the cut-over completes, automatic housekeeping cannot prune the shared
    history (L3).
TICKET: 12_TICKET-20260928-BO-4300-legacy-cut-over.md

Real git auto-gc is triggered for real: the test's isolated global config lowers `gc.auto` to 5 with
`gc.autoDetach=false`, and a batch of loose objects that all land in `objects/17` (found by hashing
in memory) is written so git's estimate (> 1 object in objects/17) is exceeded. The CONTROL project
(no cut-over) proves the trigger genuinely packs; the cut-over project (repo-local `gc.auto 0`,
`maintenance.auto false`, which outrank the global config) must stay byte-for-byte unpacked.

Report contract and fixtures: see test_bo_4300f_3.py (MigrateCase).

DEPENDS ON (not yet built -- expected RED): `migrate-legacy` in templates/scripts/worktree_migrate.py.

DECISION HISTORY
====================================================================
- 2026-10-12 19:00 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/12,
  BO-4300f-3-ii]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/12)
====================================================================
"""
from __future__ import annotations

import hashlib
import unittest
from pathlib import Path

from unit_tests.build_orchestration._workspace_maker_fixtures import legacy_worktree, make_project
from unit_tests.build_orchestration.test_bo_4300f_3 import MigrateCase

LOOSE_IN_DIR_17 = 20  # git's gc --auto sees > ceil(5/256)=1 object in objects/17
EXTRA_COMMITS = 3


class HousekeepingCase(MigrateCase):
    def setUp(self) -> None:
        super().setUp()
        with open(self.home / ".gitconfig", "a", encoding="utf-8", newline="\n") as fh:
            fh.write("[gc]\n\tauto = 5\n\tautoDetach = false\n[maintenance]\n\tautoDetach = false\n")

    def object_state(self, repo: Path) -> tuple[int, list[str]]:
        """(loose-object count, sorted pack files)."""
        counts = dict(line.split(": ", 1) for line in self.git(["count-objects", "-v"], repo).splitlines())
        packs = sorted(p.name for p in (repo / ".git" / "objects" / "pack").glob("*.pack"))
        return int(counts["count"]), packs

    def seed_loose_objects(self, repo: Path) -> None:
        """Write LOOSE_IN_DIR_17 distinct blobs whose ids start with '17'."""
        found, i = [], 0
        scratch = repo.parent / f"{repo.name}-blobs"
        scratch.mkdir(exist_ok=True)
        while len(found) < LOOSE_IN_DIR_17:
            data = f"housekeeping blob {i}\n".encode()
            i += 1
            if hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest().startswith("17"):
                path = scratch / f"b{len(found)}.txt"
                path.write_bytes(data)
                found.append(path)
        self.git(["hash-object", "-w", *[str(p) for p in found]], repo)

    def commit_past_threshold(self, repo: Path) -> None:
        for n in range(EXTRA_COMMITS):
            self.git(["commit", "-q", "--allow-empty", "-m", f"housekeeping probe {n}"], repo)


class TestHousekeeping(HousekeepingCase):
    def test_automatic_housekeeping_does_not_run_while_legacy_workspaces_remain(self):
        # covers: BO-4300f-3-ii
        # angle: failure
        """AC-2: after the cut-over (one legacy workspace left for a decision), commits that would
        trigger `gc --auto` leave the pack set unchanged and the loose count at exactly before + the
        new commits. The control project (no cut-over, same global threshold) really does pack."""
        control = make_project(self.tmp / "control")["project"]
        self.seed_loose_objects(control)
        loose_c, packs_c = self.object_state(control)
        self.commit_past_threshold(control)
        loose_c_after, packs_c_after = self.object_state(control)
        self.assertNotEqual(packs_c_after, packs_c, msg="control: auto-gc never triggered; proof is vacuous")
        self.assertLess(loose_c_after, loose_c)

        hotfix = legacy_worktree(self.project, "hotfix-login", unsent=True)
        self.assertTrue(hotfix.exists())
        answer = self.migrate_ok()
        self.assertEqual(len(answer["needs_decision"]), 1, msg=f"{answer}")
        self.assertEqual(self.git_config_get("gc.auto"), "0")
        self.assertEqual(self.git_config_get("maintenance.auto"), "false")

        self.seed_loose_objects(self.project)
        loose, packs = self.object_state(self.project)
        self.commit_past_threshold(self.project)
        loose_after, packs_after = self.object_state(self.project)
        self.assertEqual(packs_after, packs)
        self.assertEqual(loose_after, loose + EXTRA_COMMITS)

    def test_every_commit_referenced_by_legacy_workspaces_stays_readable(self):
        # covers: BO-4300f-3-ii
        # angle: criterion
        """AC-2: every commit a legacy workspace refers to (heads of the worktrees, their branches) is
        still readable by `git cat-file -e` in the main checkout after the cut-over and the
        threshold-crossing commits, for the workspace left for a decision."""
        legacy_worktree(self.project, "EPIC-Beta")
        hotfix = legacy_worktree(self.project, "hotfix-login", unsent=True)
        referenced = [self.git(["rev-parse", "HEAD"], hotfix), self.git(["rev-parse", "HEAD~1"], hotfix)]
        self.migrate_ok()
        self.seed_loose_objects(self.project)
        self.commit_past_threshold(self.project)
        self.assertTrue(hotfix.exists())
        for sha in referenced:
            self.git(["cat-file", "-e", sha + "^{commit}"], self.project)

    def test_previous_housekeeping_settings_restored_after_last_legacy_retired(self):
        # covers: BO-4300f-3-ii
        # angle: boundary
        """AC-2: previous values (gc.auto 1234, maintenance.auto true) are held at 0/false while a legacy
        workspace remains, and put back by the run that retires the last one."""
        self.git(["config", "--local", "gc.auto", "1234"])
        self.git(["config", "--local", "maintenance.auto", "true"])
        hotfix = legacy_worktree(self.project, "hotfix-login", unsent=True)
        first = self.migrate_ok()
        self.assertEqual(len(first["needs_decision"]), 1, msg=f"{first}")
        self.assertEqual(self.git_config_get("gc.auto"), "0")
        self.assertEqual(self.git_config_get("maintenance.auto"), "false")

        self.git(["push", "-q", "origin", "hotfix-login"], hotfix)  # the work is now sent
        second = self.migrate_ok()
        self.assertEqual(len(second["retired"]), 1, msg=f"{second}")
        self.assertFalse(hotfix.exists())
        self.assertEqual(self.git_config_get("gc.auto"), "1234")
        self.assertEqual(self.git_config_get("maintenance.auto"), "true")

    def test_settings_that_were_unset_are_unset_again_after_last_legacy_retired(self):
        # covers: BO-4300f-3-ii
        # angle: boundary
        """AC-2: when the project had no local gc.auto / maintenance.auto at all, they are absent
        again (not left at 0/false) once the last legacy workspace is gone."""
        self.assertIsNone(self.git_config_get("gc.auto"))
        hotfix = legacy_worktree(self.project, "hotfix-login", unsent=True)
        self.migrate_ok()
        self.assertEqual(self.git_config_get("gc.auto"), "0")
        self.git(["push", "-q", "origin", "hotfix-login"], hotfix)
        self.migrate_ok()
        self.assertIsNone(self.git_config_get("gc.auto"))
        self.assertIsNone(self.git_config_get("maintenance.auto"))


if __name__ == "__main__":
    unittest.main()
