"""
MODULE: unit_tests/build_orchestration/test_bo4500a_4_iii_no_shared_side_effects.py
GOAL: BO-4500a-4-iii -- the shared commit step (templates/scripts/commit_changes.py) never
      stops other work on the machine and never touches the repository's shared stash,
      on any of its four outcomes (committed, nothing_to_commit, refused, hook_failed).

GUARD tests: a "never does X" property that the step already satisfies, so they are green
today. What makes them constrain the code is that each one goes red under the exact wrong
version its AC names:

  * a machine-wide `pkill -f pytest` / `pkill -f unittest` inside the step kills the two
    fixture processes (their argv carries both words) -> the process test goes red;
  * a `git stash push` ... `git stash pop` around the commit leaves the final stash list
    identical, so the list alone would stay green. Two independent observers are used:
    the refs/stash reflog and a `reference-transaction` hook that logs every update of
    refs/stash made by anything during the call. Either one going non-empty fails the test.

Every test runs the REAL script as a subprocess against a REAL scratch git repository.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo4500a4_support import JUDGE_FAILS, StepScenario, install_checks, scenario3  # noqa: E402
from unit_tests.build_orchestration._workspace_maker_fixtures import link_checkout  # noqa: E402

# Unique substring in both fixture script names: a mutation under test may kill by it
# instead of machine-wide, which is equivalent for proving the test notices a kill.
FIXTURE_TAG = "bo4500a4iii_fixture"
_SLEEPER = "import time\ntime.sleep(600)\n"
_REF_HOOK = '#!/bin/sh\ncat | grep " refs/stash$" >> "$(git rev-parse --git-dir)/stash_ref_updates"\nexit 0\n'

OUTCOMES = ("committed", "nothing_to_commit", "refused", "hook_failed")


def _scenario_for(case: unittest.TestCase, outcome: str) -> tuple[StepScenario, list[str]]:
    """A scratch repo on feature/x ready to end in *outcome*, plus the step's argv."""
    if outcome == "nothing_to_commit":
        sc = StepScenario(case)
        sc.seed_and_commit({"a.py": "a\n", "notes.md": "notes\n"})
        return sc, ["--message-file", str(sc.message_file), "a.py"]
    sc = scenario3(case)
    if outcome == "committed":
        install_checks(sc, "exit 0\n")
    elif outcome == "hook_failed":
        install_checks(sc, JUDGE_FAILS)
    paths = [] if outcome == "refused" else ["a.py"]
    return sc, ["--message-file", str(sc.message_file), *paths]


def _run_outcome(case: unittest.TestCase, outcome: str, sc: StepScenario, argv: list[str]) -> dict:
    """Run the real step and confirm it really ended in *outcome* (so all four are covered)."""
    proc = sc.run_raw(argv)
    try:
        answer = json.loads(proc.stdout)
    except json.JSONDecodeError:
        case.fail(f"{outcome}: stdout is not one JSON object: {proc.stdout!r} stderr={proc.stderr[-300:]!r}")
    case.assertEqual(answer.get("status"), outcome, f"scenario did not end in {outcome}: {answer}")
    return answer


def _start_fixture_run(case: unittest.TestCase, scratch: Path, cwd: Path, word: str) -> subprocess.Popen:
    """A long-running process whose command line contains *word* (pytest / unittest)."""
    script = scratch / f"{FIXTURE_TAG}_{word}_run.py"
    script.write_text(_SLEEPER, encoding="utf-8")
    proc = subprocess.Popen([sys.executable, str(script)], cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _stop() -> None:
        if proc.poll() is None:
            proc.terminate()
        proc.wait(timeout=30)

    case.addCleanup(_stop)
    cmdline = ""
    deadline = time.monotonic() + 10
    while not cmdline and time.monotonic() < deadline:  # /proc is briefly empty while the child execs
        cmdline = Path(f"/proc/{proc.pid}/cmdline").read_bytes().replace(b"\0", b" ").decode()
        if not cmdline:
            time.sleep(0.02)
    case.assertIn(word, cmdline, "fixture must look like a test run so `pkill -f` would match it")
    case.assertIsNone(proc.poll(), "fixture process must be running before the step starts")
    return proc


def _seed_two_stash_entries(sc: StepScenario) -> None:
    """Record two stash entries without touching the working tree or index."""
    original = sc.read("a.py").decode()
    for n, text in enumerate(("stash one\n", "stash two\n"), start=1):
        sc.write("a.py", text)
        sha = sc.git("stash", "create").strip()
        sc.case.assertTrue(sha, "fixture: git stash create produced no commit")
        sc.git("stash", "store", "-m", f"fixture {n}", sha)
    sc.write("a.py", original)


def _stash_list(sc: StepScenario) -> list[str]:
    return sc.git("stash", "list", "--format=%gd %H %gs").splitlines()


def _stash_reflog(sc: StepScenario) -> list[str]:
    return sc.git("reflog", "show", "refs/stash", "--format=%H %gd %gs").splitlines()


def _stash_ref_updates(sc: StepScenario) -> list[str]:
    log = sc.repo / ".git" / "stash_ref_updates"
    return log.read_text().splitlines() if log.exists() else []


def _install_stash_ref_observer(sc: StepScenario) -> None:
    hook = sc.repo / ".git" / "hooks" / "reference-transaction"
    hook.write_text(_REF_HOOK, encoding="utf-8")
    hook.chmod(0o755)


class TestNoSharedSideEffects(unittest.TestCase):
    def test_parallel_test_runs_survive_every_outcome(self):
        # covers: BO-4500a-4-iii
        # angle: criterion
        """Two test-run-looking processes (sibling worktree, this workspace) outlive all four outcomes."""
        for outcome in OUTCOMES:
            with self.subTest(outcome=outcome):
                sc, argv = _scenario_for(self, outcome)
                sibling = sc.scratch / "sibling"
                link_checkout(sc.repo, ["-q", "-b", "sibling-branch", str(sibling)])
                sibling_run = _start_fixture_run(self, sc.scratch, sibling, "pytest")
                local_run = _start_fixture_run(self, sc.scratch, sc.repo, "unittest")
                _run_outcome(self, outcome, sc, argv)
                self.assertIsNone(sibling_run.poll(), f"{outcome}: the sibling-worktree test run was ended (rc={sibling_run.poll()})")
                self.assertIsNone(local_run.poll(), f"{outcome}: this workspace's test run was ended (rc={local_run.poll()})")

    def test_shared_stash_is_unchanged_on_every_outcome(self):
        # covers: BO-4500a-4-iii
        # angle: discrimination
        """Two stash entries are identical in content and order after each outcome; none was added mid-call."""
        for outcome in OUTCOMES:
            with self.subTest(outcome=outcome):
                sc, argv = _scenario_for(self, outcome)
                _seed_two_stash_entries(sc)
                list_before, reflog_before = _stash_list(sc), _stash_reflog(sc)
                self.assertEqual(len(list_before), 2, "fixture must hold exactly two stash entries")
                self.assertEqual(len(reflog_before), 2, "fixture must hold exactly two stash reflog entries")
                _install_stash_ref_observer(sc)
                _run_outcome(self, outcome, sc, argv)
                self.assertEqual(_stash_list(sc), list_before, f"{outcome}: stash list changed")
                self.assertEqual(_stash_reflog(sc), reflog_before, f"{outcome}: refs/stash reflog gained or lost entries")
                self.assertEqual(_stash_ref_updates(sc), [], f"{outcome}: refs/stash was updated during the call")
