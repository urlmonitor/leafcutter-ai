"""
MODULE: test_bo_4300a_1_regressions
GOAL: Regression tests for the four defects pr-reviewer found in the BO-4300a-1
    workspace maker (H-1 canary destroys work, M-1 non-hook failure read as a
    hook rejection, M-2 failed ensure strands a workspace, low nit unreachable
    hub under --allow-stale-base succeeds silently).
PROOF SHAPE: like test_bo_4300a_1.py, the DEPLOYED maker (shared reference
    layout, read-only) runs as a separate process against a real bare hub and a
    real shared project in a temp directory. Every test owns its own world, so
    the workspaces these tests damage on purpose never touch another test.
    No mock of git, no import of the maker, no grep of its source.
"""
from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path

import pytest

from scripts.suite_performance._shared_layout_producer import get_or_produce_shared_layout

from ._bo4300a1_helpers import STUB_BUILD, build_world, git, git_ok, run_maker

CANARY_NAME = ".leafcutter-canary-known-bad.py"
FAILING_BUILD = (
    "import sys\n"
    "print('stub build: forced failure', file=sys.stderr)\n"
    "sys.exit(4)\n"
)
HUB_WORDS = ("unreachable", "could not", "stale", "unavailable")


def _scripts_dir() -> Path:
    return Path(get_or_produce_shared_layout()) / ".leafcutter" / "scripts"


def _children(landing: Path) -> list[str]:
    """Sorted names of the workspace folders in the landing place (empty if absent)."""
    if not landing.is_dir():
        return []
    return sorted(c.name for c in landing.iterdir() if c.is_dir())


def _warns_about_hub(stderr: str) -> bool:
    text = stderr.lower()
    return "hub" in text and any(word in text for word in HUB_WORDS)


