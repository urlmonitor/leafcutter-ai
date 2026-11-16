"""
MODULE: test_tq100a_2
AC: TQ-100a-2 -- a linked-worktree test sandbox never writes the host repository's
    shared commit identity; it takes its identity from the inherited environment.
GOAL: Real-git tests of the sandbox pattern: real host, real linked worktree.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _tq100a_2_support as S  # noqa: E402

_FIXTURE_FILES = ("test_ge_120e_1.py", "test_ge_120e_1_i.py")


def _fixture_env_overrides(filename: str) -> dict[str, str]:
    """The overrides dict the real fixture file merges into every git call."""
    path = S.REPO_ROOT / "unit_tests" / "portability" / filename
    spec = importlib.util.spec_from_file_location("_tq100a_2_probe_" + path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.pop(0)
    return dict(mod._GIT_ENV_OVERRIDES)


class TestTq100a2(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.env = S.scrubbed_env(self.root / "home")

    def _host_and_sandbox(self, identity=True):
        host = S.make_host(self.root, self.env, identity=identity)
        return host, S.add_worktree(host, self.root, self.env)

    def test_tq100a_2_host_identity_is_unchanged_after_a_linked_worktree_fixture_runs(self):
        # covers: TQ-100a-2
        # angle: real_artifact
        """Use the real fixture files' own env overrides for a real linked-worktree
        commit and read the host's shared config back."""
        host, wt = self._host_and_sandbox()
        for fname in _FIXTURE_FILES:
            overrides = _fixture_env_overrides(fname)
            for var in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
                        "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
                self.assertIn(var, overrides, f"{fname} must supply {var} (all four)")
            (wt / f"{fname}.txt").write_text("x\n", encoding="utf-8")
            S.must_git(["add", "."], wt, self.env)
            res = S.git(["commit", "-q", "-m", fname], wt, dict(self.env, **overrides))
            self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(S.read_key(host, "user.name", self.env), S.HUMAN_NAME)
        self.assertEqual(S.read_key(host, "user.email", self.env), S.HUMAN_EMAIL)

    def test_tq100a_2_sandbox_commits_carry_the_fixture_identity_as_author_and_committer(self):
        # covers: TQ-100a-2
        # angle: criterion
        host, wt = self._host_and_sandbox()
        res = S.sandbox_commit(wt, self.env)
        self.assertEqual(res.returncode, 0, res.stderr)
        fmt = "--format=%an <%ae>|%cn <%ce>"
        want = f"{S.FIXTURE_NAME} <{S.FIXTURE_EMAIL}>"
        self.assertEqual(S.must_git(["log", "-1", fmt], wt, self.env).strip(), f"{want}|{want}")
        # A commit made in the host afterwards is still attributed to the human.
        (host / "after.txt").write_text("a\n", encoding="utf-8")
        S.must_git(["add", "after.txt"], host, self.env)
        S.must_git(["commit", "-q", "-m", "after"], host, self.env)
        human = f"{S.HUMAN_NAME} <{S.HUMAN_EMAIL}>"
        self.assertEqual(S.must_git(["log", "-1", fmt], host, self.env).strip(), f"{human}|{human}")

    def test_tq100a_2_commits_succeed_with_no_configured_identity_anywhere(self):
        # covers: TQ-100a-2
        # angle: boundary
        host, wt = self._host_and_sandbox(identity=False)
        self.assertIsNone(S.read_key(host, "user.name", self.env))
        self.assertIsNone(S.read_key(host, "user.email", self.env))
        res = S.sandbox_commit(wt, self.env)
        self.assertEqual(res.returncode, 0, res.stderr)
        want = f"{S.FIXTURE_NAME} <{S.FIXTURE_EMAIL}>"
        got = S.must_git(["log", "-1", "--format=%an <%ae>|%cn <%ce>"], wt, self.env).strip()
        self.assertEqual(got, f"{want}|{want}")
        self.assertIsNone(S.read_key(host, "user.email", self.env))

    def test_tq100a_2_worktree_scoped_configuration_being_enabled_changes_nothing(self):
        # covers: TQ-100a-2
        # angle: failure
        host, wt = self._host_and_sandbox()
        S.must_git(["config", "extensions.worktreeConfig", "true"], host, self.env)
        res = S.sandbox_commit(wt, self.env)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(S.read_key(host, "user.name", self.env), S.HUMAN_NAME)
        self.assertEqual(S.read_key(host, "user.email", self.env), S.HUMAN_EMAIL)
        # The named mutation (an unqualified write) lands on the host even with the
        # extension on: this is what rules the extension out as a mitigation.
        S.must_git(["config", "user.email", S.FIXTURE_EMAIL], wt, self.env)
        self.assertEqual(S.read_key(host, "user.email", self.env), S.FIXTURE_EMAIL)
        # The shipped fixtures must not contain that mutation at any site.
        for fname in _FIXTURE_FILES:
            src = (S.REPO_ROOT / "unit_tests" / "portability" / fname).read_text(encoding="utf-8")
            self.assertIsNone(
                re.search(r"""["']config["']\s*,\s*["']user\.(name|email)["']""", src),
                f"{fname} still writes an identity into shared configuration",
            )


if __name__ == "__main__":
    unittest.main()
