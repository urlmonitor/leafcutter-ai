"""
MODULE: unit_tests/build_guards/test_bp_1300f_1_viii_run_ci_local.py
GOAL: BP-1300f-1-viii -- scripts/run_ci_local.py's typecheck step is the required CI check
    "mypy ratchet (new errors only)": the same scripts/ci/mypy_ratchet.py call with the
    arguments ci.yml gives it (base origin/main), blocking, and never a pass when it
    inspected nothing or could not check.
APPROACH: Every behavioural arm runs the REAL scripts/run_ci_local.py as a subprocess with
    ``--only typecheck`` against a REAL temporary git repository holding the REAL ci.yml
    and the REAL ratchet, a base commit on main (also pointed at by refs/remotes/origin/main)
    and a head commit on a feature branch, with the real mypy. Nothing is stubbed. The parity
    arm extracts the ratchet call from the real ci.yml with a regex written here, not with the
    module's own parser, so a parser that drops or reorders a pathspec is caught.
"""

from __future__ import annotations

import importlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import NamedTuple

from unit_tests.build_guards._bp1300f_ratchet_fixture import REPO_ROOT, git

RUN_CI_LOCAL = REPO_ROOT / "scripts" / "run_ci_local.py"
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
RATCHET = REPO_ROOT / "scripts" / "ci" / "mypy_ratchet.py"
TIMEOUT = 600
_CALL = re.compile(r"python scripts/ci/mypy_ratchet\.py(?:[^\n\\]|\\\n)*")
_SVC_BASE = 'def f() -> str:\n    return "ok"\n'


class LocalRun(NamedTuple):
    code: int
    out: str


def ci_ratchet_tokens(ci_text: str) -> list[str]:
    """The ratchet call in *ci_text*, split as the shell would: an extraction independent
    of run_ci_local's own reader. Empty when ci.yml holds no such call."""
    match = _CALL.search(ci_text)
    return [] if match is None else shlex.split(match.group(0).replace("\\\n", " "))


