"""
MODULE: unit_tests/build_orchestration/test_bo_4300f_3_cutover.py
AC: BO-4300f-3 (A8 deferred readiness; A4 canonical-first identity), BO-4300a-2, BO-4300a-1 IT3 (A1),
    BO-4300c-2 (M4 migrate) -- the cut-over of old-style workspaces.
TICKET: tickets/00_inbox/epics/EPIC-WorkspaceMakerHardening/
    08_TICKET-20261022-cut-over-canonical-deferred-readiness-lossless.md

Real-subprocess proof against the DEPLOYED maker (`worktree.py migrate-legacy`, then `ensure`), real temp
repos, a real bare hub, legacy worktrees made only by the ONE test-side creator `legacy_worktree`. No mock
of git, never a build.py spawn of its own. Git runs with an isolated HOME / GIT_CONFIG_GLOBAL.

REPORT CONTRACT ASSUMED (python-coder: satisfy it, or raise the mismatch before changing a test):
a `brought_over` entry gains `next == "ensure --kind <k> --slug <s>"` and its marker state is "creating"
(A8). That ensure answers workspace_action "completed" and line_of_work "resumed" and keeps every brought-over
commit and every uncommitted and untracked file byte-identical; the completed marker carries full checks.
An unmappable line (nothing usable left of its slug) is listed `needs_decision`, untouched (A4 + ticket 06).

Placed in a NEW file because test_bo_4300f_3.py (which holds MigrateCase) is already large.

DECISION HISTORY
====================================================================
- 2026-10-22 [test-writer/EPIC-WorkspaceMakerHardening/08, BO-4300f-3]: Created the red baseline.
====================================================================
"""
from __future__ import annotations

import ast
import json
import os
import stat
import unittest
from pathlib import Path
from typing import Any

from unit_tests.build_orchestration._workspace_maker_fixtures import (  # fixtures first: avoids the builders cycle
    legacy_worktree,
    run_maker,
)
from unit_tests.build_orchestration.test_bo_4300f_3 import MigrateCase, norm

_SCRIPTS = Path(__file__).resolve().parents[2] / "templates" / "scripts"
_CUT_OVER_SOURCES = ("worktree_migrate.py", "worktree_migrate_carry.py", "worktree_migrate_guards.py")
_HOOK_FAIL_TEXT = "forced checkout failure from the fixture hook"


def _append(path: Path, text: str) -> None:
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _has_hardlinked_object(workspace: Path) -> bool:
    for root, _dirs, files in os.walk(workspace / ".git" / "objects"):
        if any(os.stat(os.path.join(root, name)).st_nlink > 1 for name in files):
            return True
    return False


class CutOverCase(MigrateCase):
    """MigrateCase plus readers for a brought-over workspace's marker and entries."""

    def marker(self, workspace: Path) -> dict[str, Any]:
        return json.loads((workspace / ".leafcutter" / "workspace.json").read_text(encoding="utf-8"))

    def entry_for(self, answer: dict[str, Any], legacy: Path, bucket: str = "brought_over") -> dict[str, Any]:
        entry = next((e for e in answer[bucket] if norm(e["path"]) == norm(legacy)), None)
        self.assertIsNotNone(entry, msg=f"{legacy} is not in {bucket}: {answer}")
        return entry

    def maker(self, args: list[str]) -> dict[str, Any]:
        return run_maker(args, cwd=self.project, env=self.env(), timeout=180)


