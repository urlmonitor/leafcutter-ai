"""
MODULE: unit_tests/build_orchestration/test_bo4500a_3_ii_bounded_retry.py
GOAL: BO-4500a-3-ii -- after the last allowed retry a failure is reported; a fixer
      that never settles cannot loop the step, and the ceiling comes from
      config/commit_step.json (default 3), not from the step's code.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo4500a3_support import (  # noqa: E402
    CONFIG_ENV,
    install_checks,
    package_ceiling_config,
    run_count,
    scenario3,
)

_NEVER_SETTLES = """
ran format-py
echo "formatted $n" > a.py
report format-py Failed
echo '- files were modified by this hook'
exit 1
"""


class TestBoundedRetry(unittest.TestCase):
    def test_judging_failure_on_second_run_stops_after_two_runs(self):
        # covers: BO-4500a-3-ii
        # angle: criterion
        """Fixer rewrites a.py on run 1; a judging check fails a.py on run 2: two runs, no commit."""
        sc = scenario3(self)
        install_checks(
            sc,
            'if [ "$n" = "1" ]; then\n'
            "  echo 'formatted' > a.py\n"
            "  report format-py Failed\n"
            "  echo '- files were modified by this hook'\n"
            "  exit 1\n"
            "fi\n"
            "report judge-py Failed\n"
            "echo '- hook id: judge-py'\n"
            "echo\n"
            "echo 'a.py: cannot be judged acceptable'\n"
            "exit 1\n",
        )
        baseline_commits = sc.commit_count()

        answer = sc.run_step(["a.py"])

        self.assertEqual(run_count(sc), 2, "the checks must have run exactly twice")
        self.assertEqual(answer.get("status"), "hook_failed", answer)
        self.assertEqual(answer.get("reason_code"), "check_failed", answer)
        self.assertEqual(answer.get("hook_name"), "judge-py", answer)
        self.assertIn("a.py", answer.get("failing_files") or [], answer)
        self.assertEqual(sc.commit_count(), baseline_commits, "a commit was recorded")
        self.assertEqual(sc.staged_names(), [])

    def test_never_settling_fixer_is_stopped_at_the_configured_ceiling(self):
        # covers: BO-4500a-3-ii
        # angle: discrimination
        """A fixer that rewrites a.py on every run is stopped at 1 + ceiling runs.

        Wrong versions caught: retrying until the fixer settles (the run count would be
        unbounded or the commit eventually recorded); a ceiling hard-coded in the step
        (the disposable-config runs would still show the default's run count).
        """
        for ceiling, env_override in ((3, False), (1, True), (5, True)):
            with self.subTest(ceiling=ceiling):
                sc = scenario3(self)
                if env_override:
                    config = dict(package_ceiling_config())
                    config["max_automated_fix_retries"] = ceiling
                    disposable = sc.scratch / "commit_step.json"
                    disposable.write_text(json.dumps(config), encoding="utf-8")
                    sc.env[CONFIG_ENV] = str(disposable)
                install_checks(sc, _NEVER_SETTLES)
                baseline_commits = sc.commit_count()

                answer = sc.run_step(["a.py"])

                self.assertEqual(run_count(sc), 1 + ceiling, f"expected exactly {1 + ceiling} runs")
                self.assertEqual(answer.get("status"), "hook_failed", answer)
                self.assertEqual(answer.get("reason_code"), "check_unsettled", answer)
                self.assertEqual(answer.get("hook_name"), "format-py", answer)
                self.assertEqual(answer.get("failing_files"), ["a.py"], answer)
                self.assertEqual(sc.commit_count(), baseline_commits, "a commit was recorded")
                self.assertEqual(sc.staged_names(), [], "the call left files staged")
                self.assertEqual(sc.read("a.py"), f"formatted {1 + ceiling}\n".encode(), "the last rewrite was not kept")
                if not env_override:
                    default = package_ceiling_config().get("max_automated_fix_retries")
                    self.assertEqual(default, 3, "config/commit_step.json must default the ceiling to 3")


if __name__ == "__main__":
    unittest.main()
