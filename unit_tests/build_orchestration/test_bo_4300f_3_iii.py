"""
MODULE: unit_tests/build_orchestration/test_bo_4300f_3_iii.py
AC: BO-4300f-3-iii (A9) -- work the cut-over cannot carry over exactly keeps the old workspace for a decision.
TICKET: tickets/00_inbox/epics/EPIC-WorkspaceMakerHardening/
    08_TICKET-20261022-cut-over-canonical-deferred-readiness-lossless.md

Four old-style workspaces (all made by the one test-side creator `legacy_worktree`): "m" in the middle of a
merge with an unresolved conflict, "s" whose line has a stashed change (nothing else unsent), "i" holding a
staged, uncommitted change, "l" locked by its user with the reason "on USB drive" (nothing else unsent). The
preview and then the run must keep m, s and l (reason each, all different), keep or exactly carry i (staged
change still staged), and change no folder, registration, stash entry or branch of the kept ones.

REASON TEXT ASSUMED (python-coder: raise a mismatch rather than editing a test): each kept entry's `reason`
names its cause in plain words -- "merge" for m, "stash" for s, "lock" for l. The AC fixes no wording; these
three words are the plain description of the three causes.

Real subprocess against the DEPLOYED maker; no mock of git; no raw linked-checkout command spelled here.

DECISION HISTORY
====================================================================
- 2026-10-22 [test-writer/EPIC-WorkspaceMakerHardening/08, BO-4300f-3-iii]: Created the red baseline.
====================================================================
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from unit_tests.build_orchestration._workspace_maker_fixtures import (  # fixtures first: avoids the builders cycle
    legacy_worktree,
    start_merge,
)
from unit_tests.build_orchestration.test_bo_4300f_3 import MigrateCase, norm, paths_of

_KEPT_WORDS = {"m": "merge", "s": "stash", "l": "lock"}


def _write(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


class TestKeptForDecision(MigrateCase):
    def run_git(self, args: list[str], cwd: Path) -> Any:
        return subprocess.run(["git", *args], cwd=str(cwd), env=self.env(), capture_output=True, text=True)

    def commit(self, root: Path, name: str, text: str, message: str) -> None:
        _write(root / name, text)
        self.git(["add", "-A"], root)
        self.git(["commit", "-q", "-m", message], root)

    def make_four(self) -> dict[str, Path]:
        """Build m, s, i and l (each on its own feature/<letter> line)."""
        world = {k: legacy_worktree(self.project, f"feature/{k}") for k in "msil"}
        self.make_conflicted_merge(world["m"])
        _write(world["s"] / "README.md", "stashed change\n")
        self.git(["stash", "push", "-q", "-m", "stashed on feature/s"], world["s"])
        _write(world["i"] / "STAGED.txt", "staged, not committed\n")
        self.git(["add", "STAGED.txt"], world["i"])
        _write(self.project / ".git" / "worktrees" / "l" / "locked", "on USB drive")
        return world

    def make_conflicted_merge(self, root: Path) -> None:
        self.git(["checkout", "-q", "-b", "theirs-m", "main"], root)
        self.commit(root, "README.md", "their side\n", "their side")
        self.git(["checkout", "-q", "feature/m"], root)
        self.commit(root, "README.md", "our side\n", "our side")
        start_merge(root, "feature/m", "theirs-m", lambda args, cwd: self.run_git(args, cwd))
        self.assertIn("README.md", self.git(["diff", "--name-only", "--diff-filter=U"], root))

    def state(self, world: dict[str, Path]) -> dict[str, Any]:
        """Everything that must stay put for a kept workspace: folder bytes, registration files, branches, stashes."""
        for folder in world.values():
            self.git(["status", "--porcelain"], folder)  # settle the index's stat cache before the snapshot
        admin = self.project / ".git" / "worktrees"
        return {
            "folders": {k: self.snap(v) for k, v in world.items()},
            "admin": {k: self.snap(admin / k) for k in world},
            "heads": self.git(["for-each-ref", "--format=%(refname) %(objectname)", "refs/heads"]),
            "stash": self.git(["stash", "list"]),
            "staged": {k: self.git(["diff", "--cached"], v) for k, v in world.items()},
        }

    def assert_reasons(self, answer: dict[str, Any], world: dict[str, Path]) -> dict[str, str]:
        kept = {norm(e["path"]): e for e in answer["needs_decision"]}
        reasons: dict[str, str] = {}
        for key, word in _KEPT_WORDS.items():
            entry = kept.get(norm(world[key]))
            self.assertIsNotNone(entry, msg=f"{key} is not listed for a decision: {answer}")
            reasons[key] = entry["reason"]
            self.assertIn(word, reasons[key].lower(), msg=f"{key}'s reason must say why: {reasons[key]!r}")
        self.assertEqual(len(set(reasons.values())), 3, msg=f"the three reasons must differ: {reasons}")
        self.assertNotIn(norm(world["l"]), paths_of(answer["retired"]), msg="a locked workspace was retired")
        self.assertNotIn(norm(world["s"]), paths_of(answer["retired"]), msg="a stashed workspace was retired")
        return reasons

    def assert_i_kept_or_carried(self, answer: dict[str, Any], world: dict[str, Path], staged: str) -> str:
        if norm(world["i"]) in paths_of(answer["needs_decision"]):
            self.assertTrue(world["i"].exists(), msg="a kept workspace's folder was removed")
            return "kept"
        entry = next(e for e in answer["brought_over"] if norm(e["path"]) == norm(world["i"]))
        carried = self.git(["diff", "--cached"], Path(entry["workspace_path"]))
        self.assertEqual(carried, staged, msg="the brought-over copy lost the staged change")
        return "carried"

    def test_work_that_cannot_be_carried_exactly_keeps_the_old_workspace(self):
        # covers: BO-4300f-3-iii
        # angle: deployed
        """AC-3 (A9): m (merge with an unresolved conflict), s (a stash made on its branch) and l (locked,
        'on USB drive') are listed in needs_decision with distinct reasons, by the preview and then by the
        run; i (a staged change) is either listed or brought over with `git diff --cached` identical. The
        folder digests, registration files, `git stash list` and branch tips of m, s and l are unchanged by
        both -- even for s and l, which hold nothing unsent.
        Must implement: an in-progress operation, a stash on the workspace's branch and a user lock send the
        entry to needs_decision (run and preview); staged changes are carried with the index or kept.
        WRONG VERSIONS caught: s and l retired because nothing is unsent; m brought over as plain files; i
        brought over as an untracked file with its staged state lost; the preview reporting differently."""
        world = self.make_four()
        staged = self.git(["diff", "--cached"], world["i"])
        self.assertIn("STAGED.txt", staged)
        before = self.state(world)

        preview = self.migrate_ok(preview=True)
        preview_reasons = self.assert_reasons(preview, world)
        self.assertEqual(self.state(world), before, msg="the preview changed something")

        answer = self.migrate_ok()
        self.assertEqual(self.assert_reasons(answer, world), preview_reasons, msg="preview and run disagree")
        i_run = self.assert_i_kept_or_carried(answer, world, staged)
        i_preview = "kept" if norm(world["i"]) in paths_of(preview["needs_decision"]) else "carried"
        self.assertEqual(i_run, i_preview, msg="the preview reports i differently from the run")

        after = self.state({k: v for k, v in world.items() if k in _KEPT_WORDS})
        wanted = {name: {k: v for k, v in before[name].items() if k in _KEPT_WORDS} for name in ("folders", "admin")}
        self.assertEqual({name: after[name] for name in wanted}, wanted)
        self.assertEqual((after["heads"], after["stash"]), (before["heads"], before["stash"]))
