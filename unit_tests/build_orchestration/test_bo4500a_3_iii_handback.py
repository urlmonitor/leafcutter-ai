"""
MODULE: unit_tests/build_orchestration/test_bo4500a_3_iii_handback.py
GOAL: BO-4500a-3-iii -- a failure that needs judgement is handed back whole: the
      check's message verbatim, the BO-3800a handoff for an engage-specialist
      declaration, and the step starts no agent, edits no file, records no commit,
      and holds no state between calls.

SEAM: the real check-complexity script (templates/scripts/commit_guardian) is the
producer of the refusal text; the REAL remedy_handoff.py is the oracle the step's
`handoff` key is compared with.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo4500a3_support import REPO_ROOT, install_checks, ran_checks, run_count  # noqa: E402
from _commit_step_support import StepScenario  # noqa: E402

GUARDIAN_DIR = REPO_ROOT / "templates" / "scripts" / "commit_guardian"
SEED = REPO_ROOT / "templates" / "scripts" / "precommit-autofix.json"
MESSAGE = "scripts/big.py: 1210 lines exceeds the 1000-line limit"
BLOCK = (
    "check-file-size.......................................Failed\n"
    "- hook id: check-file-size\n"
    "- exit code: 1\n"
    "\n"
    f"{MESSAGE}\n"
    "  split it:  keep two spaces,\ttabs and trailing blanks   \n"
)
BIG = "".join(f"x{i} = {i}\n" for i in range(1210))
SMALL = "".join(f"x{i} = {i}\n" for i in range(10))
_JUDGE = """
if [ "$(wc -l < scripts/big.py)" -gt 1000 ]; then
  ran check-file-size
  cat "$S/block.txt"
  exit 1
