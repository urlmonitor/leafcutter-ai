"""
MODULE: unit_tests/commit_guardian/test_folder_density_merge_commit.py
COVERS: TICKET-20261010-FolderDensityMergeCommit (ticket-only work, no AC id;
    tagged ``# covers: UNKNOWN`` per the house style for AC-less tests).

PROBLEM. check_folder_density.py reads its BEFORE snapshot from
    ``git ls-tree -r HEAD`` only. In a merge commit HEAD is the branch's old
    tip, so every folder that crossed the limit on the MERGED-IN branch counts
    as "newly dense in this commit" and the merge is refused.

CONTRACT (ticket Scope 1-2). With MERGE_HEAD present, a folder is pre-existing
    when it is over the limit in HEAD OR in MERGE_HEAD; only a folder the merge
    result itself pushes over the limit is a violation. A normal commit
    (no MERGE_HEAD) is unchanged.

ENTRY POINT. The hook is driven through run_hook.py (``fx.run_via_hook``)
    against a REAL git repository left in a real ``git merge --no-commit``
    state; git runs with cwd set to the repo, never ``git -C``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_120h_3_fixture as fx  # noqa: E402

LIMIT = json.loads(fx.MANIFEST_PATH.read_text(encoding="utf-8"))["folder_density"][
    "max_files_per_folder"
]

_GIT_ENV = {
    **os.environ,
    "COMMIT_AGENT_MODE": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Real git with cwd=root and an isolated config (no -C)."""
    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=60,
        check=check,
        env=_GIT_ENV,
    )


def _write_files(root: Path, folder: str, prefix: str, count: int) -> None:
    d = root / folder
    d.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (d / f"{prefix}{i}.txt").write_text(f"{prefix} {i}\n", encoding="utf-8")


def _commit(root: Path, message: str) -> None:
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", message)


class _RepoCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = fx.fresh_repo_dir("fdens_merge_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        _git(self.root, "init", "-q")
        _git(self.root, "config", "user.email", "t@example.com")
        _git(self.root, "config", "user.name", "fdens merge test")
        _git(self.root, "config", "commit.gpgsign", "false")
        (self.root / "base.txt").write_text("base\n", encoding="utf-8")
        _commit(self.root, "base")
        self.main = _git(self.root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()

    def merge_state(self, a_side, b_side) -> None:
        """Fork 'other' from base; apply b_side there and a_side on main; then
        ``merge --no-commit --no-ff`` other into main, leaving MERGE_HEAD."""
        _git(self.root, "checkout", "-q", "-b", "other")
        b_side()
        _commit(self.root, "other side")
        _git(self.root, "checkout", "-q", self.main)
        a_side()
        _commit(self.root, "main side")
        _git(self.root, "merge", "--no-commit", "--no-ff", "other")
        self.assertTrue((self.root / ".git" / "MERGE_HEAD").exists())

    def hook(self) -> tuple[int, str]:
        # Same entry point as fx.run_via_hook, but decoded as UTF-8: the hook
        # prints emoji and fx's text=True decode dies on cp1252 (Windows).
        r = subprocess.run(
            [sys.executable, str(fx.RUN_HOOK), str(fx.FOLDER_DENSITY)],
            cwd=str(self.root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            env={**_GIT_ENV, "PYTHONIOENCODING": "utf-8"},
        )
        return r.returncode, (r.stdout or "") + (r.stderr or "")


class TestMergeCommit(_RepoCase):
    def test_merge_bringing_in_already_dense_folder_passes(self):
        # covers: UNKNOWN
        # angle: reachability
        """Folder X is over the limit only on MERGE_HEAD's side. The merge
        must pass and must not report X as FOLDER TOO DENSE.

        RED TODAY: BEFORE is read from HEAD only, so X looks newly dense.
        """
        self.merge_state(
            lambda: (self.root / "main_only.txt").write_text("m\n", encoding="utf-8"),
            lambda: _write_files(self.root, "X", "x", LIMIT + 3),
        )
        code, out = self.hook()
        self.assertNotIn("FOLDER TOO DENSE", out, msg=out)
        self.assertEqual(0, code, msg=out)

    def test_merge_dense_only_in_result_is_refused(self):
        # covers: UNKNOWN
        # angle: failure
        """Folder Y is under the limit in the merge base (10), in HEAD (14)
        and in MERGE_HEAD (14), but 18 in the merged result: refused, naming Y.
        """
        def base_y():
            _write_files(self.root, "Y", "base", 10)

        base_y()
        _commit(self.root, "Y base")
        self.merge_state(
            lambda: _write_files(self.root, "Y", "a", 4),
            lambda: _write_files(self.root, "Y", "b", 4),
        )
        self.assertGreater(10 + 4 + 4, LIMIT)
        self.assertLessEqual(10 + 4, LIMIT)
        code, out = self.hook()
        self.assertEqual(1, code, msg=out)
        self.assertIn("FOLDER TOO DENSE", out, msg=out)
        self.assertIn("Y", out, msg=out)


class TestNormalCommitUnchanged(_RepoCase):
    def test_sixteenth_file_in_compliant_folder_is_refused(self):
        # covers: UNKNOWN
        # angle: boundary
        """No MERGE_HEAD: folder at exactly the limit plus one file is refused."""
        _write_files(self.root, "W", "w", LIMIT)
        _commit(self.root, "W at limit")
        _write_files(self.root, "W", "extra", 1)
        _git(self.root, "add", "-A")
        code, out = self.hook()
        self.assertEqual(1, code, msg=out)
        self.assertIn("FOLDER TOO DENSE", out, msg=out)

    def test_adding_to_already_over_limit_folder_only_warns(self):
        # covers: UNKNOWN
        # angle: boundary
        """No MERGE_HEAD: a folder already over the limit in HEAD only warns."""
        _write_files(self.root, "V", "v", LIMIT + 2)
        _commit(self.root, "V already dense")
        _write_files(self.root, "V", "extra", 1)
        _git(self.root, "add", "-A")
        code, out = self.hook()
        self.assertEqual(0, code, msg=out)
        self.assertNotIn("FOLDER TOO DENSE", out, msg=out)
        self.assertIn("PRE-EXISTING", out, msg=out)


class TestExemptionDoesNotLeak(_RepoCase):
    def test_folder_dense_on_unmerged_branch_still_refused_in_normal_commit(self):
        # covers: UNKNOWN
        # angle: discrimination
        """Z is over the limit only on a branch that is never merged. A normal
        commit on main pushing Z over the limit must still be refused; the
        MERGE_HEAD exemption must not consult other branches or leak into a
        non-merge commit. Catches a wrong version that exempts any folder
        dense on ANY other ref.
        """
        _write_files(self.root, "Z", "z", LIMIT - 1)
        _commit(self.root, "Z compliant")
        _git(self.root, "checkout", "-q", "-b", "elsewhere")
        _write_files(self.root, "Z", "e", 8)
        _commit(self.root, "Z dense elsewhere")
        _git(self.root, "checkout", "-q", self.main)
        self.assertFalse((self.root / ".git" / "MERGE_HEAD").exists())
        _write_files(self.root, "Z", "extra", 2)
        _git(self.root, "add", "-A")
        code, out = self.hook()
        self.assertEqual(1, code, msg=out)
        self.assertIn("FOLDER TOO DENSE", out, msg=out)


if __name__ == "__main__":
    unittest.main()
