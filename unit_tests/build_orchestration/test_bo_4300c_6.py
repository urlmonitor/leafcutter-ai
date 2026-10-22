"""
MODULE: unit_tests/build_orchestration/test_bo_4300c_6.py
AC: BO-4300c-6 (a protection canary never mistakes a git failure for a pass, and never blocks
    ordinary work)
GOAL: Prove, on the DEPLOYED canary run as its own process in real temporary repos (no git mock),
    that a git failure fails closed with a git report and no rejection marker, that a missing
    ORIG_HEAD alone means "nothing merged", and that non-UTF-8 input never blocks ordinary work.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._bo_4300c_6_fixtures import (
    MARKER, clean_env, commit_msg_shim, declared, git, head_commit_bytes, init_repo, merge_branch,
    non_repo_env, parse_report, run_canary, stage_bytes_paths, write,
)
from unit_tests.build_orchestration._workspace_maker_builders import _run_git


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory(prefix="bo4300c6-")
        self.addCleanup(self._td.cleanup)
        self.tmp = Path(self._td.name)

    def assert_fails_closed(self, done, env, repo, needle):
        self.assertNotEqual(done.returncode, 0, done.out + done.err)
        self.assertNotIn(MARKER, done.out + done.err)
        args, rc, _text = parse_report(done.err)
        self.assertNotEqual(rc, 0)
        again = git(args, repo, env)
        self.assertEqual(again.returncode, rc, "re-running the named command must reproduce the status")
        self.assertIn(needle, done.err)
        self.assertIn(again.stderr.strip().splitlines()[0], done.err, "git's own first stderr line must be reported")


class TestCommitTimeGitFailure(Base):
    def _arms(self):
        reserved = declared("pre-commit")["path"]
        for label, rel in (("reserved", reserved), ("ordinary", "ordinary.txt")):
            repo = init_repo(self.tmp, f"p-{label}")
            write(repo, rel)
            _run_git(["add", rel], repo)
            yield label, repo

    def test_commit_time_canary_fails_closed_on_corrupt_index_with_git_report(self):
        # covers: BO-4300c-6
        # angle: failure
        """AC-1/2/3: a truncated .git/index makes git fail; the canary exits non-zero, no marker,
        and reports the git command, its status and git's own text."""
        for label, repo in self._arms():
            with self.subTest(arm=label):
                (repo / ".git" / "index").write_bytes(b"DIRC\x00\x00\x00\x02\x00\x00")
                done = run_canary(["--stage", "pre-commit"], repo)
                self.assert_fails_closed(done, clean_env(), repo, "index file smaller than expected")

    def test_commit_time_canary_fails_closed_when_git_dir_is_not_a_repository(self):
        # covers: BO-4300c-6
        # angle: failure
        """AC-1/2/3: GIT_DIR naming a non-repository folder is a git failure, never an empty list."""
        for label, repo in self._arms():
            with self.subTest(arm=label):
                env = non_repo_env(self.tmp)
                done = run_canary(["--stage", "pre-commit"], repo, env)
                self.assert_fails_closed(done, env, repo, "not a git repository")


class TestPostMerge(Base):
    def test_after_merge_canary_passes_when_nothing_was_merged(self):
        # covers: BO-4300c-6
        # angle: boundary
        """AC-4: no ORIG_HEAD (fresh clone / fresh repo) means nothing to check: exit 0, quiet."""
        source = init_repo(self.tmp, "source")
        clone = self.tmp / "clone"
        self.assertEqual(git(["clone", "-q", str(source), str(clone)], self.tmp).returncode, 0)
        for label, repo in (("clone", clone), ("fresh", init_repo(self.tmp, "fresh"))):
            with self.subTest(arm=label):
                self.assertEqual(git(["rev-parse", "-q", "--verify", "ORIG_HEAD"], repo).returncode, 1)
                done = run_canary(["--stage", "post-merge"], repo)
                self.assertEqual(done.returncode, 0, done.out + done.err)
                self.assertNotIn(MARKER, done.out + done.err)
                self.assertNotIn("exited", done.err)

    def test_after_merge_canary_fails_closed_when_git_dir_is_not_a_repository(self):
        # covers: BO-4300c-6
        # angle: failure
        """AC-5/6: after a real merge, a non-repository GIT_DIR is a failure, never 'nothing merged'."""
        repo = init_repo(self.tmp)
        merge_branch(repo, "feat", "feat.txt")
        env = non_repo_env(self.tmp)
        done = run_canary(["--stage", "post-merge"], repo, env)
        self.assert_fails_closed(done, env, repo, "not a git repository")

    def test_after_merge_canary_fails_closed_on_dangling_orig_head(self):
        # covers: BO-4300c-6
        # angle: discrimination
        """AC-5/6: ORIG_HEAD present but naming no object is a broken repository, not 'nothing
        merged' (an absence probe that peels ORIG_HEAD^{commit} would exit 1 and pass quietly)."""
        repo = init_repo(self.tmp)
        merge_branch(repo, "feat", "feat.txt")
        (repo / ".git" / "ORIG_HEAD").write_text("deadbeef" * 5 + "\n", encoding="ascii")
        done = run_canary(["--stage", "post-merge"], repo)
        self.assertNotEqual(done.returncode, 0, done.out + done.err)
        self.assertNotIn(MARKER, done.out + done.err)
        _args, rc, _text = parse_report(done.err)
        self.assertNotEqual(rc, 0)
        self.assertIn("bad object", done.err)


