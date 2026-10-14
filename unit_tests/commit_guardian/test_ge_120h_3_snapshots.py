"""
MODULE: unit_tests/commit_guardian/test_ge_120h_3_snapshots.py
COVERS: GE-120h-3 -- three review defects in the before/after snapshot logic
    of check_folder_density.py and the no-subject accounting of
    check_sql_complexity.py. Every test drives the check through the
    registered ``run_hook.py`` entry point against a REAL ``git init``
    scratch repository; no check function is ever imported or called.

    H-1 (rename/delete accounting): AFTER must be HEAD tree minus staged
        deletions and rename sources, plus staged additions and rename
        destinations. Tests 1 and 2 are RED against the current
        ``HEAD tree U staged-new-paths`` computation.
    M-1 (locale): detecting "no HEAD yet" by matching English git stderr
        crashes under a localised git. No German git catalogue is installed
        on the authoring machine (``locale -a`` offers only C/POSIX and
        /usr/share/locale/de has no git.mo), so forcing LANGUAGE=de alone
        can never go red. The test therefore SIMULATES the localised
        message deterministically: a PATH-shadowing ``git`` wrapper answers
        ``ls-tree`` with the German text and delegates everything else to
        the real git.
    M-2 (unreadable .sql): a non-UTF-8 .sql file must not be reported as
        ``nothing_to_inspect``.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_120h_3_fixture as fx  # noqa: E402

_LIMIT = 15


def _write_files(folder: Path, count: int, prefix: str = "f") -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (folder / f"{prefix}{i}.txt").write_text(f"content {i}\n", encoding="utf-8")


class _ScratchRepoCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = fx.fresh_repo_dir("ge120h3_snap_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        fx.init_repo(self.root)


class TestFolderDensityRenameAndDeleteAccounting(_ScratchRepoCase):
    def test_ge120h3_rename_within_at_limit_folder_is_accepted(self):
        # covers: GE-120h-3
        # angle: boundary
        """15 committed files; one is renamed in place. The folder stays at
        15, so the commit must be accepted. RED today: the rename source is
        still counted, so AFTER reads 16."""
        _write_files(self.root / "dense", _LIMIT)
        fx.commit_all(self.root, "establish at-limit dir")

        fx.git(["mv", "dense/f0.txt", "dense/renamed0.txt"], self.root)

        result = fx.run_via_hook(fx.FOLDER_DENSITY, self.root)
        combined = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, msg=f"Rename keeps count at 15. Got: {combined!r}")
        self.assertNotIn("FOLDER TOO DENSE", combined, msg=combined)

    def test_ge120h3_delete_plus_add_net_zero_is_accepted(self):
        # covers: GE-120h-3
        # angle: boundary
        """15 committed files; one deleted and one added (net 15). Must be
        accepted. RED today: the staged deletion is never subtracted."""
        _write_files(self.root / "dense", _LIMIT)
        fx.commit_all(self.root, "establish at-limit dir")

        fx.git(["rm", "-q", "dense/f0.txt"], self.root)
        (self.root / "dense" / "added.txt").write_text("new\n", encoding="utf-8")
        fx.stage_all(self.root)

        result = fx.run_via_hook(fx.FOLDER_DENSITY, self.root)
        combined = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, msg=f"Net count stays 15. Got: {combined!r}")
        self.assertNotIn("FOLDER TOO DENSE", combined, msg=combined)

    def test_ge120h3_rename_out_of_over_limit_folder_into_at_limit_folder_is_refused(self):
        # covers: GE-120h-3
        # angle: discrimination
        """Source folder already over the limit (16); destination at 15.
        Moving one file across pushes the DESTINATION to 16 because of this
        commit -> refused, and the source must not be reported as a
        violation. Guards against a fix that credits only the destination or
        only the source."""
        _write_files(self.root / "over", _LIMIT + 1)
        _write_files(self.root / "dest", _LIMIT, prefix="d")
        fx.commit_all(self.root, "establish over and at-limit dirs")

        fx.git(["mv", "over/f0.txt", "dest/moved0.txt"], self.root)

        result = fx.run_via_hook(fx.FOLDER_DENSITY, self.root)
        combined = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, msg=f"dest crosses 15->16. Got: {combined!r}")
        self.assertIn("FOLDER TOO DENSE: dest/", combined, msg=combined)
        self.assertNotIn("FOLDER TOO DENSE: over/", combined, msg=combined)

    def test_ge120h3_one_new_file_into_at_limit_folder_is_still_refused(self):
        # covers: GE-120h-3
        # angle: failure
        """Control: 15 committed + 1 newly staged file is still refused, so
        the snapshot fix cannot have been over-corrected into accepting
        genuine additions."""
        _write_files(self.root / "dense", _LIMIT)
        fx.commit_all(self.root, "establish at-limit dir")
        (self.root / "dense" / "extra.txt").write_text("extra\n", encoding="utf-8")
        fx.stage_all(self.root)

        result = fx.run_via_hook(fx.FOLDER_DENSITY, self.root)
        combined = result.stdout + result.stderr
        self.assertNotEqual(0, result.returncode, msg=combined)
        self.assertIn("FOLDER TOO DENSE", combined, msg=combined)


class TestFolderDensityRootCommitIsLocaleIndependent(_ScratchRepoCase):
    def test_ge120h3_root_commit_survives_a_localised_git_message(self):
        # covers: GE-120h-3
        # angle: failure
        """A repository with no commits yet: ``git ls-tree -r HEAD`` fails
        with a LOCALISED message. A PATH-shadowing git wrapper emits the
        German text (a real German catalogue is not installed here, so the
        locale env vars alone cannot reproduce it) and passes every other
        subcommand to the real git. The check must still treat this as an
        empty BEFORE snapshot, not crash. RED today: the English substring
        match misses, the CalledProcessError is re-raised."""
        real_git = shutil.which("git")
        self.assertIsNotNone(real_git)
        shim_dir = fx.fresh_repo_dir("ge120h3_gitshim_")
        self.addCleanup(shutil.rmtree, shim_dir, ignore_errors=True)
        shim = shim_dir / "git"
        shim.write_text(
            "#!/bin/sh\n"
            'for a in "$@"; do\n'
            '  if [ "$a" = "ls-tree" ]; then\n'
            "    echo \"fatal: Kein gültiger Objektname: 'HEAD'.\" >&2\n"
            "    exit 128\n"
            "  fi\n"
            "done\n"
            f'exec "{real_git}" "$@"\n',
            encoding="utf-8",
        )
        shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        _write_files(self.root / "sub", 3)
        fx.stage_all(self.root)

        env = {
            **os.environ,
            "PATH": f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            "LANGUAGE": "de",
            "LC_ALL": "de_DE.UTF-8",
            "LANG": "de_DE.UTF-8",
        }
        result = subprocess.run(
            [fx._PYTHON, str(fx.RUN_HOOK), str(fx.FOLDER_DENSITY)],
            cwd=str(self.root),
            capture_output=True,
            text=True,
            timeout=fx._SUBPROCESS_TIMEOUT_SECONDS,
            env=env,
        )
        combined = result.stdout + result.stderr
        self.assertNotIn("Traceback", combined, msg=combined)
        self.assertEqual(0, result.returncode, msg=f"Root commit, 3 files. Got: {combined!r}")


class TestSqlComplexityUnreadableFileIsNotNothingToInspect(_ScratchRepoCase):
    def test_ge120h3_non_utf8_sql_file_is_not_reported_as_nothing_to_inspect(self):
        # covers: GE-120h-3
        # angle: failure
        """A staged .sql file that is not valid UTF-8 is a real subject the
        check could not read. It must not claim ``nothing_to_inspect`` and
        must name the file. RED today: ``except Exception: continue``
        swallows the decode error uncounted."""
        (self.root / "bad.sql").write_bytes(b"SELECT 1;\xff\xfe\n")
        fx.stage_all(self.root)

        result = fx.run_via_hook(fx.SQL_COMPLEXITY, self.root)
        combined = result.stdout + result.stderr
        self.assertNotIn("nothing_to_inspect", combined, msg=combined)
        self.assertIn("bad.sql", combined, msg=f"The unreadable file must be named. Got: {combined!r}")


class TestSqlComplexityStagedThenRemovedFromWorktree(_ScratchRepoCase):
    def test_ge120h3_staged_sql_removed_from_worktree_is_not_nothing_to_inspect(self):
        # covers: GE-120h-3
        # angle: failure
        """pr-reviewer M-1. A .sql file is ``git add``-ed and then removed with
        os.remove (NOT ``git rm``): the index still holds the content the
        commit would carry. The check must not claim ``nothing_to_inspect``
        and must name the file. RED today: every FileNotFoundError is treated
        as a staged deletion."""
        target = self.root / "gone.sql"
        target.write_text("SELECT 1;\n", encoding="utf-8")
        fx.git(["add", "gone.sql"], self.root)
        os.remove(target)

        result = fx.run_via_hook(fx.SQL_COMPLEXITY, self.root)
        combined = result.stdout + result.stderr
        self.assertNotIn("RESULT: nothing_to_inspect", combined, msg=combined)
        self.assertIn("gone.sql", combined, msg=f"The file must be named. Got: {combined!r}")

    def test_ge120h3_real_staged_deletion_still_reports_nothing_to_inspect(self):
        # covers: GE-120h-3
        # angle: boundary
        """Control: ``git rm`` of a committed .sql, nothing else staged, is a
        genuine deletion with no subject -> nothing_to_inspect."""
        (self.root / "old.sql").write_text("SELECT 1;\n", encoding="utf-8")
        fx.commit_all(self.root, "add sql")
        fx.git(["rm", "-q", "old.sql"], self.root)

        result = fx.run_via_hook(fx.SQL_COMPLEXITY, self.root)
        combined = result.stdout + result.stderr
        self.assertEqual(0, result.returncode, msg=combined)
        self.assertIn("RESULT: nothing_to_inspect", combined, msg=combined)


if __name__ == "__main__":
    unittest.main()
