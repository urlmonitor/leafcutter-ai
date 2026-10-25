"""
MODULE: unit_tests/build_orchestration/test_bo_4300a_1_checkout_race.py
AC: BO-4300a-1 IT3 / BO-4300c-1 -- a new workspace's line of work starts exactly where its files are, or
    the maker refuses.
TICKET: tickets/00_inbox/epics/EPIC-WorkspaceMakerHardening/
    11_TICKET-20261025-new-workspace-head-matches-its-files.md

The race: ``checkout -B <branch> origin/main`` resolves the start point by NAME twice (tree, then branch). A
smudge filter, configured through the isolated git environment (GIT_CONFIG_COUNT), rewrites
``refs/remotes/origin/main`` while the tree is being written, which splits HEAD from the index. The filter only
fires when origin/main still holds the hub tip, and logs each rewrite so a green run cannot be vacuous.

Runs the DEPLOYED maker (shared locator) against fixture projects; never spawns scripts/build.py itself and never
touches the real repository.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._workspace_maker_fixtures import make_project, run_maker  # fixtures first: builders cycle
from unit_tests.build_orchestration._workspace_maker_fixtures import _bounded_maker_env, deployed_maker_path  # noqa: I001
from unit_tests.build_orchestration._bo_4300a_1_ii_fixtures import git, push_hub_line  # noqa: I001

# The only untracked paths the stub install legitimately writes (make_project has no .gitignore for them).
_INSTALL_UNTRACKED = ("?? .leafcutter/", "?? INSTALLED_MARKER.txt")
_NEEDS_SH = unittest.skipUnless(shutil.which("sh"), "fixture hooks and filters need a POSIX sh")

_SMUDGE = """#!/bin/sh
cur=$(git rev-parse -q --verify refs/remotes/origin/main 2>/dev/null)
if [ "$cur" = "{frm}" ]; then
  git update-ref refs/remotes/origin/main {to} && echo rewrote >> "{log}"
fi
cat
"""
_POST_CHECKOUT = """#!/bin/sh
branch=$(git symbolic-ref --short -q HEAD)
gitdir=$(git rev-parse --git-dir)
if [ "$branch" = "feature/dirty" ] && [ ! -e "$gitdir/dirtied" ]; then
  echo "dirt" >> README.md
  touch "$gitdir/dirtied"
