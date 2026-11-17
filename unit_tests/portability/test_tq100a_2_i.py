"""
MODULE: test_tq100a_2_i
AC: TQ-100a-2-i -- a session-scoped guard compares the host repository's shared
    commit identity before and after the session and fails the run on any change.
GOAL: TDD red-baseline tests. The guard is a pytest plugin that does not exist yet.

CONTRACT ASSUMED (python-coder implements exactly this):
  scripts/suite_performance/pytest_git_identity_guard.py, loadable as
  ``-p scripts.suite_performance.pytest_git_identity_guard``, exposing
    ABSENT                         -- sentinel, a state distinct from "" (empty)
    read_identity(repo_root)       -> dict[key, str | ABSENT] for user.name and
                                      user.email, read from the host repository's
                                      shared config as git resolves it
    compare_identity(before, after, fixture) -> list[str]
        one message per changed key, each naming the fixture, the key, the
        before value and the after value; [] when nothing changed. Compares
        STATES, never strings (ABSENT != "").
  As a registered plugin it snapshots before the first test and compares at
  session end (including after -x), failing the run (non-zero exit) and
  printing the message naming the test whose sandbox made the change.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _tq100a_2_support as S  # noqa: E402

_PLUGIN = "scripts.suite_performance.pytest_git_identity_guard"

_POLLUTER = textwrap.dedent(
    '''\
    import subprocess
    from pathlib import Path

    import unit_tests.build_orchestration._workspace_maker_fixtures  # noqa: F401 -- breaks the builders/fixtures import cycle
    from unit_tests.build_orchestration._workspace_maker_builders import link_checkout

    HOST = Path(__file__).resolve().parent


    def test_polluting_fixture_sandbox(tmp_path):
        wt = tmp_path / "wt"
        link_checkout(HOST, ["--detach", "-q", str(wt)])  # census-exempt add spelling
        subprocess.run(["git", "config", "user.email", "polluted@example.invalid"],
                       cwd=wt, check=True)
    '''
)

_FAILER = "def test_zz_fails_second():\n    assert False\n"
_CLEAN = "def test_clean():\n    assert True\n"


def _guard():
    import importlib

    return importlib.import_module(_PLUGIN)


class TestTq100a2IUnit(unittest.TestCase):
    def test_tq100a_2_i_a_changed_value_fails_and_names_fixture_key_before_and_after(self):
        # covers: TQ-100a-2-i
        # angle: criterion
        g = _guard()
        before = {"user.name": "Real Human", "user.email": "real-human@example.com"}
        after = {"user.name": "Real Human", "user.email": "fixture@example.invalid"}
        findings = g.compare_identity(before, after, "test_some_sandbox")
        self.assertEqual(len(findings), 1)
        msg = findings[0]
        for element in ("test_some_sandbox", "user.email",
                        "real-human@example.com", "fixture@example.invalid"):
            self.assertIn(element, msg)

    def test_tq100a_2_i_an_unchanged_identity_reports_nothing(self):
        # covers: TQ-100a-2-i
        # angle: failure
        g = _guard()
        a = {"user.name": "Real Human", "user.email": "real-human@example.com"}
        b = {"user.email": "real-human@example.com", "user.name": "Real Human"}  # reordered
        self.assertEqual(g.compare_identity(a, b, "f"), [])
        self.assertEqual(g.compare_identity(a, dict(a), "f"), [])

    def test_tq100a_2_i_absent_is_a_distinct_state_from_empty_in_both_directions(self):
        # covers: TQ-100a-2-i
        # angle: boundary
        g = _guard()
        A = g.ABSENT
        self.assertNotEqual(A, "")
        appeared = g.compare_identity({"user.email": A}, {"user.email": "x@example.invalid"}, "f")
        self.assertEqual(len(appeared), 1)
        self.assertIn("x@example.invalid", appeared[0])
        vanished = g.compare_identity({"user.email": "x@example.invalid"}, {"user.email": A}, "f")
        self.assertEqual(len(vanished), 1)
        self.assertEqual(g.compare_identity({"user.email": A}, {"user.email": A}, "f"), [])
        empty_to_absent = g.compare_identity({"user.email": ""}, {"user.email": A}, "f")
        self.assertEqual(len(empty_to_absent), 1)


class TestTq100a2ISession(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.env = S.scrubbed_env(self.root / "home")
        self.host = S.make_host(self.root, self.env)
        (self.host / "pytest.ini").write_text(
            f"[pytest]\naddopts = -p {_PLUGIN} -p no:cacheprovider -p no:randomly\n",
            encoding="utf-8",
        )

    def _run(self, files: dict[str, str], *args: str):
        for name, body in files.items():
            (self.host / name).write_text(body, encoding="utf-8")
        env = dict(self.env, PYTHONPATH=str(S.REPO_ROOT))
        return subprocess.run(
            [sys.executable, "-m", "pytest", "-q", *args], cwd=str(self.host), env=env,
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
        )

    def test_tq100a_2_i_a_polluting_fixture_fails_a_real_session_in_a_real_repository(self):
        # covers: TQ-100a-2-i
        # angle: real_artifact
        control = self._run({"test_clean.py": _CLEAN})
        self.assertEqual(control.returncode, 0, control.stdout + control.stderr)
        (self.host / "test_clean.py").unlink()
        res = self._run({"test_polluter.py": _POLLUTER})
        out = res.stdout + res.stderr
        self.assertNotEqual(res.returncode, 0, out)
        self.assertIn("test_polluting_fixture_sandbox", out)
        self.assertIn("user.email", out)
        self.assertIn("real-human@example.com", out)
        self.assertIn("polluted@example.invalid", out)

    def test_tq100a_2_i_a_session_that_stopped_at_the_first_failure_still_compares(self):
        # covers: TQ-100a-2-i
        # angle: failure
        res = self._run({"test_a_polluter.py": _POLLUTER, "test_b_failer.py": _FAILER}, "-x")
        out = res.stdout + res.stderr
        self.assertNotEqual(res.returncode, 0, out)
        self.assertIn("test_polluting_fixture_sandbox", out)
        self.assertIn("polluted@example.invalid", out)
        self.assertIn("1 failed", out)  # the run really stopped at the failing test


def _guard_lines(out: str) -> list[str]:
    """The guard's own session-end record lines (its non-failure report)."""
    return [ln.strip() for ln in out.splitlines()
            if "git-identity-guard" in ln.lower() and "FAILURE" not in ln]


