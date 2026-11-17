"""
MODULE: unit_tests/commit_guardian/test_presence_only_merge_aware.py
GOAL: check_presence_only_assertions.py must judge only what a merge itself
    adds. A presence-only assertion that exists in the working tree only
    because the merged-in branch added it was already judged on that branch,
    and must not be refused on the merge commit. An assertion the merge
    resolution adds (in neither parent), and an assertion in a plain commit,
    are still refused.
BUSINESS CONTEXT: Found 2026-10-17 merging origin/main into a long-lived
    branch: the hook read a bare `git diff --cached` (against HEAD only), so
    every test main had added since the branch point read as authored by the
    merge. Same misattribution fixed for check-folder-density and
    check-file-size. Shared merge-scoping source: _authored_change.py.
EXERCISE STRATEGY: no git mocks. Each test builds a real temporary git repo
    with isolated git config (empty GIT_CONFIG_GLOBAL / GIT_CONFIG_SYSTEM),
    creates real branches, merges with --no-commit so MERGE_HEAD is set, and
    runs the REAL hook script as a subprocess with cwd = that repo. The only
    injected input is the guard config (HOOK_TEST_CONFIG, the convention from
    test_bp_1100b_5.py); the diff is NOT injected, so the hook reads git
    itself. The config file is written via json.dump.

RED BASELINE: test 1 fails by assertion today (the hook sees the carried-in
    assertion as added by the merge and exits 1). Tests 2 and 3 are guards
    that pass today by design and must stay green.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_SCRIPT = (
    _REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_presence_only_assertions.py"
)

_SOURCE_PATH = "templates/scripts/commit_guardian/sample_target.py"
_TEST_PATH = "unit_tests/commit_guardian/test_added_presence_only.py"
_GUARD_CONFIG = {
    "enabled": True,
    "scanned_source_globs": ["templates/scripts/commit_guardian/*.py"],
    "waiver_marker": "presence-only",
}
_TIMEOUT = 60

# A test file whose whole "coverage" is a substring grep over a scanned source.
_PRESENCE_ONLY_TEST = (
    "import unittest\n"
    "from pathlib import Path\n"
    "\n"
    "\n"
    "class TestWiring(unittest.TestCase):\n"
    "    def test_helper_is_wired(self):\n"
    f"        content = Path('{_SOURCE_PATH}').read_text()\n"
    # presence-only: fixture text the test plants in its temp repo so the hook has a presence-only assertion to judge
    "        assert 'compute_thing(' in content\n"
)


class _TempRepo:
    """A real throwaway git repo with git config fully isolated."""

    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir()
        empty_cfg = root.parent / "empty.gitconfig"
        empty_cfg.write_text("", encoding="utf-8")
        self.env = os.environ.copy()
        for key in ("HOOK_TEST_DIFF", "HOOK_TEST_CONFIG", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
            self.env.pop(key, None)
        self.env.update(
            GIT_CONFIG_GLOBAL=str(empty_cfg),
            GIT_CONFIG_SYSTEM=str(empty_cfg),
            GIT_AUTHOR_NAME="t",
            GIT_AUTHOR_EMAIL="t@example.com",
            GIT_COMMITTER_NAME="t",
            GIT_COMMITTER_EMAIL="t@example.com",
        )
        self.config_path = root.parent / "guard.json"
        self.config_path.write_text(json.dumps(_GUARD_CONFIG), encoding="utf-8")
        self.git("init", "-q", "-b", "base")

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        result = subprocess.run(
            ["git", *args], cwd=str(self.root), env=self.env,
            capture_output=True, text=True, timeout=_TIMEOUT, check=False,
        )
        if check and result.returncode != 0:
            detail = f"git {args} failed: {result.stderr}"
            raise AssertionError(detail)
        return result

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")

    def commit_file(self, rel: str, text: str, message: str) -> None:
        self.write(rel, text)
        self.git("add", rel)
        self.git("commit", "-q", "-m", message)

    def run_hook(self) -> subprocess.CompletedProcess:
        env = dict(self.env)
        env["HOOK_TEST_CONFIG"] = str(self.config_path)
        return subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)], cwd=str(self.root), env=env,
            capture_output=True, text=True, timeout=_TIMEOUT, check=False,
        )


class TestPresenceOnlyMergeAware(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = _TempRepo(Path(self._tmp.name) / "repo")
        self.repo.commit_file(_SOURCE_PATH, "def compute_thing():\n    return 1\n", "base source")

    def _branch_off_work(self) -> None:
        """Move HEAD to `work` (off base) with one unrelated commit."""
        self.repo.git("checkout", "-q", "-b", "work")
        self.repo.commit_file("docs/work_only.txt", "work branch change\n", "work-only change")

    def _start_merge_of_feature(self) -> None:
        self.repo.git("merge", "--no-commit", "--no-ff", "feature", check=False)
        merge_head = self.repo.git("rev-parse", "-q", "--verify", "MERGE_HEAD", check=False)
        self.assertEqual(merge_head.returncode, 0, "setup: MERGE_HEAD must be set")

    def test_merge_bringing_in_branch_added_presence_only_assertion_passes(self):
        # covers: UNKNOWN
        # angle: criterion
        """A presence-only assertion existing only because the merged-in branch
        added it is not refused on the merge. Today the hook reads the diff
        against HEAD alone, so the carried-in test reads as added by the merge
        and the hook exits 1 (assertion red).
        """
        self.repo.git("checkout", "-q", "-b", "feature")
        self.repo.commit_file(_TEST_PATH, _PRESENCE_ONLY_TEST, "feature adds presence-only test")
        self.repo.git("checkout", "-q", "base")
        self._branch_off_work()
        self._start_merge_of_feature()

        staged = self.repo.git("diff", "--cached", "--name-only").stdout.split()
        self.assertIn(_TEST_PATH, staged, "setup: merge result must contain the carried-in test")
        result = self.repo.run_hook()
        self.assertEqual(
            result.returncode, 0,
            f"carried-in assertion must not be judged on the merge; "
            f"stdout={result.stdout!r} stderr={result.stderr!r}",
        )
        self.assertNotIn("BLOCKED", result.stdout)
        self.assertNotIn(_TEST_PATH, result.stdout)

    def test_merge_resolution_adding_presence_only_assertion_is_refused(self):
        # covers: UNKNOWN
        # angle: failure
        """An assertion in neither parent but in the merge result (added by the
        resolution) is refused. Control: the carried-in change is unrelated
        and clean, so the refusal is caused by the resolution alone.
        """
        self.repo.git("checkout", "-q", "-b", "feature")
        self.repo.commit_file("docs/feature_only.txt", "feature change\n", "feature change")
        self.repo.git("checkout", "-q", "base")
        self._branch_off_work()
        self._start_merge_of_feature()

        clean = self.repo.run_hook()
        self.assertEqual(clean.returncode, 0, f"control: clean merge must pass; {clean.stdout!r}")

        self.repo.write(_TEST_PATH, _PRESENCE_ONLY_TEST)
        self.repo.git("add", _TEST_PATH)
        result = self.repo.run_hook()
        self.assertEqual(result.returncode, 1, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        self.assertIn("BLOCKED", result.stdout)
        self.assertIn(_TEST_PATH, result.stdout)
        # presence-only: asserts the hook's refusal message names the planted fixture's symbol, not that source contains it
        self.assertIn("compute_thing(", result.stdout)

    def test_plain_commit_adding_presence_only_assertion_still_refused(self):
        # covers: UNKNOWN
        # angle: failure
        """With no operation in progress, an added presence-only assertion is
        refused as before. Control: a plain commit of an unrelated file
        passes, so the refusal is caused by the assertion alone.
        """
        self.repo.write("docs/plain.txt", "plain change\n")
        self.repo.git("add", "docs/plain.txt")
        control = self.repo.run_hook()
        self.assertEqual(control.returncode, 0, f"control: {control.stdout!r}")

        self.repo.write(_TEST_PATH, _PRESENCE_ONLY_TEST)
        self.repo.git("add", _TEST_PATH)
        result = self.repo.run_hook()
        self.assertEqual(result.returncode, 1, f"stdout={result.stdout!r} stderr={result.stderr!r}")
        self.assertIn("BLOCKED", result.stdout)
        self.assertIn(_TEST_PATH, result.stdout)
        # presence-only: asserts the hook's refusal message names the planted fixture's symbol, not that source contains it
        self.assertIn("compute_thing(", result.stdout)


if __name__ == "__main__":
    unittest.main()