fi
exit 0
"""
_REF_TRANSACTION = """#!/bin/sh
cat > /dev/null
[ "$1" = "prepared" ] || exit 0
{{ echo "== record"; git remote -v; }} >> "{log}"
exit 0
"""


def _scratch(case: unittest.TestCase, prefix: str) -> Path:
    path = Path(tempfile.mkdtemp(prefix=prefix)).resolve()
    case.addCleanup(shutil.rmtree, str(path), True)
    return path


def _git_config_env(pairs: list[tuple[str, str]]) -> dict[str, str]:
    """Extra git config for every git process of the maker run (git >= 2.31 environment config)."""
    env = {"GIT_CONFIG_COUNT": str(len(pairs))}
    for i, (key, value) in enumerate(pairs):
        env[f"GIT_CONFIG_KEY_{i}"] = key
        env[f"GIT_CONFIG_VALUE_{i}"] = value
    return env


def _hub_ahead(case: unittest.TestCase, fx: dict[str, Path], with_later_branch: bool) -> dict[str, str]:
    """Advance the hub: main gets the filter attribute and a .dat file (H1); optionally branch ``later`` is H1 + one more (H2).

    The main checkout's local main stays at the seed commit (S0), behind the hub.
    """
    project, hub = fx["project"], fx["hub"]
    s0 = git(["rev-parse", "main"], project)
    elsewhere = _scratch(case, "bo4300a1race_adv_")
    adv = elsewhere / "adv"
    git(["clone", "-q", str(hub), str(adv)], elsewhere)
    (adv / ".gitattributes").write_text("*.dat filter=race\n", encoding="utf-8", newline="\n")
    (adv / "b.dat").write_text("payload\n", encoding="utf-8", newline="\n")
    git(["add", "-A"], adv)
    git(["commit", "-q", "-m", "hub: filtered payload"], adv)
    git(["push", "-q", "origin", "main"], adv)
    shas = {"s0": s0, "h1": git(["rev-parse", "main"], hub), "h2": ""}
    if with_later_branch:
        (adv / "c.txt").write_text("newer\n", encoding="utf-8", newline="\n")
        git(["add", "-A"], adv)
        git(["commit", "-q", "-m", "hub: newer than main"], adv)
        git(["push", "-q", "origin", "HEAD:refs/heads/later"], adv)
        shas["h2"] = git(["rev-parse", "HEAD"], adv)
    return shas


def _race_env(case: unittest.TestCase, frm: str, to: str) -> tuple[dict[str, str], Path]:
    """Environment that makes every smudge of a ``*.dat`` file move origin/main from *frm* to *to*."""
    home = _scratch(case, "bo4300a1race_filter_")
    log = home / "fired.log"
    script = home / "smudge.sh"
    script.write_text(_SMUDGE.format(frm=frm, to=to, log=log), encoding="utf-8", newline="\n")
    script.chmod(0o755)
    return _git_config_env([("filter.race.smudge", str(script))]), log


def _template_with_hook(case: unittest.TestCase, hook_name: str, body: str) -> Path:
    template = _scratch(case, "bo4300a1race_tpl_")
    hooks = template / "hooks"
    hooks.mkdir()
    hook = hooks / hook_name
    hook.write_text(body, encoding="utf-8", newline="\n")
    hook.chmod(0o755)
    return template


def _assert_no_split(case: unittest.TestCase, res: dict, expected_base: str, fired_log: Path) -> None:
    """Either an ok workspace whose HEAD is the recorded base with nothing staged, or a refusal naming a step."""
    case.assertTrue(fired_log.is_file() and fired_log.read_text(encoding="utf-8").strip(),
                    "precondition: the smudge filter never rewrote origin/main, so the race was not provoked")
    ans = res["answer"]
    if ans.get("status") != "ok":
        case.assertIn(ans.get("status"), ("refused", "error"), ans)
        case.assertTrue(ans.get("step"), f"a refusal must name the step: {ans}")
        case.assertNotEqual(res["exit_code"], 0, ans)
        return
    ws = Path(ans["workspace_path"])
    case.assertEqual(git(["rev-parse", "HEAD"], ws), ans.get("base_commit"), f"HEAD is not the recorded base: {ans}")
    case.assertEqual(ans.get("base_commit"), expected_base, f"base is not the hub tip fetched: {ans}")
    leftovers = [ln for ln in git(["status", "--porcelain"], ws).splitlines() if ln not in _INSTALL_UNTRACKED]
    case.assertEqual(leftovers, [], "an ok workspace must have a clean git status (bar the install's own files)")
    case.assertEqual(git(["diff", "--cached", "--name-only"], ws), "", "an ok workspace must have nothing staged")


def _origin_urls_at(log: Path, main_checkout: Path) -> list[str]:
    """Every recorded ``origin`` remote line whose URL is the main checkout's path."""
    main = os.path.normcase(str(main_checkout.resolve()))
    hits = []
    for line in log.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "origin" and os.path.normcase(str(Path(parts[1]).resolve())) == main:
            hits.append(line)
    return hits


def _creating_workspace(case: unittest.TestCase, local_ahead: bool) -> tuple[dict[str, Path], Path, str, str]:
    """A half-made ('creating', nothing checked out) workspace whose LOCAL feature/x already exists.

    The hub carries feature/x (one commit). The maker is stopped right after the clone (its abort seam),
    then the workspace gets a local feature/x at the hub SHA, or one extra commit ahead of it.
    Returns ``(fixture, workspace, hub_sha, local_sha)``.
    """
    fx = make_project(_scratch(case, "bo4300a1race_") / "world")
    hub_sha = push_hub_line(fx["project"], "feature/x")[0]
    env = _bounded_maker_env({"LEAFCUTTER_WORKSPACE_ABORT_AT": "after_clone"})
    cmd = [sys.executable, str(deployed_maker_path()), "ensure", "--kind", "feature", "--slug", "x"]
    subprocess.run(cmd, cwd=str(fx["project"]), env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL, check=False)
    ws = fx["landing_place"] / "feature" / "x"
    case.assertTrue((ws / ".git").is_dir(), "precondition: the clone exists")
    case.assertEqual(git(["ls-files"], ws), "", "precondition: nothing is checked out (a 'creating' workspace)")
    git(["fetch", "-q", str(fx["hub"]), "feature/x"], ws)
    local_sha = hub_sha
    if local_ahead:
        tree = git(["rev-parse", f"{hub_sha}^{{tree}}"], ws)
        local_sha = git(["commit-tree", tree, "-p", hub_sha, "-m", "local work the hub lacks"], ws)
    git(["update-ref", "refs/heads/feature/x", local_sha], ws)
    return fx, ws, hub_sha, local_sha