class TestDeferredReadiness(CutOverCase):
    def test_brought_over_workspace_is_not_ready_until_proven(self):
        # covers: BO-4300f-3
        # angle: deployed
        """AC-1 (A8): a legacy feature/a with an unpushed commit, an uncommitted edit and an untracked file
        is brought over with marker state 'creating', verify answers INCOMPLETE, its entry names
        `ensure --kind feature --slug a`, and that ensure answers ok / completed / resumed with the commit,
        the edit and the untracked file byte-identical and the completed marker holding full checks.
        Must implement: _marker writes 'creating' + brought_over entry gains `next`; ensure's creating-and-
        checked-out path answers the marker's recorded 'resumed' (not head_state's 'new').
        WRONG VERSIONS caught: marker still 'ready' (never proven); no `next` hint; line_of_work 'new' from
        head_state; ensure refusing or touching the brought-over content; a completed marker with no checks."""
        legacy = legacy_worktree(self.project, "feature/a", unsent=True)
        _append(legacy / "README.md", "uncommitted edit by the person\n")
        (legacy / "UNTRACKED_NOTES.txt").write_bytes(b"untracked notes\n")
        sha = self.git(["rev-parse", "HEAD"], legacy)
        kept = {n: (legacy / n).read_bytes() for n in ("README.md", "UNTRACKED_NOTES.txt", "UNSENT_WORK.txt")}

        entry = self.entry_for(self.migrate_ok(), legacy)
        ws = Path(entry["workspace_path"])
        self.assertEqual(self.marker(ws).get("state"), "creating", msg=f"{entry}")
        verify = self.maker(["verify", "--path", str(ws)])["answer"]
        self.assertEqual(verify.get("code"), "INCOMPLETE", msg=f"{verify}")
        self.assertEqual(entry.get("next"), "ensure --kind feature --slug a", msg=f"{entry}")

        res = self.maker(["ensure", "--kind", "feature", "--slug", "a"])
        answer = res["answer"]
        self.assertEqual((answer.get("status"), res["exit_code"]), ("ok", 0), msg=f"{res}")
        self.assertEqual(answer.get("workspace_action"), "completed", msg=f"{answer}")
        self.assertEqual(answer.get("line_of_work"), "resumed", msg=f"{answer}")
        self.assertEqual(norm(answer.get("workspace_path", "")), norm(ws), msg=f"{answer}")
        self.assertEqual(self.git(["rev-parse", "HEAD"], ws), sha)
        self.assertEqual({n: (ws / n).read_bytes() for n in kept}, kept, msg="brought-over bytes changed")
        # the install's own output is untracked here (the fixture has no .gitignore for it): name it, nothing broader
        install_output = {"?? .leafcutter/", "?? INSTALLED_MARKER.txt"}
        status = [ln.strip() for ln in self.git(["status", "--porcelain"], ws).splitlines()]
        work = sorted(ln for ln in status if ln not in install_output)
        self.assertEqual(work, ["?? UNTRACKED_NOTES.txt", "M README.md"], msg=f"{status}")
        self.assert_completed_marker_has_full_checks(ws)

    def assert_completed_marker_has_full_checks(self, ws: Path) -> None:
        marker = self.marker(ws)
        self.assertEqual(marker.get("state"), "ready", msg=f"{marker}")
        self.assertEqual(marker.get("line_of_work"), "resumed", msg=f"{marker}")
        checks = marker.get("checks") or {}
        self.assertIs(checks.get("build_ok"), True, msg=f"completed marker lacks a proven build: {marker}")
        verify = self.maker(["verify", "--path", str(ws)])["answer"]
        self.assertEqual(verify.get("status"), "ok", msg=f"{verify}")


class TestCanonicalIdentity(CutOverCase):
    def test_legacy_feature_line_is_one_workspace_whichever_kind_finds_it(self):
        # covers: BO-4300f-3
        # covers: BO-4300a-2
        # angle: deployed
        """AC-2 (A4): cut over a legacy feature/x holding unsent work, then `ensure --kind feature --slug x`:
        the same workspace_path the cut-over reported (<landing>/feature/x, never ticket/x), workspace_action
        completed or re-readied, ONE folder for x in the landing place, and one branch for x in the hub and
        in the workspace.
        WRONG VERSIONS caught: declared aliases tried before canonical prefixes (feature/x landing under
        ticket/x, a second workspace on ensure); a second line for x created by the later ensure."""
        legacy = legacy_worktree(self.project, "feature/x", unsent=True)
        entry = self.entry_for(self.migrate_ok(), legacy)
        reported = Path(entry["workspace_path"])
        self.assertEqual(norm(reported), norm(self.landing / "feature" / "x"), msg=f"{entry}")

        res = self.maker(["ensure", "--kind", "feature", "--slug", "x"])
        answer = res["answer"]
        self.assertEqual((answer.get("status"), res["exit_code"]), ("ok", 0), msg=f"{res}")
        self.assertEqual(norm(answer.get("workspace_path", "")), norm(reported), msg=f"{answer}")
        self.assertIn(answer.get("workspace_action"), ("completed", "re-readied"), msg=f"{answer}")
        folders = sorted(p.relative_to(self.landing).as_posix() for p in self.landing.glob("*/x"))
        self.assertEqual(folders, ["feature/x"], msg="the landing place must hold exactly one folder for x")
        for repo, expected in ((self.hub, []), (reported, ["feature/x"])):
            heads = self.git(["for-each-ref", "--format=%(refname:short)", "refs/heads"], repo).splitlines()
            self.assertEqual([h for h in heads if h.rsplit("/", 1)[-1] == "x"], expected, msg=f"{repo}: {heads}")

    def test_legacy_line_with_no_usable_name_is_left_for_a_decision(self):
        # covers: BO-4300f-3
        # angle: failure
        """A4 + ticket 06 empty-slug guard: a legacy line feature/--- (nothing usable left of its slug after
        normalising) holding unsent work is listed needs_decision, untouched, and nothing is made in the
        landing place -- never a guessed or empty-named workspace.
        WRONG VERSION caught: identity_for returning Identity('feature', '') and landing at <landing>/feature."""
        legacy = legacy_worktree(self.project, "feature/---", unsent=True)
        before = self.snap(legacy)
        answer = self.migrate_ok()
        entry = self.entry_for(answer, legacy, "needs_decision")
        self.assertTrue(entry.get("reason"), msg=f"{entry}")
        self.assertEqual(answer["brought_over"], [], msg=f"{answer}")
        self.assertEqual(self.snap(legacy), before)
        self.assertFalse(self.landing.exists() and any(self.landing.rglob("*")), msg="nothing may be made")


