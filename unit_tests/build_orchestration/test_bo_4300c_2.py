"""
MODULE: unit_tests/build_orchestration/test_bo_4300c_2.py
AC: BO-4300c-2 -- "The maker's answer is one readable answer and nothing else"
TICKET: tickets/00_inbox/epics/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/
    03_TICKET-20260928-BO-4300-answer-contract.md

Real-subprocess proof against the DEPLOYED maker (resolved through the shared
locator in _workspace_maker_fixtures.py): real temp repos, a real bare hub, no
mock of git, no import of the maker module. Run with AC_ENFORCE_STRICT=1 to see
the genuine red baseline.

DECISION HISTORY
====================================================================
- 2026-09-30 10:00 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/03,
  BO-4300c-2]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/03)
====================================================================
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._workspace_maker_fixtures import (
    deployed_maker_path,
    make_project,
    run_maker,
)

_STATUS_EXIT = {"ok": 0, "refused": 2, "error": 1}
_FULL_ENUM = (
    "OK NOT_FOUND INCOMPLETE OCCUPIED OCCUPIED_LEGACY_WORKTREE IN_PROGRESS NO_REPO "
    "AMBIGUOUS_REPO NO_HUB FETCH_FAILED GIT_FAILED NO_CONFIG BOOTSTRAP_FAILED "
    "BOOTSTRAP_DIRTIED_TRACKED WORK_AT_RISK HOOKS_INACTIVE VERIFY_FAILED UNSENT_WORK "
    "PROCESS_HOLDS_FILES ON_PROTECTED_BRANCH TICKET_NOT_ON_BASE AMBIGUOUS_LINE USAGE "
    "INTERNAL_ERROR"
).split()
_FAILING_BUILD = "import sys\nsys.exit(3)\n"
_ENSURE = ["ensure", "--kind", "scratch", "--slug", "alpha"]


class TestBO4300c2Answer(unittest.TestCase):
    """One JSON object on stdout, stated status, matching exit, git chatter on stderr."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300c2-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def _outcomes(self) -> dict[str, dict]:
        """Run the four named outcomes; run_maker itself asserts exactly ONE JSON object."""
        results: dict[str, dict] = {}
        ok = make_project(self.tmp / "ok")
        results["ok"] = run_maker(_ENSURE, cwd=ok["project"])

        occ = make_project(self.tmp / "occ")
        (occ["landing_place"] / "scratch" / "alpha").mkdir(parents=True)
        (occ["landing_place"] / "scratch" / "alpha" / "note.txt").write_text("x\n", encoding="utf-8", newline="\n")
        results["occupied"] = run_maker(_ENSURE, cwd=occ["project"])

        unreach = make_project(self.tmp / "unreach")
        unreach["hub"].rename(self.tmp / "unreach" / "hub-moved.git")
        results["unreachable"] = run_maker(_ENSURE, cwd=unreach["project"])

        boot = make_project(self.tmp / "boot", stub_build=_FAILING_BUILD)
        results["bootstrap"] = run_maker(_ENSURE, cwd=boot["project"])
        return results

    def test_stdout_holds_exactly_one_json_object_in_each_outcome(self):
        # covers: BO-4300c-2
        # angle: criterion
        """stdout is exactly one JSON object: no BOM, one non-blank line, in all four outcomes."""
        outcomes = self._outcomes()
        for name, res in outcomes.items():
            with self.subTest(outcome=name):
                self.assertFalse(res["stdout"].startswith("﻿"))
                lines = [ln for ln in res["stdout"].splitlines() if ln.strip()]
                self.assertEqual(len(lines), 1, res["stdout"])
        self.assertEqual(outcomes["ok"]["answer"]["status"], "ok")

    def test_every_answer_states_its_status(self):
        # covers: BO-4300c-2
        # angle: criterion
        """Each answer has status in {ok, refused, error}, a code and a schema_version;
        the three named refusals are 'refused'."""
        outcomes = self._outcomes()
        for name, res in outcomes.items():
            with self.subTest(outcome=name):
                ans = res["answer"]
                self.assertIn(ans.get("status"), _STATUS_EXIT)
                self.assertIsInstance(ans.get("code"), str)
                self.assertIsInstance(ans.get("schema_version"), int)
        self.assertEqual(outcomes["ok"]["answer"]["code"], "OK")
        self.assertEqual(outcomes["occupied"]["answer"]["code"], "OCCUPIED")
        self.assertEqual(outcomes["unreachable"]["answer"]["status"], "refused")
        self.assertIn(outcomes["unreachable"]["answer"]["code"], ("FETCH_FAILED", "NO_HUB"))
        self.assertEqual(outcomes["bootstrap"]["answer"]["code"], "BOOTSTRAP_FAILED")
        self.assertEqual(outcomes["bootstrap"]["answer"]["status"], "refused")

    def test_git_progress_messages_appear_on_stderr_not_stdout(self):
        # covers: BO-4300c-2
        # angle: seam
        """Real git's own lines are forwarded to stderr and never reach stdout."""
        proj = make_project(self.tmp / "seam")
        res = run_maker(_ENSURE, cwd=proj["project"])
        for chatter in ("HEAD is now at", "set up to track", "Cloning into", "Switched to"):
            self.assertNotIn(chatter, res["stdout"])
        self.assertIn("Cloning into", res["stderr"], "git's own output must be forwarded to stderr")

    def test_exit_code_matches_stated_status(self):
        # covers: BO-4300c-2
        # angle: criterion
        """Exit code is 0/2/1 for ok/refused/error in each outcome."""
        outcomes = self._outcomes()
        for name, res in outcomes.items():
            with self.subTest(outcome=name):
                self.assertEqual(res["exit_code"], _STATUS_EXIT[res["answer"]["status"]])
        self.assertEqual(outcomes["ok"]["exit_code"], 0)
        self.assertEqual(outcomes["occupied"]["exit_code"], 2)

    def test_usage_error_still_emits_one_json_object(self):
        # covers: BO-4300c-2
        # angle: boundary
        """An unknown verb exits 64 with one JSON object (status error, code USAGE)."""
        res = run_maker(["no-such-verb"], cwd=self.tmp)
        self.assertEqual(res["answer"]["status"], "error")
        self.assertEqual(res["answer"]["code"], "USAGE")
        self.assertEqual(res["exit_code"], 64)

    def test_answer_table_lives_in_deployed_worktree_answer_module(self):
        # covers: BO-4300c-2
        # angle: deployed
        """worktree_answer.py is deployed beside the maker and owns the complete code table."""
        scripts_dir = deployed_maker_path().parent
        self.assertTrue((scripts_dir / "worktree_answer.py").is_file(), "worktree_answer.py not deployed")
        probe = (
            "import sys, json; sys.path.insert(0, sys.argv[1]); import worktree_answer as a\n"
            "out = {c: a.status_for_code(c) for c in sys.argv[2:]}\n"
            "out['_exit'] = a.exit_code_for_answer({'status': 'refused', 'code': 'AMBIGUOUS_LINE'})\n"
            "out['_usage'] = a.exit_code_for_answer({'status': 'error', 'code': 'USAGE'})\n"
            "print(json.dumps(out))\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", probe, str(scripts_dir), *_FULL_ENUM],
            capture_output=True, text=True, timeout=60, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        table = json.loads(proc.stdout)
        self.assertEqual(table["AMBIGUOUS_LINE"], "refused")
        self.assertEqual(table["UNSENT_WORK"], "refused")
        self.assertEqual(table["_exit"], 2)
        self.assertEqual(table["_usage"], 64)
        for code in _FULL_ENUM:
            self.assertIn(table[code], ("ok", "refused", "error"), code)

    def test_ticket_03_reachable_from_entry_point(self):
        # covers: BO-4300c-2
        # angle: reachability
        """Every verb, run through the deployed CLI, emits one object with code, schema_version, matching exit."""
        proj = make_project(self.tmp / "reach")
        cwd = proj["project"]
        ws = run_maker(_ENSURE, cwd=cwd)["answer"]["workspace_path"]
        verbs = {
            "ensure": _ENSURE,
            "locate": ["locate", "--kind", "scratch", "--slug", "alpha"],
            "verify": ["verify", "--path", ws],
            "where": ["where"],
        }
        for verb, argv in verbs.items():
            with self.subTest(verb=verb):
                res = run_maker(argv, cwd=cwd)
                self.assertEqual(res["answer"]["status"], "ok")
                self.assertEqual(res["answer"]["code"], "OK")
                self.assertIsInstance(res["answer"]["schema_version"], int)
                self.assertEqual(res["answer"]["verb"], verb)
                self.assertEqual(res["exit_code"], 0)


if __name__ == "__main__":
    unittest.main()
