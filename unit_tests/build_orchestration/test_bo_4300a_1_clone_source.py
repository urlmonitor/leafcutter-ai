"""
MODULE: unit_tests/build_orchestration/test_bo_4300a_1_clone_source.py
AC: BO-4300a-1 IT3 (amended 2026-10-22, A1) / BO-4300d-4 IT0 -- a workspace is a hardlinked local clone
    OF THE MAIN CHECKOUT whose origin is the hub, and refs/remotes/origin/* name only the hub's branches.
TICKET: tickets/00_inbox/epics/EPIC-WorkspaceMakerHardening/
    05_TICKET-20261022-ensure-clones-main-checkout-contract-shape.md

The hub is a SEPARATE bare repository reached by a ``file://`` URL. A plain-path hub hides the defect: git
honours ``--local`` (hardlinks) for a path, so cloning the hub looks like cloning the main checkout. A URL
hub gets a full copy with no hardlinks (as ``git@github.com:`` would), so only a clone of the main checkout
can satisfy the hardlink promise. The main checkout also holds a local-only branch ``feature/x`` and a
local ``main`` that is behind the hub.

Runs the DEPLOYED maker (shared locator); never spawns scripts/build.py itself.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._workspace_maker_fixtures import make_project  # fixtures first: builders cycle
from unit_tests.build_orchestration._bo_4300a_1_ii_fixtures import git, maker  # noqa: I001


def _has_hardlinked_object(workspace: Path) -> bool:
    for root, _dirs, files in os.walk(workspace / ".git" / "objects"):
        if any(os.stat(os.path.join(root, name)).st_nlink > 1 for name in files):
            return True
    return False


class TestCloneSource(unittest.TestCase):
    def test_workspace_is_hardlinked_clone_of_main_checkout_with_origin_at_hub(self):
        # covers: BO-4300a-1
        # covers: BO-4300d-4
        # angle: deployed
        """ensure --kind feature --slug x against a file:// hub (separate bare repo), a main checkout with a
        local-only feature/x and a main behind the hub: origin is the hub, an object is hardlinked, the line
        is new, base_commit is the hub's main tip and refs/remotes/origin/feature/x does not exist.
        Must implement: clone str(repo_root), re-point origin at the hub, fetch --prune origin from the hub.
        WRONG VERSIONS caught: cloning the hub (no hardlinks over a URL); cloning the main checkout without
        pruning (origin/feature/x leaks in); fetching origin/main from the stale main checkout."""
        tmp = Path(tempfile.mkdtemp(prefix="bo4300a1cs_")).resolve()
        self.addCleanup(shutil.rmtree, str(tmp), True)
        fx = make_project(tmp / "world")
        project, hub = fx["project"], fx["hub"]
        hub_url = hub.resolve().as_uri()  # file:// -- git ignores --local for a URL
        git(["remote", "set-url", "origin", hub_url], project)
        git(["checkout", "-q", "-b", "feature/x"], project)
        (project / "LOCAL_ONLY.txt").write_text("local only\n", encoding="utf-8")
        git(["add", "-A"], project)
        git(["commit", "-q", "-m", "local-only work"], project)
        git(["checkout", "-q", "main"], project)

        elsewhere = Path(tempfile.mkdtemp(prefix="bo4300a1cs_adv_")).resolve()  # not a sibling of the project
        self.addCleanup(shutil.rmtree, str(elsewhere), True)
        advancer = elsewhere / "adv"
        git(["clone", "-q", str(hub), str(advancer)], elsewhere)
        (advancer / "ADVANCED.txt").write_text("hub moved on\n", encoding="utf-8")
        git(["add", "-A"], advancer)
        git(["commit", "-q", "-m", "hub moved on"], advancer)
        git(["push", "-q", "origin", "main"], advancer)
        hub_tip = git(["rev-parse", "main"], hub)
        self.assertNotEqual(git(["rev-parse", "main"], project), hub_tip, "precondition: local main is behind")

        res = maker(["ensure", "--kind", "feature", "--slug", "x"], project)
        ans = res["answer"]
        self.assertEqual((ans.get("status"), res["exit_code"]), ("ok", 0), f"{ans} stderr={res['stderr'][-800:]!r}")
        ws = Path(ans["workspace_path"])
        self.assertEqual(git(["config", "--get", "remote.origin.url"], ws), hub_url)
        self.assertTrue(_has_hardlinked_object(ws), "no object file has st_nlink > 1: not a hardlinked local clone")
        self.assertEqual(ans.get("line_of_work"), "new", ans)
        self.assertEqual(ans.get("base_commit"), hub_tip, ans)
        self.assertEqual(git(["for-each-ref", "refs/remotes/origin/feature/x"], ws), "",
                         "the main checkout's local-only branch leaked in as a hub line")
        self.assertEqual(git(["rev-parse", "refs/remotes/origin/main"], ws), hub_tip,
                         "control: the hub's own main must be the remote-tracking main")


def _project_on_hub_url(tmp: Path) -> dict:
    """make_project with origin re-pointed at the hub's file:// URL (git ignores --local for a URL)."""
    fx = make_project(tmp / "world")
    git(["remote", "set-url", "origin", fx["hub"].resolve().as_uri()], fx["project"])
    return fx