class TestSharedHelpers(unittest.TestCase):
    def test_cut_over_uses_the_shared_delete_and_status_helpers_not_its_own_copies(self):
        # covers: BO-4300f-3
        # angle: criterion
        """M17 (BO-4300e-2 IT1): the cut-over modules (worktree_migrate and its _carry / _guards siblings) define no `_rmtree_onerror`, `_drop` or `_status_paths` of
        its own and calls worktree_remove's delete_whole_folder and status_entries / parse_status_z.
        Must implement: replace the three private copies by the shared helpers."""
        trees = [ast.parse((_SCRIPTS / name).read_text(encoding="utf-8")) for name in _CUT_OVER_SOURCES
                 if (_SCRIPTS / name).is_file()]
        defined = {n.name for tree in trees for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        self.assertEqual(defined & {"_rmtree_onerror", "_drop", "_status_paths"}, set(),
                         msg="the cut-over still carries its own delete / status-parsing copies")
        used = {n.attr for tree in trees for n in ast.walk(tree)
                if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "wrm"}
        self.assertIn("delete_whole_folder", used)
        self.assertTrue({"status_entries", "parse_status_z"} & used, msg=f"wrm users: {sorted(used)}")


class TestCloneSourceAndReasons(CutOverCase):
    def _fail_checkout_of(self, branch: str) -> None:
        """Make the clone's own `git checkout` of *branch* exit non-zero with git-looking stderr, via a
        template post-checkout hook (the hook's status becomes checkout's). Written after the world is built."""
        template = self.tmp / "template" / "hooks"
        template.mkdir(parents=True)
        hook = template / "post-checkout"
        with open(hook, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(f'#!/bin/sh\nif [ "$(git symbolic-ref -q HEAD)" = "refs/heads/{branch}" ]; then\n'
                     f'  echo "fatal: {_HOOK_FAIL_TEXT}" >&2\n  exit 1\nfi\nexit 0\n')
        hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        _append(self.home / ".gitconfig", f"[init]\n\ttemplateDir = {(self.tmp / 'template').as_posix()}\n")

    def test_brought_over_clone_is_hardlinked_from_main_checkout_and_reasons_carry_no_git_text(self):
        # covers: BO-4300f-3
        # angle: deployed
        """AC-5 (A1 / M2, M4 migrate): against a file:// hub (a plain-path hub hides the defect: git hardlinks
        a clone of a path either way), a brought-over clone's origin is the hub and some object under its
        .git/objects has st_nlink > 1; and a legacy line whose checkout is forced to fail is listed
        needs_decision with a reason that names the step and holds no line of git's stderr (no 'fatal:').
        Must implement: clone str(ctx.repo_root), re-point origin at ctx.hub, pruning fetch from the hub;
        a step-named reason in _git_steps.
        WRONG VERSIONS caught: cloning the hub (no hardlinks over a URL); git's stderr in the reason."""
        hub_url = self.hub.resolve().as_uri()
        self.git(["remote", "set-url", "origin", hub_url])
        good = legacy_worktree(self.project, "feature/a", unsent=True)
        bad = legacy_worktree(self.project, "feature/b", unsent=True)
        bad_before = self.snap(bad)
        self._fail_checkout_of("feature/b")

        answer = self.migrate_ok()
        ws = Path(self.entry_for(answer, good)["workspace_path"])
        self.assertEqual(self.git(["config", "--get", "remote.origin.url"], ws), hub_url)
        self.assertTrue(_has_hardlinked_object(ws), "no object file has st_nlink > 1: not a clone of the main checkout")

        reason = self.entry_for(answer, bad, "needs_decision")["reason"]
        self.assertIn("checkout", reason.lower(), msg=f"the reason must name the failing step: {reason!r}")
        self.assertNotIn("fatal:", reason, msg=reason)
        self.assertNotIn(_HOOK_FAIL_TEXT, reason, msg=f"git's own text leaked into the reason: {reason!r}")
        self.assertEqual(self.snap(bad), bad_before)
        self.assertFalse((self.landing / "feature" / "b").exists(), msg="a failed clone must leave nothing behind")


if __name__ == "__main__":
    unittest.main()
