"""
MODULE: unit_tests/build_orchestration/test_bo_4300e_2_xi.py
AC: BO-4300e-2-xi -- A workspace whose repository can no longer be read is refused as half-cleared
(not as a fetch or git failure), and only its one-time token lets it go.

Real-subprocess proof against the DEPLOYED maker. Fixture: `feature/zeta` is made by `ensure`, then
the stored objects of its repository (loose objects and packs) are deleted so HEAD no longer
resolves to a readable commit, and everything but README.md and src/app.py outside the repository
and the record is removed. The refusal shape follows test_bo_4300e_2_vi.py (UNSENT_WORK,
unsent.files, discard_token, then --discard-token and discarded.files). Workspaces use KIND
"feature" (the shared helper's kind). Helpers come from test_bo_4300e_2.py / _2_ix.py.

DECISION HISTORY
====================================================================
- 2026-11-03 [test-writer/fast-lane bo-4300e-2, BO-4300e-2-xi]: Created the red baseline.
====================================================================
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from typing import Any

from unit_tests.build_orchestration.test_bo_4300e_2 import _force_rmtree
from unit_tests.build_orchestration.test_bo_4300e_2_ix import StopCase

FILES = ["README.md", "src/app.py"]

GIT_FAILS = '''\
import os
import subprocess

_real_run = subprocess.run
_mode = os.environ["GIT_FAILURE_MODE"]


def run(args, *a, **k):
    first = args[0] if isinstance(args, (list, tuple)) and args else args
    if os.path.basename(str(first)).lower().startswith("git"):
        if _mode == "timeout":
            raise subprocess.TimeoutExpired(args, 1)
        raise FileNotFoundError(2, "git not found")
    return _real_run(args, *a, **k)


subprocess.run = run
'''


def says_half_cleared_unreadable(text: str) -> bool:
    low = text.lower()
    return ("half-cleared" in low or "half cleared" in low) and "no longer be read" in low \
        and "cannot be checked" in low and "shared project" in low


class DamagedCase(StopCase):
    def damage(self, ws: Path, drop_head: bool = False) -> Path:
        """Delete the stored objects (and optionally HEAD), keep only README.md and src/app.py outside .git."""
        record = (ws / ".leafcutter" / "workspace.json").read_bytes()
        objects = ws / ".git" / "objects"
        for child in sorted(objects.iterdir()):
            if child.is_dir():
                _force_rmtree(child)
            else:
                os.chmod(child, 0o600)
                child.unlink()
        if drop_head:
            (ws / ".git" / "HEAD").unlink()
        for child in sorted(ws.iterdir()):
            if child.name == ".git":
                continue
            if child.is_dir():
                _force_rmtree(child)
            else:
                os.chmod(child, 0o600)
                child.unlink()
        (ws / ".leafcutter").mkdir()
        (ws / ".leafcutter" / "workspace.json").write_bytes(record)
        (ws / "src").mkdir()
        (ws / "src" / "app.py").write_text("print('app')\n", encoding="utf-8", newline="\n")
        (ws / "README.md").write_text("readme\n", encoding="utf-8", newline="\n")
        return ws

    def zeta(self, slug: str = "zeta", drop_head: bool = False) -> Path:
        return self.damage(self.ensure(slug), drop_head)

    def refusal(self, ws: Path) -> dict[str, Any]:
        res = self.repeat(ws)
        self.assertEqual(res["answer"].get("status"), "refused", msg=f"{res}")
        self.assertEqual(res["answer"].get("code"), "UNSENT_WORK", msg=f"{res}")
        self.assertEqual(res["exit_code"], 2, msg=f"{res}")
        return res

    def git_failure_env(self, mode: str) -> dict[str, str]:
        folder = self.tmp / f"gitfail-{mode}"
        folder.mkdir(exist_ok=True)
        (folder / "sitecustomize.py").write_text(GIT_FAILS, encoding="utf-8", newline="\n")
        return {"PYTHONPATH": str(folder), "GIT_FAILURE_MODE": mode}


class TestUnreadableRepository(DamagedCase):
    def test_unreadable_repository_is_neither_fetch_failed_nor_a_damage_refusal(self):
        # covers: BO-4300e-2-xi
        # angle: discrimination
        """AC-1: with the shared project moved away (any fetch fails) a workspace whose objects are gone is
        refused UNSENT_WORK, never FETCH_FAILED or GIT_FAILED, because the readability check runs
        locally before any fetch (the commands git was started with are read back through GIT_TRACE:
        a fetch whose failure is ignored would answer the same). A second damaged workspace with HEAD
        missing, and a third whose HEAD is there but whose refs folder is gone (git no longer takes its
        repository folder for a repository), below a parent folder that is itself a readable repository
        WITH a commit, are answered the same way (git is pinned to the workspace's own repository
        folder and never climbs to the parent, whose HEAD would resolve)."""
        ws = self.zeta()
        wsb = self.zeta("zeta-nohead", drop_head=True)
        wsc = self.zeta("zeta-norefs")
        _force_rmtree(wsc / ".git" / "refs")  # HEAD is there but git no longer takes the folder for a repository
        parent = self.landing / "feature"
        self.git(["init", "-q"], parent)
        self.git(["-c", "user.name=parent", "-c", "user.email=parent@example.invalid", "commit", "-q",
                  "--allow-empty", "-m", "parent commit"], parent)  # HEAD resolves there, so a climb reads "readable"
        self.hub_moved_away()
        try:
            for target in (ws, wsb, wsc):
                env, trace = self.git_trace(target.name)
                res = self.repeat(target, extra_env=env)
                self.assertEqual(self.fetches_in(trace), [], msg=f"{target.name}: git was asked to fetch")
                code = res["answer"].get("code")
                self.assertNotIn(code, ("FETCH_FAILED", "GIT_FAILED"), msg=f"{target.name}: {res}")
                self.assertEqual(code, "UNSENT_WORK", msg=f"{target.name}: {res}")
                self.assertTrue(says_half_cleared_unreadable(str(res["answer"].get("message", ""))),
                                msg=f"{target.name}: {res['answer']}")
                self.assertTrue(target.is_dir(), msg=f"{target.name} was deleted")
        finally:
            self.hub_back()

    def test_remove_cli_refuses_unreadable_repository_with_exit_2_and_half_cleared_wording(self):
        # covers: BO-4300e-2-xi
        # angle: reachability
        """AC-1: the real CLI (worktree.py remove --path) gives exit 2, status refused, code UNSENT_WORK and
        a message saying the workspace was half-cleared, its repository can no longer be read so its
        commits cannot be checked, and its remaining files cannot be checked against the shared project."""
        ws = self.zeta()
        res = self.refusal(ws)
        message = str(res["answer"].get("message", ""))
        self.assertTrue(says_half_cleared_unreadable(message), msg=f"{res['answer']}")
        self.assertIn("commits", message.lower(), msg=f"{res['answer']}")

    def test_refusal_lists_exactly_the_two_files_and_binds_the_token_to_them(self):
        # covers: BO-4300e-2-xi
        # angle: criterion
        """AC-1: unsent.files is exactly [README.md, src/app.py] (nothing under .git, not the record),
        unsent.commits is empty, and discard_token is 32 lowercase hex characters (the same shape as
        the BO-4300e-3 token). The token goes stale when README.md changes after the refusal and the
        folder is identical after that stale request."""
        ws = self.zeta()
        answer = self.refusal(ws)["answer"]
        unsent = answer.get("unsent") or {}
        self.assertEqual(unsent.get("files"), FILES, msg=f"{answer}")
        self.assertEqual(unsent.get("commits"), [], msg=f"{answer}")
        token = answer.get("discard_token")
        self.assertTrue(isinstance(token, str) and len(token) == 32, msg=f"{answer}")
        self.assertEqual(set(token) - set("0123456789abcdef"), set(), msg=f"{token!r}")
        (ws / "README.md").write_text("changed after the refusal\n", encoding="utf-8", newline="\n")
        before = self.snap(ws, with_git=True)
        res = self.repeat(ws, token=token)
        self.assertEqual(res["answer"].get("status"), "refused", msg=f"a stale token cleared it: {res}")
        self.assertTrue(ws.is_dir())
        self.assertEqual(self.snap(ws, with_git=True), before)

    def test_refused_damaged_workspace_is_identical_before_and_after(self):
        # covers: BO-4300e-2-xi
        # angle: discrimination
        """AC-1: a snapshot with_git=True of feature/zeta (the damaged .git included) is equal before and
        after the refusal. Catches a check that runs git where it writes (index refresh, FETCH_HEAD,
        gc, a lock) in the damaged repository, a fetch to see what is unsent, and a token computation
        that touches the folder. Control: the next test shows the same request with the token clears it."""
        ws = self.zeta()
        before = self.snap(ws, with_git=True)
        self.assertIn("README.md", before)
        self.refusal(ws)
        self.assertTrue(ws.is_dir(), msg="the folder was deleted without a token")
        self.assertEqual(self.snap(ws, with_git=True), before)
        self.assertFalse((ws / ".git" / "FETCH_HEAD").exists(), msg="a fetch wrote into the damaged repository")

    def test_token_finishes_the_damaged_workspace_and_lists_both_files_discarded(self):
        # covers: BO-4300e-2-xi
        # angle: criterion
        """AC-1: the request repeated with the returned --discard-token is ok (exit 0), discarded.files is
        [README.md, src/app.py], discarded.commits is empty, and nothing of feature/zeta (the damaged
        repository included) remains at its location."""
        ws = self.zeta()
        token = self.refusal(ws)["answer"].get("discard_token")
        self.assertTrue(token, msg="no token to present")
        res = self.repeat(ws, token=token)
        self.assertEqual(res["answer"].get("status"), "ok", msg=f"{res}")
        self.assertEqual(res["exit_code"], 0, msg=f"{res}")
        discarded = res["answer"].get("discarded") or {}
        self.assertEqual(discarded.get("files"), FILES, msg=f"{res['answer']}")
        self.assertEqual(discarded.get("commits") or [], [], msg=f"{res['answer']}")
        self.assertFalse(os.path.lexists(ws), msg="something of zeta remains")

    def test_intact_repository_with_an_unsent_commit_is_not_treated_as_half_cleared(self):
        # covers: BO-4300e-2-xi
        # angle: discrimination
        """AC-1: feature/eta (intact repository, one unpushed commit) is refused UNSENT_WORK with the full
        40-character identifier in unsent.commits; the message neither says half-cleared nor that the
        repository cannot be read; the folder is identical. Control: the damaged zeta's message does say
        it. Where git itself fails for another reason (a timeout, git not found; simulated in the maker
        process) the existing error answer stays and is never reported as half-cleared."""
        zeta = self.zeta()
        zeta_message = str(self.refusal(zeta)["answer"].get("message", ""))
        self.assertIn("no longer be read", zeta_message.lower(), msg="control: the damaged message")
        eta = self.ensure("eta")
        sha = self.commit_unsent(eta, "unsent.txt", "unpushed\n")
        before = self.snap(eta, with_git=True)
        answer = self.refusal(eta)["answer"]
        self.assertEqual((answer.get("unsent") or {}).get("commits"), [sha], msg=f"{answer}")
        self.assertEqual(len(sha), 40)
        low = str(answer.get("message", "")).lower()
        self.assertNotIn("half-cleared", low, msg=f"{answer}")
        self.assertNotIn("no longer be read", low, msg=f"{answer}")
        self.assertEqual(self.snap(eta, with_git=True), before)
        nohead = self.zeta("zeta-nohead", drop_head=True)
        for mode in ("timeout", "missing"):
            # Positive evidence: no HEAD file is damage without asking git, so git failing to run does not hide it.
            res = self.remove(nohead, extra_env=self.git_failure_env(mode))
            self.assertEqual(res["answer"].get("code"), "UNSENT_WORK", msg=f"{mode}: damage not seen without git: {res}")
            self.assertTrue(says_half_cleared_unreadable(str(res["answer"].get("message", ""))), msg=f"{mode}: {res}")
            self.assertTrue(nohead.is_dir(), msg=f"{mode}: the damaged folder was deleted")
        for mode in ("timeout", "missing"):
            res = self.remove(eta, extra_env=self.git_failure_env(mode))
            failed = res["answer"]
            self.assertTrue(failed, msg=f"{mode}: no answer: {res}")
            self.assertNotEqual(failed.get("status"), "ok", msg=f"{mode}: {res}")
            self.assertNotEqual(failed.get("code"), "UNSENT_WORK", msg=f"{mode}: git failure became a refusal: {res}")
            self.assertNotIn("half-cleared", str(failed.get("message", "")).lower(), msg=f"{mode}: {failed}")
            self.assertNotIn("discard_token", failed, msg=f"{mode}: {failed}")
            self.assertEqual(self.snap(eta, with_git=True), before, msg=mode)


if __name__ == "__main__":
    unittest.main()
