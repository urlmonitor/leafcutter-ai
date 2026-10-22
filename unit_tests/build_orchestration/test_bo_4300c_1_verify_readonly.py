"""
MODULE: unit_tests/build_orchestration/test_bo_4300c_1_verify_readonly.py
AC: BO-4300c-1 (A3 read-only re-check, BO-4300c-1-iii) -- tree_clean is TRACKED-only everywhere and is
    never a verify refusal; origin_matches_hub tolerates respellings of the same hub; verify never
    rewrites the index.

Real-subprocess proof against the DEPLOYED maker; real temp repos and bare hub, no git mock.
Classification of the earlier expectation that an untracked file made tree_clean false:
test_drift (production is right per BO-4300c-1-iii).

DECISION HISTORY
====================================================================
- 2026-10-22 [test-writer/EPIC-WorkspaceMakerHardening/07, BO-4300c-1]: Added after the pr-reviewer
  mediums M-1, M-2 and M-3. (#EPIC-WorkspaceMakerHardening/07)
====================================================================
"""
from __future__ import annotations

import time
import unittest
from pathlib import Path

from unit_tests.build_orchestration.test_bo_4300e_2 import KIND, WorkspaceCase


class TestVerifyReadOnly(WorkspaceCase):
    def verify(self, ws: Path) -> dict:
        return self.cli(["verify", "--path", str(ws)])

    def reensure(self, slug: str) -> dict:
        return self.cli(["ensure", "--kind", KIND, "--slug", slug, "--repo-root", str(self.project)])

    def test_tree_clean_is_tracked_only_and_ensure_and_verify_agree(self):
        # covers: BO-4300c-1
        # angle: discrimination
        """Untracked file: verify ok, tree_clean true, and a repeat ensure agrees. Modified tracked
        file: verify still ok (never refuses on tree_clean) with tree_clean false, and ensure's
        answer reports the same tree_clean value for the same workspace."""
        ws = self.ensure("x")
        self.dirty(ws, "UNTRACKED_ONLY.txt")
        ver = self.verify(ws)
        self.assertEqual(ver["answer"].get("status"), "ok", msg=f"{ver}")
        self.assertIs(ver["answer"]["checks"].get("tree_clean"), True, msg=f"untracked counted: {ver}")
        ens = self.reensure("x")
        self.assertIs((ens["answer"].get("checks") or {}).get("tree_clean"), True, msg=f"{ens}")

        self.dirty(ws, "README.md", "tracked change\n")
        ver = self.verify(ws)
        self.assertEqual((ver["answer"].get("status"), ver["exit_code"]), ("ok", 0), msg=f"{ver}")
        self.assertIs(ver["answer"]["checks"].get("tree_clean"), False, msg=f"{ver}")
        ens = self.reensure("x")
        self.assertEqual((ws / "README.md").read_text(encoding="utf-8"), "tracked change\n",
                         msg=f"ensure destroyed an uncommitted tracked change: {ens}")
        self.assertEqual(ens["answer"].get("status"), "ok", msg=f"{ens}")
        ens_clean = (ens["answer"].get("checks") or {}).get("tree_clean")
        self.assertIs(ens_clean, False, msg=f"{ens}")
        self.assertEqual(ens_clean, ver["answer"]["checks"].get("tree_clean"), msg="ensure and verify disagree")

    def test_origin_matches_hub_tolerates_respellings_but_not_another_hub(self):
        # covers: BO-4300c-1
        # angle: boundary
        """Origin respelled with a trailing '/', as file://<path>, or without the .git suffix still
        verifies ok. Control: an origin at a genuinely different hub is VERIFY_FAILED naming
        origin_matches_hub."""
        ws = self.ensure("x")
        hub = str(self.hub)
        stem = hub[:-4] if hub.endswith(".git") else hub
        for label, url in (("trailing slash", hub + "/"), ("file scheme", "file://" + hub),
                           ("no .git suffix", stem)):
            self.git(["remote", "set-url", "origin", url], ws)
            res = self.verify(ws)
            self.assertEqual(res["answer"].get("status"), "ok", msg=f"{label} ({url}): {res}")
            self.assertIs(res["answer"]["checks"].get("origin_matches_hub"), True, msg=label)
        self.git(["remote", "set-url", "origin", str(self.tmp / "another-hub.git")], ws)
        res = self.verify(ws)
        self.assertEqual(res["answer"].get("code"), "VERIFY_FAILED", msg=f"{res}")
        self.assertIn("origin_matches_hub", res["answer"].get("failed_ingredients", []), msg=f"{res}")

    def test_verify_does_not_rewrite_the_index(self):
        # covers: BO-4300c-1
        # angle: discrimination
        """With a stat-dirty tracked file (rewritten, same content) a plain `git status` refreshes the
        index; verify must leave .git/index bytes and mtime untouched."""
        ws = self.ensure("x")
        readme = ws / "README.md"
        readme.write_bytes(readme.read_bytes())  # same bytes, new stat data
        time.sleep(1.1)
        index = ws / ".git" / "index"
        before = (index.read_bytes(), index.stat().st_mtime_ns)
        res = self.verify(ws)
        self.assertEqual(res["answer"].get("status"), "ok", msg=f"{res}")
        self.assertEqual((index.read_bytes(), index.stat().st_mtime_ns), before,
                         msg="verify rewrote the index")


if __name__ == "__main__":
    unittest.main()