class TestCommitMsg(Base):
    def test_commit_msg_canary_lets_non_utf8_and_empty_messages_through(self):
        # covers: BO-4300c-6
        # angle: boundary
        """AC-7: a cp1252 message and an empty message both commit through the real shim."""
        repo = init_repo(self.tmp)
        commit_msg_shim(repo)
        msg = self.tmp / "cp1252.txt"
        msg.write_bytes(b"Gr\xf6\xdfe\n")
        for label, cmd in (
            ("cp1252", ["commit", "-q", "--allow-empty", "-F", str(msg)]),
            ("empty", ["commit", "-q", "--allow-empty", "--allow-empty-message", "-m", ""]),
        ):
            with self.subTest(arm=label):
                before = git(["rev-parse", "HEAD"], repo).stdout
                done = git(cmd, repo)
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                self.assertNotEqual(git(["rev-parse", "HEAD"], repo).stdout, before)
                self.assertNotIn(MARKER, done.stdout + done.stderr)
                self.assertNotIn("Traceback", done.stdout + done.stderr)
            if label == "cp1252":
                head = head_commit_bytes(repo)
                self.assertTrue(b"Gr\xf6\xdfe" in head or b"Gr\xc3\xb6\xc3\x9fe" in head)  # git may recode to UTF-8

    def test_commit_msg_canary_rejects_reserved_first_line_with_lf_or_crlf(self):
        # covers: BO-4300c-6
        # angle: discrimination
        """AC-8: exact first-line byte comparison: LF, CRLF and non-UTF-8 body rejected; near
        misses pass; a real commit of the reserved message is rejected and HEAD is unchanged."""
        reserved = declared("commit-msg")["message"].encode("utf-8")
        cases = {
            "lf": (reserved + b"\n", 1),
            "crlf": (reserved + b"\r\n" + b"body\r\n", 1),
            "non_utf8_body": (reserved + b"\n\n" + b"Gr\xf6\xdfe\n", 1),
            "suffix_near_miss": (reserved + b" x\r\n", 0),
            "second_line_near_miss": (b"subject\r\n" + reserved + b"\r\n", 0),
        }
        repo = init_repo(self.tmp)
        for name, (body, want) in cases.items():
            with self.subTest(case=name):
                path = self.tmp / f"msg_{name}"
                path.write_bytes(body)
                done = run_canary(["--stage", "commit-msg", str(path)], repo)
                self.assertEqual(done.returncode, want, done.out + done.err)
                self.assertEqual(MARKER in done.out, bool(want), done.out + done.err)
                self.assertNotIn("Traceback", done.err)
        commit_msg_shim(repo)
        head = git(["rev-parse", "HEAD"], repo).stdout
        path = self.tmp / "real_lf"
        path.write_bytes(reserved + b"\n")
        done = git(["commit", "-q", "--allow-empty", "-F", str(path)], repo)
        self.assertNotEqual(done.returncode, 0)
        self.assertEqual(git(["rev-parse", "HEAD"], repo).stdout, head)


class TestNonAsciiPaths(Base):
    def test_ordinary_non_ascii_and_non_utf8_paths_never_crash_the_canary(self):
        # covers: BO-4300c-6
        # angle: boundary
        """Ordinary staged paths with byte 0x81 / non-UTF-8 never crash; reserved still rejected."""
        repo = init_repo(self.tmp)
        stage_bytes_paths(repo, [b"\xc5\x81\xc3\xb3d\xc5\xba.txt", b"Gr\xf6\xdfe.txt"])
        done = run_canary(["--stage", "pre-commit"], repo)
        self.assertEqual(done.returncode, 0, done.out + done.err)
        self.assertNotIn(MARKER, done.out + done.err)
        self.assertNotIn("Traceback", done.err)
        stage_bytes_paths(repo, [declared("pre-commit")["path"].encode()])
        done = run_canary(["--stage", "pre-commit"], repo)
        self.assertEqual(done.returncode, 1, done.out + done.err)
        self.assertIn(MARKER, done.out)
        repo2 = init_repo(self.tmp, "p2")
        merge_branch(repo2, "lodz", "Łódź.txt")
        done = run_canary(["--stage", "post-merge"], repo2)
        self.assertEqual(done.returncode, 0, done.out + done.err)
        self.assertNotIn(MARKER, done.out + done.err)
        self.assertNotIn("Traceback", done.err)


class TestReachability(Base):
    def test_bo_4300c_6_reachable_from_entry_point(self):
        # covers: BO-4300c-6
        # angle: reachability
        """Entry point: `python precommit_canary.py --stage pre-commit` (CLI via subprocess, as the
        registered hook runs it). A git failure surfaces as a consumed non-zero exit + git report."""
        repo = init_repo(self.tmp)
        write(repo, "ordinary.txt")
        _run_git(["add", "ordinary.txt"], repo)
        ok = run_canary(["--stage", "pre-commit"], repo)
        self.assertEqual(ok.returncode, 0, ok.out + ok.err)
        (repo / ".git" / "index").write_bytes(b"DIRC\x00\x00")
        done = run_canary(["--stage", "pre-commit"], repo)
        self.assertEqual(done.returncode, 1)
        self.assertNotIn(MARKER, done.out + done.err)
        self.assertEqual(len(parse_report(done.err)), 3)


if __name__ == "__main__":
    unittest.main()
