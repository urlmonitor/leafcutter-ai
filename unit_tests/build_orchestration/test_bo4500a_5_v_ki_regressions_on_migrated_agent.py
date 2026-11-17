"""
MODULE: unit_tests/build_orchestration/test_bo4500a_5_v_ki_regressions_on_migrated_agent.py
GOAL: BO-4500a-5-v (test_spec test 4) -- the regression tests for
      KI-BO-20260914-commit-agent-rewrites-co-author-trailer and
      KI-BO-20260925-commit-agent-pkill-kills-parallel-test-runs run against the migrated
      commit agent AND the real shared step, and pass.

The existing KI regression tests live in this directory and exercise the REAL step
(templates/scripts/commit_changes.py) as a subprocess against a real scratch repo:

  * KI-BO-20260914 (trailer rewritten by the agent):
      test_bo4500a_2_ii_trailers.py          (no trailer gained, trailers kept in order,
                                              message after a fixer retry equals the file)
      test_bo4500a_2_message_from_file.py    (message recorded verbatim from the file)
  * KI-BO-20260925 (pkill kills parallel runs):
      test_bo4500a_4_iii_no_shared_side_effects.py  (parallel pytest/unittest-looking
                                              processes survive all four outcomes; shared
                                              stash untouched)

They cover the STEP half. They cannot see the agent template, which is where both KIs
originated (the 'Footer: Co-Authored-By: Claude Opus 4.7' line and Step 0's process kill).
So this test drives them in a FRESH pytest subprocess (never importlib.reload) AND asserts
the migrated template no longer carries either cause: the two halves together are the
"run against the migrated agent and the shared step" the AC asks for.

RED TODAY: the step half passes; the template half fails because commit.md still
carries both causes.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "workflows"))

import _bo4500a5v_support as T  # noqa: E402

KI_TRAILER_TESTS = ("test_bo4500a_2_ii_trailers.py", "test_bo4500a_2_message_from_file.py")
KI_PKILL_TESTS = ("test_bo4500a_4_iii_no_shared_side_effects.py",)


def _run_pytest(files: tuple[str, ...]) -> subprocess.CompletedProcess:
    argv = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *[str(HERE / f) for f in files]]
    return subprocess.run(argv, cwd=T.REPO_ROOT, capture_output=True, text=True, timeout=540, check=False)


class TestKiRegressionsOnMigratedAgent(unittest.TestCase):
    def test_regression_tests_for_trailer_and_pkill_kis_pass_against_migrated_agent(self):
        # covers: BO-4500a-5-v
        # angle: real_artifact
        """AC BO-4500a-5-v: both KI regression suites pass against the real step AND the
        migrated template carries neither cause.

        Wrong versions caught: migrate the step but leave commit.md's hardcoded Claude
        footer (KI-BO-20260914) or its Step 0 process kill (KI-BO-20260925) in place.
        """
        for ki, files in (("KI-BO-20260914", KI_TRAILER_TESTS), ("KI-BO-20260925", KI_PKILL_TESTS)):
            for name in files:
                self.assertTrue((HERE / name).is_file(), f"{ki}: regression test {name} is missing")
            with self.subTest(ki=ki, half="real step"):
                done = _run_pytest(files)
                self.assertEqual(done.returncode, 0, f"{ki}: regression tests failed:\n{done.stdout[-1500:]}\n{done.stderr[-500:]}")
                self.assertRegex(done.stdout, r"\d+ passed", f"{ki}: no passing test was reported:\n{done.stdout[-500:]}")

        text = T.template_text()
        hits = T.forbidden_hits(text)
        with self.subTest(ki="KI-BO-20260914", half="migrated template"):
            self.assertEqual(
                [h for h in hits if h in ("literal model name", "Claude co-author trailer")],
                [],
                "commit.md still hardcodes the Claude Co-Authored-By footer",
            )
        with self.subTest(ki="KI-BO-20260925", half="migrated template"):
            self.assertEqual(
                [h for h in hits if h in ("pkill", "kill", "taskkill", "Stop-Process", "process enumeration (pgrep)")],
                [],
                "commit.md still enumerates / kills test processes",
            )


if __name__ == "__main__":
    unittest.main()