class LocalTypecheckRepo(unittest.TestCase):
    """A real repository per test: the real ci.yml and ratchet plus scripts/svc.py on main."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="bp1300f-viii-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "repo"
        (self.root / ".github" / "workflows").mkdir(parents=True)
        (self.root / "scripts" / "ci").mkdir(parents=True)
        shutil.copyfile(CI_YML, self.root / ".github" / "workflows" / "ci.yml")
        shutil.copyfile(RATCHET, self.root / "scripts" / "ci" / "mypy_ratchet.py")
        git(self.root, "init", "-q", "-b", "main")

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit_base(self, files: dict[str, str], origin_main: bool = True) -> None:
        for rel, text in files.items():
            self.write(rel, text)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "base")
        if origin_main:
            git(self.root, "update-ref", "refs/remotes/origin/main", "HEAD")

    def commit_head(self, files: dict[str, str]) -> None:
        git(self.root, "checkout", "-q", "-b", "feature")
        for rel, text in files.items():
            self.write(rel, text)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "head")

    def run_local(self) -> LocalRun:
        argv = [sys.executable, str(RUN_CI_LOCAL), "--repo-root", str(self.root), "--only", "typecheck"]
        done = subprocess.run(argv, cwd=str(self.root), capture_output=True, text=True, timeout=TIMEOUT)
        return LocalRun(done.returncode, done.stdout + done.stderr)

    def assert_status(self, run: LocalRun, status: str) -> None:
        self.assertRegex(run.out, rf"\[{re.escape(status)}\] typecheck", run.out)


class TestTypecheckIsTheCiCall(unittest.TestCase):

    def test_bp_1300f_1_viii_local_typecheck_is_the_ci_ratchet_call(self):
        # covers: BP-1300f-1-viii
        # angle: seam
        local = importlib.import_module("scripts.run_ci_local")
        tokens = ci_ratchet_tokens(CI_YML.read_text(encoding="utf-8"))
        self.assertTrue(tokens, "ci.yml holds no scripts/ci/mypy_ratchet.py call")
        self.assertEqual(tokens[0], "python")
        expected = [sys.executable] + [
            token.replace("${{ github.base_ref }}", "main") for token in tokens[1:]
        ]
        self.assertIn("origin/main", expected)
        self.assertEqual(local.typecheck_command(REPO_ROOT, "main"), expected)
        self.assertGreaterEqual(len(expected[expected.index("--") + 1:]), 12, expected)

        gates = local.build_gates(REPO_ROOT, include_informational=False, base_branch="main")
        typecheck = [gate for gate in gates if gate["key"] == "typecheck"]
        self.assertEqual(len(typecheck), 1, gates)
        self.assertTrue(typecheck[0]["blocking"])
        self.assertEqual(typecheck[0]["argv"], expected)
        self.assertEqual(expected[1], "scripts/ci/mypy_ratchet.py", "the step must run the ratchet, not plain mypy")


class TestTypecheckVerdicts(LocalTypecheckRepo):

    def test_bp_1300f_1_viii_local_typecheck_follows_a_changed_ci_scope(self):
        # covers: BP-1300f-1-viii
        # angle: reachability
        ci_path = self.root / ".github" / "workflows" / "ci.yml"
        text = ci_path.read_text(encoding="utf-8")
        narrowed = 'python scripts/ci/mypy_ratchet.py --base "origin/${{ github.base_ref }}" -- \'tools/*.py\''
        ci_path.write_text(_CALL.sub(lambda _m: narrowed, text, count=1), encoding="utf-8")
        self.commit_base({"tools/x.py": _SVC_BASE})
        self.commit_head({"tools/x.py": "def f() -> str:\n    return 1\n"})
        run = self.run_local()
        self.assertEqual(run.code, 1, run.out)
        self.assert_status(run, "FAIL")
        self.assertIn("tools/x.py:2:", run.out)

    def test_bp_1300f_1_viii_new_error_fails_the_local_run_naming_it(self):
        # covers: BP-1300f-1-viii
        # angle: criterion
        self.commit_base({"scripts/svc.py": _SVC_BASE})
        self.commit_head({"scripts/svc.py": "def f() -> str:\n    return 1\n"})
        run = self.run_local()
        self.assertEqual(run.code, 1, run.out)
        self.assert_status(run, "FAIL")
        named = [line for line in run.out.splitlines() if "scripts/svc.py:2:" in line and "[return-value]" in line]
        self.assertTrue(named, run.out)

    def test_bp_1300f_1_viii_new_type_ignore_fails_the_local_run(self):
        # covers: BP-1300f-1-viii
        # angle: criterion
        self.commit_base({"scripts/svc.py": _SVC_BASE})
        self.commit_head({"scripts/svc.py": _SVC_BASE + "\n\nX: int = 1  # type: ignore\n"})
        run = self.run_local()
        self.assertEqual(run.code, 1, run.out)
        self.assert_status(run, "FAIL")
        self.assertIn("scripts/svc.py: type-ignore comments rose from 0 to 1", run.out)

    def test_bp_1300f_1_viii_clean_change_passes(self):
        # covers: BP-1300f-1-viii
        # angle: criterion
        self.commit_base({"scripts/svc.py": _SVC_BASE})
        self.commit_head({"scripts/svc.py": 'def f() -> str:\n    return "ok!"\n'})
        run = self.run_local()
        self.assertEqual(run.code, 0, run.out)
        self.assert_status(run, "PASS")

    def test_bp_1300f_1_viii_could_not_check_fails_the_local_run(self):
        # covers: BP-1300f-1-viii
        # angle: failure
        self.commit_base({"scripts/svc.py": _SVC_BASE}, origin_main=False)
        self.commit_head({"scripts/svc.py": 'def f() -> str:\n    return "ok!"\n'})
        run = self.run_local()
        self.assertEqual(run.code, 1, run.out)
        self.assert_status(run, "FAIL")
        self.assertIn("could not check", run.out.lower())
        self.assertNotRegex(run.out, r"\[PASS\] typecheck")

    def test_bp_1300f_1_viii_missing_ratchet_call_in_ci_fails_the_local_run(self):
        # covers: BP-1300f-1-viii
        # angle: failure
        self.write(".github/workflows/ci.yml",
                   "name: CI\non: push\njobs:\n  lint:\n    runs-on: ubuntu-latest\n"
                   "    steps:\n      - run: echo hi\n")
        self.commit_base({"scripts/svc.py": _SVC_BASE})
        self.commit_head({"scripts/svc.py": "def f() -> str:\n    return 1\n"})
        run = self.run_local()
        self.assertEqual(run.code, 1, run.out)
        self.assert_status(run, "FAIL")
        self.assertIn("could not check", run.out.lower())
        self.assertIn("ci.yml", run.out)

    def test_bp_1300f_1_viii_nothing_in_scope_is_not_shown_as_a_pass(self):
        # covers: BP-1300f-1-viii
        # angle: failure
        self.commit_base({"scripts/svc.py": _SVC_BASE})
        self.commit_head({"docs/notes.md": "# notes\n"})
        run = self.run_local()
        self.assertEqual(run.code, 0, run.out)
        self.assert_status(run, "NOTHING INSPECTED")
        self.assertNotRegex(run.out, r"\[PASS\] typecheck")
        last = [line for line in run.out.splitlines() if line.strip()][-1]
        self.assertIn("inspected nothing", last)


if __name__ == "__main__":
    unittest.main()
