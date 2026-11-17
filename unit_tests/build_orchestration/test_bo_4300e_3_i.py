"""
MODULE: unit_tests/build_orchestration/test_bo_4300e_3_i.py
AC: BO-4300e-3-i -- A discard token clears only the workspace and the unsent work it was issued for.

Given an unattended clean-up clears "alpha" and "beta", both holding unsent work, and holds the
token returned by the refusal to clear "alpha": clearing "beta" with alpha's token is refused and
beta is identical before and after; clearing "alpha" with its own token removes it. And: a token
issued for "gamma" is worthless once one more commit exists in "gamma" (or its listed uncommitted
file is edited, or the workspace was re-made at the same path).

Real-subprocess proof against the DEPLOYED maker; real repos; helpers from test_bo_4300e_2.py.

DECISION HISTORY
====================================================================
- 2026-10-12 16:30 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/08,
  BO-4300e-3-i]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/08)
====================================================================
"""
from __future__ import annotations

import time
import unittest
from pathlib import Path

from unit_tests.build_orchestration.test_bo_4300e_2 import WorkspaceCase, names_file, shas_name


class TestTokenBinding(WorkspaceCase):
    def refused_unchanged(self, ws: Path, token: str | None, before, heads) -> dict:
        """Request removal with *token*; it must be refused UNSENT_WORK and leave *ws* identical."""
        answer = self.refuse(ws, token)
        self.assertTrue(ws.is_dir())
        self.assertEqual(self.snap(ws), before, msg="a refused request changed the workspace")
        self.assertEqual(self.refs(ws), heads, msg="a refused request changed the workspace's commits")
        return answer

    def two_unsent(self):
        alpha, alpha_sha = self.make_unsent("alpha", "a")
        beta, beta_sha = self.make_unsent("beta", "b")
        return alpha, alpha_sha, beta, beta_sha

    def test_authorisation_for_alpha_removes_alpha_only(self):
        # covers: BO-4300e-3-i
        # angle: criterion
        """AC-6: alpha, requested with the token from its own refusal, is removed (ok, folder
        gone); beta, holding its own unsent work, is still there."""
        alpha, _a, beta, _b = self.two_unsent()
        token_alpha = self.refuse(alpha)["discard_token"]
        res = self.remove(alpha, token_alpha)
        self.assertEqual(res["answer"].get("status"), "ok", msg=f"{res}")
        self.assertFalse(alpha.exists())
        self.assertTrue(beta.is_dir(), msg="alpha's token also cleared beta")

    def test_token_for_alpha_cannot_clear_beta(self):
        # covers: BO-4300e-3-i
        # angle: failure
        """AC-6: beta, requested with alpha's token, is refused UNSENT_WORK with its OWN lists and a
        different token, the message states the presented token does not match, and beta's files,
        commits and marker are byte-identical. Then alpha's own token still clears alpha."""
        alpha, _a, beta, beta_sha = self.two_unsent()
        token_alpha = self.refuse(alpha)["discard_token"]
        before, heads = self.snap(beta), self.refs(beta)
        answer = self.refused_unchanged(beta, token_alpha, before, heads)
        self.assertTrue(shas_name(answer["unsent"]["commits"], beta_sha), msg=f"{answer}")
        self.assertTrue(names_file(answer["unsent"]["files"], "dirty-b.txt"), msg=f"{answer}")
        self.assertFalse(names_file(answer["unsent"]["files"], "dirty-a.txt"), msg=f"{answer}")
        self.assertTrue(answer.get("discard_token"), msg=f"{answer}")
        self.assertNotEqual(answer["discard_token"], token_alpha)
        self.assertIn("match", answer.get("message", "").lower(), msg=f"{answer}")
        self.assertEqual(self.remove(alpha, token_alpha)["answer"].get("status"), "ok")
        self.assertFalse(alpha.exists())

    def test_beta_without_its_own_authorisation_is_refused_and_unchanged(self):
        # covers: BO-4300e-3-i
        # angle: boundary
        """AC-6: beta, requested next without any token, is UNSENT_WORK and byte-identical (alpha's
        earlier authorisation left nothing behind that applies to beta)."""
        alpha, _a, beta, _b = self.two_unsent()
        token_alpha = self.refuse(alpha)["discard_token"]
        self.assertEqual(self.remove(alpha, token_alpha)["answer"].get("status"), "ok")
        before, heads = self.snap(beta), self.refs(beta)
        answer = self.refused_unchanged(beta, None, before, heads)
        self.assertTrue(answer.get("discard_token"), msg=f"{answer}")
        self.assertNotEqual(answer["discard_token"], token_alpha)

    def test_token_is_invalid_after_a_new_commit(self):
        # covers: BO-4300e-3-i
        # angle: failure
        """AC-6: gamma refused with token T; one more commit is made in gamma; remove with T is
        refused UNSENT_WORK listing BOTH shas, with gamma byte-identical to just before that request."""
        gamma, first = self.make_unsent("gamma", "g")
        token = self.refuse(gamma)["discard_token"]
        second = self.commit_unsent(gamma, "commit-g2.txt", "second unpushed\n")
        before, heads = self.snap(gamma), self.refs(gamma)
        answer = self.refused_unchanged(gamma, token, before, heads)
        commits = answer["unsent"]["commits"]
        self.assertEqual(len(commits), 2, msg=f"{answer}")
        self.assertTrue(shas_name(commits, first) and shas_name(commits, second), msg=f"{commits}")
        self.assertNotEqual(answer.get("discard_token"), token)

    def test_token_is_invalid_after_an_uncommitted_file_is_edited(self):
        # covers: BO-4300e-3-i
        # angle: boundary
        """AC-6: gamma refused with token T; the already-listed uncommitted file's content is edited
        (same path set); remove with T is refused and gamma is unchanged."""
        gamma, _sha = self.make_unsent("gamma", "g")
        first = self.refuse(gamma)
        self.dirty(gamma, "dirty-g.txt", "uncommitted g -- edited after the refusal\n")
        before, heads = self.snap(gamma), self.refs(gamma)
        answer = self.refused_unchanged(gamma, first["discard_token"], before, heads)
        self.assertEqual(answer["unsent"]["files"], first["unsent"]["files"], msg="same path set expected")
        self.assertNotEqual(answer.get("discard_token"), first["discard_token"])

    def test_token_for_a_remade_workspace_at_the_same_path_is_invalid(self):
        # covers: BO-4300e-3-i
        # angle: boundary
        """AC-6: delta refused with token T, then removed with T; delta is re-made at the same path
        with equivalent uncommitted content; remove with the old T is refused and the new workspace is
        unchanged (the maker record, not only the content, is part of the binding)."""
        delta = self.ensure("delta")
        self.dirty(delta, "dirty-d.txt", "uncommitted d\n")
        token = self.refuse(delta)["discard_token"]
        self.assertEqual(self.remove(delta, token)["answer"].get("status"), "ok")
        self.assertFalse(delta.exists())
        time.sleep(1.2)  # the maker record carries a seconds-resolution creation time
        again = self.ensure("delta")
        self.assertEqual(again, delta)
        self.dirty(again, "dirty-d.txt", "uncommitted d\n")
        before, heads = self.snap(again), self.refs(again)
        answer = self.refused_unchanged(again, token, before, heads)
        self.assertNotEqual(answer.get("discard_token"), token)


if __name__ == "__main__":
    unittest.main()