fi
"""


def big_scenario(case: unittest.TestCase) -> StepScenario:
    sc = StepScenario(case)
    sc.seed_and_commit({"scripts/big.py": SMALL, "notes.md": "notes\n"})
    sc.write("scripts/big.py", BIG)
    sc.write("notes.md", "notes changed\n")
    (sc.scratch / "block.txt").write_bytes(BLOCK.encode("utf-8"))
    return sc


def _function(name: str, score: int) -> str:
    body = "".join(f"    if x == {i}:\n        pass\n" for i in range(score - 1))
    return f"def {name}(x):\n{body}    return x\n"


class TestJudgementHandback(unittest.TestCase):
    def test_judging_failure_message_is_reproduced_verbatim(self):
        # covers: BO-4500a-3-iii
        # angle: criterion
        """check-file-size fails scripts/big.py: hook_failed with the message byte for byte."""
        sc = big_scenario(self)
        install_checks(sc, _JUDGE + "exit 0\n")

        answer = sc.run_step(["scripts/big.py"])

        self.assertEqual(answer.get("status"), "hook_failed", answer)
        self.assertEqual(answer.get("hook_name"), "check-file-size", answer)
        self.assertEqual(answer.get("failing_files"), ["scripts/big.py"], answer)
        self.assertEqual(answer.get("reason_code"), "check_failed", answer)
        output = answer.get("hook_output") or ""
        self.assertIn(MESSAGE, output)
        self.assertIn(BLOCK, output, "hook_output is not the check's output byte for byte")

    def test_step_starts_no_agent_changes_no_file_records_no_commit(self):
        # covers: BO-4500a-3-iii
        # angle: discrimination
        """After the judging failure big.py is byte-identical, no commit exists, no agent started.

        Wrong version caught: the step trims the file to satisfy the limit (or launches an
        agent CLI to do it).
        """
        sc = big_scenario(self)
        install_checks(sc, _JUDGE + "exit 0\n")
        shims = sc.scratch / "bin"
        shims.mkdir()
        for tool in ("claude", "codex", "gemini"):
            shim = shims / tool
            shim.write_text(f"#!/bin/sh\necho {tool} >> '{sc.scratch}/agent_started.log'\n", encoding="utf-8")
            shim.chmod(0o755)
        sc.env["PATH"] = f"{shims}:{sc.env['PATH']}"
        before, notes_before, commits = sc.read("scripts/big.py"), sc.read("notes.md"), sc.commit_count()

        answer = sc.run_step(["scripts/big.py", "notes.md"])

        self.assertEqual(answer.get("status"), "hook_failed", answer)
        self.assertEqual(answer.get("hook_name"), "check-file-size", answer)
        self.assertEqual(answer.get("failing_files"), ["scripts/big.py"], answer)
        self.assertEqual(sc.read("scripts/big.py"), before, "the step changed the file to satisfy the check")
        self.assertEqual(sc.read("notes.md"), notes_before)
        self.assertEqual(sc.commit_count(), commits, "a commit was recorded")
        self.assertEqual(sc.staged_names(), [])
        self.assertFalse((sc.scratch / "agent_started.log").exists(), "the step started an agent")
        self.assertEqual(run_count(sc), 1, "only the check runner may run, once")
        self.assertEqual(sc.porcelain(), {"scripts/big.py": " M", "notes.md": " M"})

    def test_engage_specialist_handoff_equals_remedy_handoff_output(self):
        # covers: BO-4500a-3-iii
        # angle: seam
        """On real check-complexity output the answer's handoff equals remedy_handoff.py's stdout."""
        sc = StepScenario(self)
        shutil.copytree(GUARDIAN_DIR, sc.repo / "scripts" / "commit_guardian", ignore=shutil.ignore_patterns("__pycache__"))
        (sc.repo / "scripts" / "precommit-autofix.json").write_bytes(SEED.read_bytes())
        sc.seed_and_commit({"scripts/planner.py": _function("plan_batches", 30)})
        sc.git("add", "-A")
        sc.git("commit", "-q", "-m", "wire guardian")
        sc.write("scripts/planner.py", _function("plan_batches", 31))
        complexity = f"'{sys.executable}' scripts/commit_guardian/check_complexity.py"
        install_checks(
            sc,
            f"{complexity} > \"$S/complexity.out\" 2>&1\n"
            "rc=$?\n"
            'if [ $rc -ne 0 ]; then report check-complexity Failed; cat "$S/complexity.out"; exit 1; fi\n'
            "exit 0\n",
        )
        # Oracle: the real check on the real change, then the real builder on its output.
        sc.git("add", "scripts/planner.py")
        produced = subprocess.run(
            [sys.executable, "scripts/commit_guardian/check_complexity.py"],
            cwd=sc.repo, env=sc.env, capture_output=True, text=True, check=False,
        )
        sc.git("reset", "-q")
        self.assertEqual(produced.returncode, 1, produced.stdout + produced.stderr)
        self.assertIn("COMPLEXITY_REFUSAL_RECORD:", produced.stdout)
        oracle = subprocess.run(
            [sys.executable, "scripts/commit_guardian/remedy_handoff.py", "--hook-id", "check-complexity"],
            cwd=sc.repo, env=sc.env, input=produced.stdout, capture_output=True, text=True, check=False,
        )
        self.assertEqual(oracle.returncode, 0, oracle.stderr)
        expected = json.loads(oracle.stdout)

        answer = sc.run_step(["scripts/planner.py"])

        self.assertEqual(answer.get("status"), "hook_failed", answer)
        self.assertEqual(answer.get("hook_name"), "check-complexity", answer)
        self.assertEqual(answer.get("failing_files"), ["scripts/planner.py"], answer)
        self.assertIn("COMPLEXITY_REFUSAL_RECORD:", answer.get("hook_output") or "")
        self.assertEqual(answer.get("handoff"), expected, "the step's handoff differs from remedy_handoff.py's payload")
        self.assertEqual(answer.get("remedy"), expected["remedy"])

    def test_fresh_call_after_change_runs_checks_from_the_start(self):
        # covers: BO-4500a-3-iii
        # angle: boundary
        """After big.py is changed a second call runs the checks from run 1 with its own retry."""
        sc = big_scenario(self)
        install_checks(
            sc,
            _JUDGE
            + 'if [ "$(cat notes.md)" != "formatted" ]; then\n'
            "  ran format-md\n"
            '  echo "formatted" > notes.md\n'
            "  report format-md Failed\n"
            "  echo '- files were modified by this hook'\n"
            "  exit 1\n"
            "fi\n"
            "ran format-md\n"
            "exit 0\n",
        )
        names = ["scripts/big.py", "notes.md"]

        first = sc.run_step(names)
        self.assertEqual(first.get("status"), "hook_failed", first)
        self.assertEqual(first.get("failing_files"), ["scripts/big.py"], first)
        self.assertEqual(run_count(sc), 1)

        sc.write("scripts/big.py", SMALL)
        second = sc.run_step(names)

        self.assertEqual(second.get("status"), "committed", second)
        fixed = second.get("autofixed") or []
        self.assertEqual([item.get("hook_name") for item in fixed], ["format-md"], second)
        self.assertEqual(run_count(sc), 3, "the second call must run the checks twice (run 1 fixed, run 2 passed)")
        self.assertEqual(sc.committed_text("notes.md"), "formatted\n")
        self.assertEqual(sc.committed_text("scripts/big.py"), SMALL)
        self.assertEqual(ran_checks(sc).count("check-file-size"), 1, "the judging check ran in the first call only")


if __name__ == "__main__":
    unittest.main()
