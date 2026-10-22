"""
MODULE: unit_tests/build_orchestration/test_bo_4300c_1_path_keyed_canaries.py
AC: BO-4300c-1-ii / BO-4300c-1 -- stage canaries are keyed on reserved paths / a reserved message
line, never on file contents (coordinator decision 2026-10-09: the old content token blocked every
commit that merely mentioned it). Real git repos in temp dirs; the REAL precommit_canary.py and the
REAL commit_guardian.json declaration are run as the hooks.

DECISION HISTORY
====================================================================
- 2026-10-09 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05]: Created for the
  path-keyed canary round (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05).
====================================================================
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "templates" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import worktree_canaries as wc  # noqa: E402

CG = SCRIPTS / "commit_guardian"
OLD_TOKEN = "LEAFCUTTER_STAGE_CANARY_KNOWN_BAD"
MARK = "PRECOMMIT_CANARY_REJECTED"
DECL = json.loads((CG / "commit_guardian.json").read_text(encoding="utf-8"))["stage_canaries"]


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False)


def _write(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.tmp = Path(self._td.name)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        _git(self.repo, "init", "-q", "-b", "feature")
        for k, v in (("user.name", "t"), ("user.email", "t@example.invalid"), ("commit.gpgsign", "false")):
            _git(self.repo, "config", k, v)
        _write(self.repo, "a.txt", "x\n")
        _git(self.repo, "add", "a.txt")
        assert _git(self.repo, "commit", "-q", "-m", "init").returncode == 0
        d = self.tmp / "hookscripts"
        d.mkdir()
        shutil.copy(CG / "precommit_canary.py", d / "precommit_canary.py")
        shutil.copy(CG / "commit_guardian.json", d / "commit_guardian.json")
        script, py = (d / "precommit_canary.py").as_posix(), Path(sys.executable).as_posix()
        self.hook("pre-commit", f'"{py}" "{script}" --stage pre-commit\n')
        self.hook("commit-msg", f'"{py}" "{script}" --stage commit-msg "$1"\n')
        self.hook("post-merge", f'"{py}" "{script}" --stage post-merge\n')

    def hook(self, stage, body):
        h = self.repo / ".git" / "hooks" / stage
        h.write_text("#!/bin/sh\n" + body, encoding="utf-8", newline="\n")
        h.chmod(0o755)

    def head(self):
        return _git(self.repo, "rev-parse", "HEAD").stdout.strip()

    def commit(self, *files, msg="work"):
        for f in files:
            _git(self.repo, "add", "--", f)
        return _git(self.repo, "commit", "-q", "-m", msg)

    def merge_side(self, files: dict[str, str]):
        """Merge a side branch adding *files*; return the post-merge hook run."""
        _git(self.repo, "checkout", "-q", "-b", "side")
        for rel, text in files.items():
            _write(self.repo, rel, text)
            _git(self.repo, "add", "--", rel)
        self.assertEqual(_git(self.repo, "commit", "-q", "--no-verify", "-m", "side").returncode, 0)
        _git(self.repo, "checkout", "-q", "feature")
        _write(self.repo, "b.txt", "b\n")
        self.assertEqual(self.commit("b.txt", msg="b").returncode, 0)
        m = _git(self.repo, "merge", "-q", "--no-ff", "--no-verify", "-m", "m", "side")
        self.assertEqual(m.returncode, 0, m.stdout + m.stderr)
        return _git(self.repo, "hook", "run", "post-merge", "--", "0")


class TestDeclarationIsPathKeyed(unittest.TestCase):
    def test_declaration_has_no_content_token(self):
        # covers: BO-4300c-1-ii
        # angle: real_artifact
        """Neither commit_guardian.json nor precommit_canary.py may carry a scannable content token."""
        for name in ("commit_guardian.json", "precommit_canary.py"):
            text = (CG / name).read_text(encoding="utf-8")
            self.assertNotIn(OLD_TOKEN, text, name)
        self.assertNotIn("_SKIP", (CG / "precommit_canary.py").read_text(encoding="utf-8"))

    def test_pre_commit_and_post_merge_declare_distinct_reserved_paths(self):
        # covers: BO-4300c-1-ii
        # angle: criterion
        """pre-commit and post-merge each declare a reserved path; commit-msg a reserved first line."""
        pre, post, msg = DECL["pre-commit"], DECL["post-merge"], DECL["commit-msg"]
        self.assertTrue(isinstance(pre.get("path"), str) and pre["path"])
        self.assertTrue(isinstance(post.get("path"), str) and post["path"])
        self.assertNotEqual(pre["path"], post["path"])
        self.assertTrue(isinstance(msg.get("message"), str) and msg["message"])
        self.assertNotIn("\n", msg["message"])
        self.assertNotIn("content", pre)
        self.assertNotIn("content", post)


class TestPreCommitPathKeyed(Base):
    def test_reserved_path_staged_is_rejected_with_marker(self):
        # covers: BO-4300c-1-ii
        # angle: criterion
        _write(self.repo, DECL["pre-commit"]["path"], "anything\n")
        r = self.commit(DECL["pre-commit"]["path"])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(MARK, r.stdout + r.stderr)

    def test_old_token_in_contents_and_quoted_path_are_not_rejected(self):
        # covers: BO-4300c-1-ii
        # angle: discrimination
        """Wrong version: content scanning. A file holding the old token and quoting the reserved path passes."""
        _write(self.repo, "notes.md", f"{OLD_TOKEN}\nreserved: {DECL['pre-commit']['path']}\n")
        _write(self.repo, ".leafcutter_stage_canary_bad.txt", OLD_TOKEN + "\n")
        r = self.commit("notes.md", ".leafcutter_stage_canary_bad.txt")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_commit_guardian_json_copy_is_not_rejected(self):
        # covers: BO-4300c-1-ii
        # angle: real_artifact
        """Committing the real declaration file (it names the reserved paths) is not rejected."""
        shutil.copy(CG / "commit_guardian.json", self.repo / "commit_guardian.json")
        r = self.commit("commit_guardian.json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class TestCommitMsgPathKeyed(Base):
    def test_exact_reserved_first_line_is_rejected_with_marker(self):
        # covers: BO-4300c-1-ii
        # angle: criterion
        _write(self.repo, "c.txt", "c\n")
        r = self.commit("c.txt", msg=DECL["commit-msg"]["message"])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn(MARK, r.stdout + r.stderr)

    def test_messages_quoting_token_or_reserved_line_are_not_rejected(self):
        # covers: BO-4300c-1-ii
        # angle: discrimination
        """Wrong versions: substring / any-line match. Quoting the line, or the old token, passes."""
        reserved = DECL["commit-msg"]["message"]
        msgs = (f"chore: {OLD_TOKEN}", f"subject\n\n{reserved}", f"{reserved} extra", f"x {reserved}")
        for i, msg in enumerate(msgs):
            with self.subTest(msg=msg):
                _write(self.repo, f"c{i}.txt", "c\n")
                r = self.commit(f"c{i}.txt", msg=msg)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class TestPostMergePathKeyed(Base):
    def test_merge_adding_reserved_path_reports_failure_with_marker(self):
        # covers: BO-4300c-1-ii
        # angle: criterion
        ran = self.merge_side({DECL["post-merge"]["path"]: "anything\n"})
        self.assertNotEqual(ran.returncode, 0)
        self.assertIn(MARK, ran.stdout + ran.stderr)

    def test_merge_with_token_text_or_quoted_path_is_not_failing(self):
        # covers: BO-4300c-1-ii
        # angle: discrimination
        ran = self.merge_side({"doc.md": f"{OLD_TOKEN}\n{DECL['post-merge']['path']}\n",
                               ".leafcutter_stage_canary_bad_merge.txt": OLD_TOKEN + "\n"})
        self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)
        self.assertNotIn(MARK, ran.stdout + ran.stderr)


class TestReadinessProbeUsesTheDeclaredInputs(Base):
    """The maker's probes, run against the real canary hook and the real declaration, show it fire."""

    def test_probes_show_every_stage_fired_and_leave_nothing(self):
        # covers: BO-4300c-1
        # angle: seam
        head = self.head()
        self.assertTrue(wc._pre_commit_fires(self.repo, DECL["pre-commit"], head))
        self.assertTrue(wc._commit_msg_fires(self.repo, DECL["commit-msg"], head))
        self.assertTrue(wc._post_merge_fires(self.repo, DECL["post-merge"], head, "feature"))
        self.assertEqual(self.head(), head)
        self.assertEqual(_git(self.repo, "status", "--porcelain").stdout.strip(), "")
        refs = _git(self.repo, "for-each-ref", "--format=%(refname)").stdout.split()
        self.assertEqual(refs, ["refs/heads/feature"])


if __name__ == "__main__":
    unittest.main()
