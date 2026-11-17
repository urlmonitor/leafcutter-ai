"""
MODULE: unit_tests/build_orchestration/_bo4500a3_support.py
GOAL: Helpers shared by the BO-4500a-3 tests (checks-first, bounded fix-and-retry,
      no-skip, verbatim hand-back) of the shared commit step
      (templates/scripts/commit_changes.py).

The "project's checks" are the repository's own git pre-commit hook. Each test
installs a fixture hook that COUNTS ITS OWN INVOCATIONS in a log under the scratch
directory, so every assertion reads the invocation log and git, never source.

CONTRACT PINNED FOR THE CODER (what the tests read; none of it is in the step yet):

  * Answer keys (BO-4500a-4): status, hook_name, failing_files, reason_code,
    hook_output (the check's output byte for byte), autofixed
    ([{hook_name, files}] after an in-call fix), skip_request_ignored (non-empty
    naming each skipped check when the environment asked for a skip; empty/absent
    otherwise), remedy and handoff (BO-3800a payload, or null).
  * reason_code: check_failed (a judging check failed), check_unsettled (a fixing
    check was still rewriting files on the last allowed run).
  * Retry ceiling: config/commit_step.json key max_automated_fix_retries (default
    3). Tests point the step at a DISPOSABLE copy of that file through the
    environment variable LEAFCUTTER_COMMIT_STEP_CONFIG (absolute path to the
    file). With the variable unset the step reads the package file.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _commit_step_support import REPO_ROOT, StepScenario  # noqa: E402

CONFIG_ENV = "LEAFCUTTER_COMMIT_STEP_CONFIG"
PACKAGE_CONFIG = REPO_ROOT / "config" / "commit_step.json"

_PREAMBLE = """
S='@S@'
n=$(cat "$S/count" 2>/dev/null || echo 0)
n=$((n+1))
echo "$n" > "$S/count"
echo "run $n head=$(git rev-parse --verify -q HEAD) staged=$(git diff --cached --name-only | tr '\\n' ' ')" >> "$S/runs.log"
report() { echo "$1.......................................$2"; }
ran() { echo "$1 $n" >> "$S/ran.log"; }
skipped() { case ",${SKIP:-}," in *",$1,"*) return 0;; esac; return 1; }
"""


def scenario3(case: unittest.TestCase) -> StepScenario:
    """Scratch repo: baseline a.py + notes.md, then both changed (ready to commit)."""
    sc = StepScenario(case)
    sc.seed_and_commit({"a.py": "a\n", "notes.md": "notes\n"})
    sc.write("a.py", "a changed\n")
    sc.write("notes.md", "notes changed\n")
    return sc


def install_checks(sc: StepScenario, body: str) -> None:
    """Install the fixture check runner: a counting preamble plus *body* (sh)."""
    sc.install_hook(_PREAMBLE.replace("@S@", str(sc.scratch)) + body)


def run_count(sc: StepScenario) -> int:
    """How many times the check runner was invoked (lines in the invocation log)."""
    log = sc.scratch / "runs.log"
    return len(log.read_text().splitlines()) if log.exists() else 0


def run_lines(sc: StepScenario) -> list[str]:
    log = sc.scratch / "runs.log"
    return log.read_text().splitlines() if log.exists() else []


def ran_checks(sc: StepScenario) -> list[str]:
    """Names of the individual checks that actually executed, in order."""
    log = sc.scratch / "ran.log"
    return [line.split()[0] for line in log.read_text().splitlines()] if log.exists() else []


def as_list(value: object) -> list:
    """Normalise a dict-or-list answer value to a list."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def package_ceiling_config() -> dict:
    """The package's real config/commit_step.json, parsed (fails when absent)."""
    return json.loads(PACKAGE_CONFIG.read_text(encoding="utf-8"))