@_NEEDS_SH
class TestCheckoutRace(unittest.TestCase):
    def test_origin_main_moved_back_during_checkout_never_answers_ok_split(self):
        # covers: BO-4300a-1
        # covers: BO-4300c-1
        # angle: discrimination
        """The hub is ahead of the main checkout's main; origin/main is rewritten to the OLDER seed commit while
        the tree is written. Must implement: resolve the base to one SHA right after the hub fetch and build
        the line from that SHA (or refuse naming a step).
        WRONG VERSIONS caught: checkout by ref name (HEAD at the seed, index at the hub tip, staged reverts);
        answering ok after a set-aside/put-back that hides the gap."""
        tmp = _scratch(self, "bo4300a1race_")
        fx = make_project(tmp / "world")
        shas = _hub_ahead(self, fx, with_later_branch=False)
        self.assertNotEqual(shas["s0"], shas["h1"], "precondition: hub ahead of the main checkout")
        env, fired = _race_env(self, shas["h1"], shas["s0"])
        res = run_maker(["ensure", "--kind", "feature", "--slug", "back"], cwd=fx["project"], env=env)
        _assert_no_split(self, res, shas["h1"], fired)

    def test_origin_main_moved_forward_during_checkout_never_answers_ok_split(self):
        # covers: BO-4300a-1
        # covers: BO-4300c-1
        # angle: discrimination
        """origin/main is rewritten to a NEWER hub commit (branch ``later``, fetched with the rest) while the
        tree is written. Must implement: the line is built from the SHA recorded at the fetch, so no staged
        reverts of the newer commit's files can appear.
        WRONG VERSIONS caught: checkout by ref name (HEAD at the newer commit, index at the old tip);
        base_is_fresh compared with the re-read, moved ref."""
        tmp = _scratch(self, "bo4300a1race_")
        fx = make_project(tmp / "world")
        shas = _hub_ahead(self, fx, with_later_branch=True)
        env, fired = _race_env(self, shas["h1"], shas["h2"])
        res = run_maker(["ensure", "--kind", "feature", "--slug", "fwd"], cwd=fx["project"], env=env)
        _assert_no_split(self, res, shas["h1"], fired)


@_NEEDS_SH
class TestCreatedWorkspaceIsNeverPreserved(unittest.TestCase):
    def test_created_workspace_with_dirty_tree_is_refused_not_preserved(self):
        # covers: BO-4300a-1
        # covers: BO-4300c-1
        # angle: failure
        """A post-checkout hook (init.templateDir, so it reaches the clone) dirties README.md ONCE (one-shot) when the line
        feature/dirty is checked out. Must implement: on a created workspace skip the set-aside, refuse the
        dirty tree and discard the new clone, with no rescue folder and no re-staged file.
        WRONG VERSIONS caught: set-aside then put-back and answer ok; refusing but leaving the clone behind."""
        tmp = _scratch(self, "bo4300a1race_")
        fx = make_project(tmp / "world")
        template = _template_with_hook(self, "post-checkout", _POST_CHECKOUT)
        env = _git_config_env([("init.templateDir", str(template))])
        res = run_maker(["ensure", "--kind", "feature", "--slug", "dirty"], cwd=fx["project"], env=env)
        ans = res["answer"]
        self.assertIn(ans.get("status"), ("refused", "error"), f"a dirty new workspace must be refused: {ans}")
        self.assertTrue(ans.get("step"), f"a refusal must name the step: {ans}")
        self.assertNotIn("workspace_path", ans, "a refusal carries no workspace location")
        landing = fx["landing_place"]
        left = [p for p in landing.rglob("*") if p.name in ("README.md", "rescue")] if landing.exists() else []
        self.assertEqual(left, [], f"the new clone (or its rescue folder) was left behind: {left}")
        self.assertEqual(git(["status", "--porcelain"], fx["project"]), "", "the main checkout must stay untouched")


