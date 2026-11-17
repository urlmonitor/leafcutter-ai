"""
MODULE: unit_tests/build_orchestration/test_bo_4300c_1_verify_refuses.py
AC: BO-4300c-1 (A3 read-only re-check) -- verify refuses a workspace whose ingredient is false, never
    on freshness or a dirty tree, and never fetches; a --kind/--slug that names another identity is
    VERIFY_FAILED ['identity']; an unknown kind is USAGE.

Real-subprocess proof against the DEPLOYED maker (shared locator), real temp repos and bare hub, no
mock of git, never a build.py spawn of its own.

DECISION HISTORY
====================================================================
- 2026-10-22 [test-writer/EPIC-WorkspaceMakerHardening/07, BO-4300c-1]: Created the red baseline.
  (#EPIC-WorkspaceMakerHardening/07)
====================================================================
"""
from __future__ import annotations

import unittest
from pathlib import Path

from unit_tests.build_orchestration.test_bo_4300e_2 import KIND, WorkspaceCase


class TestVerifyRefuses(WorkspaceCase):
    def verify(self, ws: Path, *extra: str) -> dict:
        return self.cli(["verify", "--path", str(ws), *extra])

    def advance_hub(self) -> str:
        """Push one new commit to the hub's main from a scratch clone; return the new tip."""
        scratch = self.tmp / "advancer"
        self.git(["clone", "-q", str(self.hub), str(scratch)], self.tmp)
        self.git(["config", "user.email", "adv@example.com"], scratch)
        self.git(["config", "user.name", "Advancer"], scratch)
        (scratch / "ADVANCED.txt").write_text("hub moved on\n", encoding="utf-8", newline="\n")
        self.git(["add", "-A"], scratch)
        self.git(["commit", "-q", "-m", "hub moved on"], scratch)
        self.git(["push", "-q", "origin", "main"], scratch)
        return self.git(["rev-parse", "HEAD"], scratch)

    def test_verify_refuses_a_false_ingredient_and_never_on_freshness_or_clean_tree(self):
        # covers: BO-4300c-1
        # covers: BO-4300c-2
        # angle: deployed
        """gc.auto re-enabled -> refused VERIFY_FAILED exit 2, failed_ingredients exactly
        ['gc_auto_disabled'], no workspace_path. Control: with gc.auto reset, an untracked file, a modified
        tracked file and a hub that moved on, verify answers ok (so the refusal is about the ingredient, not about
        verify refusing everything), and it fetched nothing: hub refs and FETCH_HEAD unchanged."""
        ws = self.ensure("x")
        self.git(["config", "gc.auto", "1"], ws)
        res = self.verify(ws)
        answer = res["answer"]
        self.assertEqual((answer.get("status"), answer.get("code"), res["exit_code"]),
                         ("refused", "VERIFY_FAILED", 2), msg=f"{res}")
        self.assertEqual(answer.get("failed_ingredients"), ["gc_auto_disabled"], msg=f"{res}")
        self.assertNotIn("workspace_path", answer)

        self.git(["config", "gc.auto", "0"], ws)
        self.dirty(ws, "UNCOMMITTED.txt")  # untracked: tree_clean is tracked-only (BO-4300c-1-iii)
        self.dirty(ws, "README.md", "tracked change\n")
        self.advance_hub()
        fetch_head = ws / ".git" / "FETCH_HEAD"
        before_fetch = fetch_head.read_bytes() if fetch_head.exists() else None
        before_refs = self.git(["for-each-ref"], self.hub)
        before_origin = self.git(["for-each-ref", "refs/remotes"], ws)
        res = self.verify(ws)
        self.assertEqual(res["answer"].get("status"), "ok", msg=f"{res}")
        self.assertEqual(res["exit_code"], 0, msg=f"{res}")
        self.assertIs(res["answer"]["checks"].get("tree_clean"), False, msg=f"{res}")
        self.assertEqual(self.git(["for-each-ref"], self.hub), before_refs)
        self.assertEqual(self.git(["for-each-ref", "refs/remotes"], ws), before_origin,
                         msg="verify moved the workspace's remote-tracking refs (it fetched)")
        after_fetch = fetch_head.read_bytes() if fetch_head.exists() else None
        self.assertEqual(after_fetch, before_fetch, msg="verify wrote FETCH_HEAD (it fetched)")

    def test_verify_with_mismatched_identity_is_verify_failed_and_bad_kind_is_usage(self):
        # covers: BO-4300c-1
        # angle: failure
        """Control: the matching --kind/--slug verifies ok. A different slug is VERIFY_FAILED with
        failed_ingredients exactly ['identity'] (no workspace_path); --kind bogus is USAGE, exit 64."""
        ws = self.ensure("x")
        ok = self.verify(ws, "--kind", KIND, "--slug", "x")
        self.assertEqual(ok["answer"].get("status"), "ok", msg=f"{ok}")
        res = self.verify(ws, "--kind", KIND, "--slug", "other")
        answer = res["answer"]
        self.assertEqual((answer.get("status"), answer.get("code"), res["exit_code"]),
                         ("refused", "VERIFY_FAILED", 2), msg=f"{res}")
        self.assertEqual(answer.get("failed_ingredients"), ["identity"], msg=f"{res}")
        self.assertNotIn("workspace_path", answer)
        bad = self.verify(ws, "--kind", "bogus", "--slug", "x")
        self.assertEqual((bad["answer"].get("code"), bad["exit_code"]), ("USAGE", 64), msg=f"{bad}")


if __name__ == "__main__":
    unittest.main()
