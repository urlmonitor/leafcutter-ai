"""
MODULE: unit_tests/build_orchestration/test_bo_4300e_1_shapes.py
AC: BO-4300c-2 (A2 item 6) / BO-4300e-1 -- locate, verify and list answer in the contract's field
    shape: top-level kind, slug, branch, checks; workspace_action 'located', line_of_work 'existing',
    created false, fetch 'skipped', origin_main_commit, base_matches_origin_main (no bootstrap or
    hooks_stages_declared); list entries are exactly {kind, slug, branch, workspace_path,
    workspace_path_posix, state}.

Real-subprocess proof against the DEPLOYED maker; the half-made workspace comes from the maker's own
LEAFCUTTER_WORKSPACE_ABORT_AT=after_clone seam.

DECISION HISTORY
====================================================================
- 2026-10-22 [test-writer/EPIC-WorkspaceMakerHardening/07, BO-4300c-2]: Created the red baseline.
  (#EPIC-WorkspaceMakerHardening/07)
====================================================================
"""
from __future__ import annotations

import unittest

from unit_tests.build_orchestration.test_bo_4300e_2 import KIND, WorkspaceCase

LIST_KEYS = {"kind", "slug", "branch", "workspace_path", "workspace_path_posix", "state"}


class TestContractShape(WorkspaceCase):
    def assert_located_shape(self, label: str, answer: dict, branch: str, tip: str) -> None:
        self.assertEqual(answer.get("status"), "ok", msg=f"{label}: {answer}")
        self.assertEqual((answer.get("kind"), answer.get("slug"), answer.get("branch")),
                         (KIND, "x", branch), msg=f"{label}: {answer}")
        self.assertIsInstance(answer.get("checks"), dict, msg=f"{label}: {answer}")
        self.assertEqual(answer.get("workspace_action"), "located", msg=label)
        self.assertEqual(answer.get("line_of_work"), "existing", msg=label)
        self.assertIs(answer.get("created"), False, msg=label)
        self.assertEqual(answer.get("fetch"), "skipped", msg=label)
        self.assertEqual(answer.get("origin_main_commit"), tip, msg=f"{label}: {answer}")
        self.assertIs(answer.get("base_matches_origin_main"), True, msg=f"{label}: {answer}")
        for absent in ("bootstrap", "hooks_stages_declared"):
            self.assertNotIn(absent, answer, msg=f"{label}: ensure-only field {absent}")

    def test_locate_verify_list_answer_in_the_contract_shape(self):
        # covers: BO-4300c-2
        # covers: BO-4300e-1
        # angle: deployed
        """Locate (by name and by path) and verify carry the located shape, with origin_main_commit
        equal to the workspace's own last-fetched origin/main. list: each entry's key set is exactly
        LIST_KEYS; the ready workspace is 'ready' and the half-made one is 'incomplete'."""
        made = self.cli(["ensure", "--kind", KIND, "--slug", "x", "--repo-root", str(self.project)])
        self.assertEqual(made["answer"].get("status"), "ok", msg=f"{made}")
        branch = made["answer"]["branch"]
        ws = self.landing / KIND / "x"
        tip = self.git(["rev-parse", "refs/remotes/origin/main"], ws)
        self.assertEqual(tip, self.git(["rev-parse", "main"], self.hub), msg="fixture: ensure fetched")

        by_name = self.cli(["locate", "--kind", KIND, "--slug", "x", "--repo-root", str(self.project)])
        by_path = self.cli(["locate", "--path", str(ws)])
        verified = self.cli(["verify", "--path", str(ws)])
        for label, res in (("locate name", by_name), ("locate path", by_path), ("verify", verified)):
            self.assert_located_shape(label, res["answer"], branch, tip)

        self.cli(["ensure", "--kind", KIND, "--slug", "delta", "--repo-root", str(self.project)],
                 extra_env={"LEAFCUTTER_WORKSPACE_ABORT_AT": "after_clone"})
        listed = self.cli(["list", "--repo-root", str(self.project)])["answer"]
        self.assertEqual(listed.get("status"), "ok", msg=f"{listed}")
        entries = {e.get("slug"): e for e in listed["workspaces"]}
        self.assertEqual(set(entries), {"x", "delta"}, msg=f"{listed}")
        for slug, entry in entries.items():
            self.assertEqual(set(entry), LIST_KEYS, msg=f"{slug}: {entry}")
        self.assertEqual(entries["x"]["state"], "ready")
        self.assertEqual(entries["delta"]["state"], "incomplete")
        self.assertEqual((entries["x"]["kind"], entries["x"]["branch"]), (KIND, branch))


if __name__ == "__main__":
    unittest.main()