@pytest.mark.shared_layout_reader
class TestBo4300a1Regressions(unittest.TestCase):
    def _world(self):
        world = build_world(_scripts_dir())
        self.addCleanup(world.holder.cleanup)
        return world

    def _ensure(self, world, kind, slug, *extra):
        argv = ["ensure", "--kind", kind, "--slug", slug,
                "--repo-root", str(world.project), *extra]
        return run_maker(world, argv)

    def _ready(self, world, kind, slug):
        done, payload = self._ensure(world, kind, slug)
        self.assertEqual(payload.get("status"), "ok", (payload, done.stderr[-1500:]))
        return Path(payload["workspace_path"])

    def _verify(self, world, ws):
        return run_maker(world, ["verify", "--path", str(ws), "--repo-root", str(world.project)])

    def _publish_build(self, world, content, tag):
        """Push a new scripts/build.py to the hub's main through a real clone."""
        seed = world.base / f"seed_publish_{tag}"
        git_ok(world.base, world.env, "clone", str(world.hub), str(seed))
        (seed / "scripts" / "build.py").write_text(content, encoding="utf-8")
        git_ok(seed, world.env, "add", "-A")
        git_ok(seed, world.env, "commit", "-m", f"build stub {tag}")
        git_ok(seed, world.env, "push", "origin", "HEAD:main")

    def _snapshot(self, world, ws):
        env = world.env
        names = ("README.md", ".gitignore", "staged.txt", "untracked.txt")
        return {
            "head": git_ok(ws, env, "rev-parse", "HEAD"),
            "branch": git_ok(ws, env, "symbolic-ref", "--short", "HEAD"),
            "status": git_ok(ws, env, "status", "--porcelain"),
            "diff": git_ok(ws, env, "diff"),
            "cached": git_ok(ws, env, "diff", "--cached"),
            "reflog": git_ok(ws, env, "reflog"),
            "files": {n: (ws / n).read_bytes() for n in names if (ws / n).exists()},
        }

    def _assert_clean_and_unmoved(self, world, ws, head, label):
        """The canary undid every trace of itself."""
        self.assertEqual(git_ok(ws, world.env, "rev-parse", "HEAD"), head, label)
        self.assertEqual(git_ok(ws, world.env, "status", "--porcelain"), "", label)
        self.assertEqual(git_ok(ws, world.env, "diff", "--cached"), "", label)
        self.assertFalse((ws / CANARY_NAME).exists(), label)
        self.assertEqual(git_ok(ws, world.env, "ls-files", CANARY_NAME), "", label)

    def test_ensure_and_verify_leave_uncommitted_and_staged_edits_unchanged(self):
        # covers: BO-4300a-1
        # angle: discrimination
        world = self._world()
        ws = self._ready(world, "feature", "bo4300a1-user-work")
        # control: on a clean workspace the canary runs and is proven, so a
        # False below is caused by the dirty tree and nothing else.
        done, clean = self._verify(world, ws)
        self.assertEqual(clean.get("status"), "ok", (clean, done.stderr[-1500:]))
        self.assertIs(clean["checks"]["hooks_canary_rejected"], True)
        self.assertIs(clean["checks"]["tree_clean"], True)
        # the user's work: one unstaged edit, one staged new file, one staged
        # edit to a tracked file, one untracked file
        (ws / "README.md").write_text("edited by the user, not staged\n", encoding="utf-8")
        (ws / "staged.txt").write_text("new file the user staged\n", encoding="utf-8")
        git_ok(ws, world.env, "add", "staged.txt")
        with (ws / ".gitignore").open("a", encoding="utf-8") as handle:
            handle.write("user-ignored-thing/\n")
        git_ok(ws, world.env, "add", ".gitignore")
        (ws / "untracked.txt").write_text("never added\n", encoding="utf-8")
        before = self._snapshot(world, ws)
        self.assertEqual(len(before["files"]), 4)
        for label, run in (
            ("verify", lambda: self._verify(world, ws)),
            ("ensure", lambda: self._ensure(world, "feature", "bo4300a1-user-work")),
        ):
            done, payload = run()
            checks = payload.get("checks")
            self.assertIsInstance(checks, dict, (label, payload))
            self.assertIs(checks["tree_clean"], False, label)
            self.assertIs(checks["hooks_canary_rejected"], False, f"{label}: proof claimed on dirty tree")
            self.assertNotEqual(payload.get("status"), "ok", label)
            after = self._snapshot(world, ws)
            for key in before:
                self.assertEqual(after[key], before[key], f"{label}: {key} changed")

    def test_canary_is_not_proven_when_the_workspace_has_no_hook(self):
        # covers: BO-4300a-1
        # angle: discrimination
        world = self._world()
        ws = self._ready(world, "feature", "bo4300a1-no-hook")
        head = git_ok(ws, world.env, "rev-parse", "HEAD")
        hook = ws / ".git" / "hooks" / "pre-commit"
        saved = world.base / "pre-commit.saved"
        shutil.copy2(hook, saved)
        hook.unlink()
        done, payload = self._verify(world, ws)
        checks = payload.get("checks")
        self.assertIsInstance(checks, dict, payload)
        self.assertIs(checks["hooks_pre_commit_fired"], False)
        self.assertIs(checks["hooks_canary_rejected"], False,
                      "a commit that nothing rejected was read as proof")
        self.assertNotEqual(payload.get("status"), "ok")
        self._assert_clean_and_unmoved(world, ws, head, "no hook")
        # control: with the very same hook restored the canary IS proven
        shutil.copy2(saved, hook)
        done, restored = self._verify(world, ws)
        self.assertEqual(restored.get("status"), "ok", (restored, done.stderr[-1500:]))
        self.assertIs(restored["checks"]["hooks_canary_rejected"], True)
        self._assert_clean_and_unmoved(world, ws, head, "hook restored")

    def test_canary_is_not_proven_when_a_commit_fails_for_a_non_hook_reason(self):
        # covers: BO-4300a-1
        # angle: discrimination
        world = self._world()
        ws = self._ready(world, "feature", "bo4300a1-non-hook")
        head = git_ok(ws, world.env, "rev-parse", "HEAD")
        # Signing is demanded and the signer always fails: EVERY commit in this
        # workspace fails, with or without hooks, while the hook is installed.
        failing_signer = shutil.which("false") or sys.executable
        git_ok(ws, world.env, "config", "commit.gpgsign", "true")
        git_ok(ws, world.env, "config", "gpg.program", failing_signer)
        probe = git(ws, world.env, "commit", "--allow-empty", "--no-verify", "-m", "probe")
        self.assertNotEqual(probe.returncode, 0, "fixture broken: commits must fail here")
        done, payload = self._verify(world, ws)
        checks = payload.get("checks")
        self.assertIsInstance(checks, dict, payload)
        self.assertIs(checks["hooks_pre_commit_fired"], True)
        self.assertIs(checks["hooks_canary_rejected"], False,
                      "a failure that was not the hook was read as a hook rejection")
        self.assertNotEqual(payload.get("status"), "ok")
        self._assert_clean_and_unmoved(world, ws, head, "signing broken")
        # control: remove only the cause, the same hook now proves itself
        git_ok(ws, world.env, "config", "--unset", "commit.gpgsign")
        git_ok(ws, world.env, "config", "--unset", "gpg.program")
        done, healed = self._verify(world, ws)
        self.assertEqual(healed.get("status"), "ok", (healed, done.stderr[-1500:]))
        self.assertIs(healed["checks"]["hooks_canary_rejected"], True)
        self._assert_clean_and_unmoved(world, ws, head, "signing healed")

    def test_failed_ensure_leaves_no_workspace_and_a_retry_is_not_blocked(self):
        # covers: BO-4300a-1
        # angle: failure
        world = self._world()
        landing = world.base / "worktrees"
        sibling = self._ready(world, "ac", "bo4300a1-sibling")
        self.assertEqual(_children(landing), [sibling.name])
        self._publish_build(world, FAILING_BUILD, "failing")
        for attempt in ("first", "second"):
            done, payload = self._ensure(world, "feature", "bo4300a1-doomed")
            self.assertNotEqual(done.returncode, 0, attempt)
            self.assertEqual(payload.get("status"), "error", (attempt, payload))
            self.assertEqual(payload.get("code"), "BUILD_FAILED", (attempt, payload))
            self.assertNotEqual(payload.get("code"), "WORKSPACE_INCOMPLETE", attempt)
            self.assertEqual(_children(landing), [sibling.name],
                             f"{attempt}: a half-made workspace was left behind")
            named = payload.get("workspace_path")
            if named:
                self.assertFalse(Path(named).exists(), f"{attempt}: answer names a leftover")
        # the cleanup removed only the failed workspace, not its neighbour
        self.assertTrue((sibling / ".git").is_dir())
        # control: once the build works, the same work gets its workspace
        self._publish_build(world, STUB_BUILD, "working")
        retry = self._ready(world, "feature", "bo4300a1-doomed")
        self.assertEqual(_children(landing), sorted([sibling.name, retry.name]))
        done, marker = run_maker(
            world, ["locate", "--path", str(retry), "--repo-root", str(world.project)])
        self.assertEqual(marker.get("state"), "ready")

    def test_allow_stale_base_with_an_unreachable_hub_warns_instead_of_succeeding_silently(self):
        # covers: BO-4300a-1
        # angle: failure
        world = self._world()
        landing = world.base / "worktrees"
        project_main = git_ok(world.project, world.env, "rev-parse", "main")
        gone = world.base / "hub.git.unreachable"
        world.hub.rename(gone)
        try:
            done, refused = self._ensure(world, "ac", "bo4300a1-no-flag")
            self.assertNotEqual(done.returncode, 0)
            self.assertEqual(refused.get("code"), "FETCH_FAILED", refused)
            self.assertEqual(_children(landing), [], "refused ensure left a workspace")
            done, allowed = self._ensure(
                world, "ac", "bo4300a1-allow-stale", "--allow-stale-base")
            self.assertEqual(allowed.get("status"), "ok", (allowed, done.stderr[-1500:]))
            self.assertEqual(allowed["base_commit"], project_main)
            self.assertNotEqual(allowed["base_commit"], world.tip)
            self.assertIsNot(allowed["checks"].get("base_is_fresh"), True,
                             "a stale base was reported as fresh")
            self.assertTrue(_warns_about_hub(done.stderr),
                            f"no warning about the unreachable hub: {done.stderr!r}")
        finally:
            gone.rename(world.hub)
        # control: with the hub reachable the same flag is silent and the base is S
        done, fresh = self._ensure(world, "ac", "bo4300a1-fresh", "--allow-stale-base")
        self.assertEqual(fresh.get("status"), "ok", (fresh, done.stderr[-1500:]))
        self.assertEqual(fresh["base_commit"], world.tip)
        self.assertIs(fresh["checks"]["base_is_fresh"], True)
        self.assertFalse(_warns_about_hub(done.stderr), done.stderr)


if __name__ == "__main__":
    unittest.main()