class TestCloneOfMainCheckoutContract(unittest.TestCase):
    def _tmp(self) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="bo4300a1cc_")).resolve()
        self.addCleanup(shutil.rmtree, str(tmp), True)
        return tmp

    def test_h1_main_checkout_on_pushed_branch_resumes_with_only_that_local_branch(self):
        # covers: BO-4300a-1
        # angle: discrimination
        """Main checkout ON feature/x, which is also pushed to the hub: ensure answers ok / 'resumed',
        the workspace is on feature/x at the hub's tip, holds no other local branch and no main-checkout-only tag.
        Must implement: after cloning the main checkout, drop the clone's local branches/tags before checkout.
        WRONG VERSIONS caught: checkout -b onto the clone's pre-existing feature/x (GIT_FAILED at checkout);
        leaving main (or the tag localtag) in the clone."""
        fx = _project_on_hub_url(self._tmp())
        project, hub = fx["project"], fx["hub"]
        git(["checkout", "-q", "-b", "feature/x"], project)
        (project / "X.txt").write_text("x\n", encoding="utf-8")
        git(["add", "-A"], project)
        git(["commit", "-q", "-m", "x work"], project)
        git(["push", "-q", "origin", "feature/x"], project)
        git(["tag", "localtag"], project)
        hub_tip = git(["rev-parse", "feature/x"], hub)

        res = maker(["ensure", "--kind", "feature", "--slug", "x"], project)
        ans = res["answer"]
        self.assertEqual((ans.get("status"), res["exit_code"]), ("ok", 0), f"{ans} stderr={res['stderr'][-800:]!r}")
        self.assertEqual(ans.get("line_of_work"), "resumed", ans)
        ws = Path(ans["workspace_path"])
        self.assertEqual(git(["rev-parse", "--abbrev-ref", "HEAD"], ws), "feature/x")
        self.assertEqual(git(["rev-parse", "HEAD"], ws), hub_tip)
        self.assertEqual(git(["for-each-ref", "--format=%(refname)", "refs/heads"], ws), "refs/heads/feature/x")
        self.assertEqual(git(["tag", "--list"], ws), "", "a tag that exists only in the main checkout leaked in")

    def test_m1_unreachable_hub_with_allow_stale_base_reports_failed_fetch_and_no_origin_main(self):
        # covers: BO-4300a-1
        # angle: failure
        """Hub unreachable after the main checkout exists: with --allow-stale-base the answer is ok, fetch
        'failed', origin_main_commit null and base_matches_origin_main false; without it FETCH_FAILED with a
        step and no git text.
        WRONG VERSION caught: keeping the main checkout's local main as origin/main (origin_main_commit set,
        base_matches_origin_main trivially true)."""
        fx = _project_on_hub_url(self._tmp())
        project = fx["project"]
        git(["remote", "set-url", "origin", (fx["hub"].parent / "missing-hub.git").resolve().as_uri()], project)

        res = maker(["ensure", "--kind", "feature", "--slug", "stale", "--allow-stale-base"], project)
        ans = res["answer"]
        self.assertEqual((ans.get("status"), res["exit_code"]), ("ok", 0), f"{ans} stderr={res['stderr'][-800:]!r}")
        self.assertEqual(ans.get("fetch"), "failed", ans)
        self.assertIn("origin_main_commit", ans)
        self.assertIsNone(ans["origin_main_commit"], ans)
        self.assertIs(ans.get("base_matches_origin_main"), False, ans)

        refused = maker(["ensure", "--kind", "feature", "--slug", "strict"], project)["answer"]
        self.assertEqual(refused.get("code"), "FETCH_FAILED", refused)
        self.assertTrue(refused.get("step"), refused)
        self.assertNotIn("fatal", json.dumps(refused).lower(), refused)

    def test_m2_ok_answer_carries_bootstrap_failure_excerpt_as_none(self):
        # covers: BO-4300c-2
        # angle: criterion
        """An ok ensure answer has bootstrap.failure_excerpt present and None (BO-4300c-2: str|null)."""
        fx = _project_on_hub_url(self._tmp())
        ans = maker(["ensure", "--kind", "feature", "--slug", "m2"], fx["project"])["answer"]
        self.assertEqual(ans.get("status"), "ok", ans)
        boot = ans.get("bootstrap")
        self.assertIsInstance(boot, dict, ans)
        self.assertIn("failure_excerpt", boot)
        self.assertIsNone(boot["failure_excerpt"], boot)

    def test_workspace_inherits_no_alternates_from_main_checkout(self):
        # covers: BO-4300a-1
        # angle: discrimination
        """The main checkout borrows objects from a separate repo (objects/info/alternates); the created
        workspace must be self-contained: no objects/info/alternates.
        WRONG VERSION caught: a plain clone of the main checkout, which copies the alternates file."""
        tmp = self._tmp()
        fx = _project_on_hub_url(tmp)
        donor = tmp / "donor"
        git(["clone", "-q", str(fx["hub"]), str(donor)], tmp)
        shared = tmp / "shared-main"
        git(["clone", "-q", "--shared", str(donor), str(shared)], tmp)
        git(["remote", "set-url", "origin", fx["hub"].resolve().as_uri()], shared)
        self.assertTrue((shared / ".git" / "objects" / "info" / "alternates").is_file(), "precondition")

        ans = maker(["ensure", "--kind", "feature", "--slug", "alt"], shared)["answer"]
        self.assertEqual(ans.get("status"), "ok", ans)
        ws = Path(ans["workspace_path"])
        self.assertFalse((ws / ".git" / "objects" / "info" / "alternates").exists(), "alternates leaked into workspace")
        git(["rev-parse", "--verify", "HEAD^{commit}"], ws)  # the workspace still resolves its own history


if __name__ == "__main__":
    unittest.main()