class TestTq100a2ISessionRecordDistinguishesCases(unittest.TestCase):
    """The run's own record must say which no-change case occurred."""

    def _session(self, identity: bool):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        env = S.scrubbed_env(root / "home")
        host = S.make_host(root, env, identity=identity)
        (host / "pytest.ini").write_text(
            f"[pytest]\naddopts = -p {_PLUGIN} -p no:cacheprovider -p no:randomly\n",
            encoding="utf-8",
        )
        (host / "test_clean.py").write_text(_CLEAN, encoding="utf-8")
        run_env = dict(env, PYTHONPATH=str(S.REPO_ROOT), AC_ENFORCE_STRICT="1")
        res = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"], cwd=str(host), env=run_env,
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
        )
        out = res.stdout + res.stderr
        return res.returncode, out, _guard_lines(out)

    def test_tq100a_2_i_present_values_matched_is_stated_in_the_session_record(self):
        # covers: TQ-100a-2-i
        # angle: criterion
        rc, out, lines = self._session(identity=True)
        self.assertEqual(rc, 0, out)  # control: unchanged identity does not fail the run
        self.assertEqual(len(lines), 1, out)
        low = lines[0].lower()
        self.assertTrue(
            "matched" in low or ("user.name" in low and "user.email" in low),
            f"line does not say present values were compared and matched: {lines[0]!r}",
        )

    def test_tq100a_2_i_no_identity_keys_is_stated_and_differs_from_the_matched_line(self):
        # covers: TQ-100a-2-i
        # angle: discrimination
        rc_absent, out_absent, absent_lines = self._session(identity=False)
        self.assertEqual(rc_absent, 0, out_absent)  # control: absent/absent does not fail
        rc_present, out_present, present_lines = self._session(identity=True)
        self.assertEqual(rc_present, 0, out_present)
        self.assertEqual(len(absent_lines), 1, out_absent)
        self.assertEqual(len(present_lines), 1, out_present)
        self.assertNotEqual(absent_lines[0], present_lines[0])
        low = absent_lines[0].lower()
        self.assertTrue(
            "no identity keys" in low or "not exercised" in low or "none present" in low,
            f"line does not say no identity keys were present: {absent_lines[0]!r}",
        )
        self.assertNotIn("matched", low)


if __name__ == "__main__":
    unittest.main()
