"""
MODULE: unit_tests/build_orchestration/test_bo4500a_3_i_checks_cannot_be_skipped.py
GOAL: BO-4500a-3-i -- no route can switch the checks off through the shared step.
      An inherited skip request (SKIP, hook-path override) is disregarded and
      reported; the step offers no skip option; a failing check named in a skip
      request still answers hook_failed.

The fixture check runner honours SKIP exactly as pre-commit does, so a step that
passes the caller's environment through unchanged leaves the checks unrun.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo4500a3_support import as_list, install_checks, ran_checks, scenario3  # noqa: E402

_SKIP = "check-doc-frontmatter,check-ac-schema"
_TWO_CHECKS = """
for c in check-doc-frontmatter check-ac-schema; do
  if skipped "$c"; then echo "$c skipped $n" >> "$S/skipped.log"; else ran "$c"; fi
done
exit 0
"""
_FAILING = """
if skipped check-ac-schema; then echo "check-ac-schema skipped" >> "$S/skipped.log"; exit 0; fi
ran check-ac-schema
report check-ac-schema Failed
echo '- hook id: check-ac-schema'
echo
echo 'notes.md: schema invalid'
exit 1
"""


def _hooks_path_override(sc) -> None:
    """Inherited git config that points core.hooksPath at nothing (turns hooks off)."""
    sc.env["GIT_CONFIG_COUNT"] = "1"
    sc.env["GIT_CONFIG_KEY_0"] = "core.hooksPath"
    sc.env["GIT_CONFIG_VALUE_0"] = str(sc.scratch / "no-such-hooks-dir")


class TestChecksCannotBeSkipped(unittest.TestCase):
    def test_inherited_skip_request_is_ignored_and_reported(self):
        # covers: BO-4500a-3-i
        # angle: discrimination
        """SKIP names two checks (plus a hooks-path override): both still run and both are reported.

        Wrong version caught: passing the caller's environment to the check runner unchanged.
        """
        control = scenario3(self)
        install_checks(control, _TWO_CHECKS)
        clean = control.run_step(["a.py", "notes.md"])
        self.assertEqual(clean.get("status"), "committed", clean)
        self.assertEqual(sorted(ran_checks(control)), ["check-ac-schema", "check-doc-frontmatter"])
        self.assertFalse(as_list(clean.get("skip_request_ignored")), "no skip was requested; none may be reported")

        sc = scenario3(self)
        install_checks(sc, _TWO_CHECKS)
        sc.env["SKIP"] = _SKIP
        sc.env["PRE_COMMIT_ALLOW_NO_CONFIG"] = "1"
        _hooks_path_override(sc)

        answer = sc.run_step(["a.py", "notes.md"])

        self.assertEqual(sorted(ran_checks(sc)), ["check-ac-schema", "check-doc-frontmatter"], "a skipped check did not run")
        self.assertFalse((sc.scratch / "skipped.log").exists(), "a check saw the skip request")
        self.assertEqual(answer.get("status"), "committed", answer)
        reported = repr(answer.get("skip_request_ignored"))
        self.assertTrue(answer.get("skip_request_ignored"), answer)
        self.assertIn("check-doc-frontmatter", reported)
        self.assertIn("check-ac-schema", reported)

    def test_step_options_offer_no_way_to_skip_checks(self):
        # covers: BO-4500a-3-i
        # angle: criterion
        """Every option in the usage text is listed; none skips checks; skip-shaped options are refused."""
        sc = scenario3(self)
        install_checks(sc, "ran check-a\nexit 0\n")
        usage = sc.run_raw(["--help"])
        self.assertEqual(usage.returncode, 0, usage.stderr)
        options = set(re.findall(r"(?<![\w-])(--?[A-Za-z][\w-]*)", usage.stdout))
        self.assertIn("--message-file", options, usage.stdout)
        self.assertEqual(options - {"--message-file", "--help", "-h"}, set(), f"unexpected options: {usage.stdout}")
        for option in options:
            self.assertIsNone(re.search(r"skip|verify|exempt|bypass|ignore|force|^-n$", option), option)

        baseline_commits = sc.commit_count()
        for flag in ("--no-verify", "--skip=check-ac-schema", "-n", "--skip-checks"):
            answer = sc.run_step(["a.py"], extra=[flag])
            self.assertEqual(answer.get("status"), "refused", (flag, answer))
            self.assertEqual(answer.get("reason_code"), "policy_unknown_option", (flag, answer))
            self.assertIn("skip_request_ignored", answer, "the answer contract carries this key on every outcome")
        self.assertEqual(sc.commit_count(), baseline_commits, "a skip-shaped option let a commit through")
        self.assertEqual(ran_checks(sc), [], "the checks ran for a refused call")

    def test_skipped_and_failing_check_answers_hook_failed_as_without_skip(self):
        # covers: BO-4500a-3-i
        # angle: failure
        """A failing check named in SKIP yields the same hook_failed answer as with no SKIP."""
        plain = scenario3(self)
        install_checks(plain, _FAILING)
        base = plain.run_step(["a.py", "notes.md"])

        sc = scenario3(self)
        install_checks(sc, _FAILING)
        sc.env["SKIP"] = _SKIP
        baseline_commits = sc.commit_count()
        answer = sc.run_step(["a.py", "notes.md"])

        self.assertEqual(base.get("status"), "hook_failed", base)
        self.assertEqual(answer.get("status"), "hook_failed", answer)
        for key in ("hook_name", "failing_files", "reason_code"):
            self.assertEqual(answer.get(key), base.get(key), key)
        self.assertEqual(answer.get("hook_name"), "check-ac-schema", answer)
        self.assertEqual(answer.get("failing_files"), ["notes.md"], answer)
        self.assertIn("check-ac-schema", repr(answer.get("skip_request_ignored")), answer)
        self.assertEqual(sc.commit_count(), baseline_commits, "a commit was recorded")
        self.assertFalse(as_list(base.get("skip_request_ignored")), "the no-skip run reported a skip")


if __name__ == "__main__":
    unittest.main()