@_NEEDS_SH
class TestCloneNeverExposesMainCheckout(unittest.TestCase):
    def test_clone_never_exposes_main_checkout_as_origin(self):
        # covers: BO-4300a-1
        # angle: reachability
        """A reference-transaction hook (init.templateDir) records ``git remote -v`` at every ref update of the
        clone: the clone, the fetch, the checkout. Must implement: clone with a temporary remote name, add
        origin at the hub, drop the temporary remote.
        WRONG VERSIONS caught: cloning as origin and re-pointing it only after the clone (the window an outside
        bare fetch hits); keeping the main checkout as a second remote named origin."""
        tmp = _scratch(self, "bo4300a1race_")
        fx = make_project(tmp / "world")
        log = _scratch(self, "bo4300a1race_log_") / "remotes.log"
        template = _template_with_hook(self, "reference-transaction", _REF_TRANSACTION.format(log=log))
        env = _git_config_env([("init.templateDir", str(template))])
        res = run_maker(["ensure", "--kind", "feature", "--slug", "clone"], cwd=fx["project"], env=env)
        self.assertEqual(res["answer"].get("status"), "ok", f"{res['answer']} stderr={res['stderr'][-600:]!r}")
        self.assertTrue(log.is_file(), "precondition: the hook never ran, so nothing was observed")
        exposed = _origin_urls_at(log, fx["project"])
        self.assertEqual(exposed, [], f"a remote named origin pointed at the main checkout: {exposed}")


@_NEEDS_SH
class TestResumeNeverResetsLocalWork(unittest.TestCase):
    def test_resume_refuses_when_local_line_holds_commits_the_hub_lacks(self):
        # covers: BO-4300a-1
        # covers: BO-4300c-1
        # angle: discrimination
        """A 'creating' workspace has local feature/x one commit AHEAD of the hub's feature/x; ensure resumes it.
        Must implement: refuse with a step instead of resetting the branch with -B.
        WRONG VERSIONS caught: ``checkout --no-track -B <branch> <hub sha>`` over an existing local branch
        (the local commit becomes unreachable except by reflog)."""
        fx, ws, hub_sha, local_sha = _creating_workspace(self, local_ahead=True)
        self.assertNotEqual(local_sha, hub_sha, "precondition: the local line is ahead")
        res = run_maker(["ensure", "--kind", "feature", "--slug", "x"], cwd=fx["project"])
        ans = res["answer"]
        self.assertIn(ans.get("status"), ("refused", "error"), f"resuming over unsent local commits must refuse: {ans}")
        self.assertTrue(ans.get("step"), f"a refusal must name the step: {ans}")
        self.assertNotEqual(res["exit_code"], 0, ans)
        self.assertEqual(git(["rev-parse", "refs/heads/feature/x"], ws), local_sha, "the local branch was reset")
        self.assertEqual(git(["merge-base", "--is-ancestor", local_sha, "refs/heads/feature/x"], ws), "")

    def test_resume_control_local_line_equal_to_hub_resumes_ok(self):
        # covers: BO-4300a-1
        # angle: criterion
        """Control: local feature/x equals the hub's feature/x, so the resume proceeds and answers ok at that SHA.
        Passes for a different reason than the negative test refuses: nothing is ahead."""
        fx, ws, hub_sha, local_sha = _creating_workspace(self, local_ahead=False)
        self.assertEqual(local_sha, hub_sha)
        res = run_maker(["ensure", "--kind", "feature", "--slug", "x"], cwd=fx["project"])
        ans = res["answer"]
        self.assertEqual(ans.get("status"), "ok", f"{ans} stderr={res['stderr'][-600:]!r}")
        self.assertEqual(ans.get("line_of_work"), "resumed", ans)
        self.assertEqual(git(["rev-parse", "HEAD"], ws), hub_sha)


if __name__ == "__main__":
    unittest.main()
