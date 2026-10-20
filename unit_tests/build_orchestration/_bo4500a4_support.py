"""
MODULE: unit_tests/build_orchestration/_bo4500a4_support.py
GOAL: Helpers shared by the BO-4500a-4 one-answer-contract tests of the shared
      commit step (templates/scripts/commit_changes.py).

CONTRACT PINNED FOR THE CODER (nothing below is in the step yet):

  * config/commit_step.json is the ONE source of the answer vocabulary:
    answer_version (int 1), answer_keys (key -> empty value), reason_codes
    partitioned {policy: [...], step: [...], check: [...], nothing: ["nothing_changed"]},
    max_automated_fix_retries (3), max_transient_retries (3).
  * LEAFCUTTER_COMMIT_STEP_CONFIG names an alternative config file; a missing or
    schema-invalid file makes the step answer refused + step_config_unreadable.
  * Every answer carries exactly the keys in CONTRACT_KEYS.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo4500a3_support import CONFIG_ENV, PACKAGE_CONFIG, install_checks, scenario3  # noqa: E402
from _commit_step_support import REPO_ROOT, STEP, StepScenario  # noqa: E402

__all__ = [
    "CONFIG_ENV", "CONTRACT_KEYS", "REPO_ROOT", "STEP", "StepScenario", "install_checks",
    "scenario3", "FAMILIES", "load_vocabulary", "four_outcomes", "run_in", "write_config_copy",
    "complexity_scenario", "JUDGE_FAILS",
]

CONTRACT_KEYS = frozenset({
    "status", "reason_code", "reason", "sha", "paths", "added_parents", "unlisted_changes",
    "autofixed", "hook_name", "failing_files", "hook_output", "remedy", "handoff",
    "skip_request_ignored", "run", "ac_id", "answer_version",
})
FAMILIES = ("policy", "step", "check", "nothing")
GUARDIAN_DIR = REPO_ROOT / "templates" / "scripts" / "commit_guardian"
SEED = REPO_ROOT / "templates" / "scripts" / "precommit-autofix.json"

JUDGE_FAILS = (
    "report judge-py Failed\n"
    "echo '- hook id: judge-py'\n"
    "echo\n"
    "echo 'a.py: cannot be judged acceptable'\n"
    "exit 1\n"
)


def load_vocabulary(case: unittest.TestCase) -> dict:
    """The package config, parsed; fails the test when it lacks the vocabulary keys."""
    config = json.loads(PACKAGE_CONFIG.read_text(encoding="utf-8"))
    for key in ("answer_version", "answer_keys", "reason_codes", "max_transient_retries"):
        if key not in config:
            case.fail(f"config/commit_step.json carries no {key!r}: the vocabulary is not in config yet")
    families = config["reason_codes"]
    if sorted(families) != sorted(FAMILIES):
        case.fail(f"reason_codes families must be exactly {FAMILIES}, got {sorted(families)}")
    return config


def run_in(cwd: Path, env: dict, argv: list[str]) -> subprocess.CompletedProcess:
    """Run the real step as a subprocess in *cwd* with *env*."""
    return subprocess.run(
        [sys.executable, str(STEP), *argv],
        cwd=cwd, env=env, capture_output=True, text=True, timeout=120, check=False,
    )


def write_config_copy(sc: StepScenario, **changes: object) -> Path:
    """Write a DISPOSABLE copy of the package config with *changes*; point the step at it."""
    config = json.loads(PACKAGE_CONFIG.read_text(encoding="utf-8"))
    config.update(changes)
    path = sc.scratch / "commit_step.copy.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    sc.env[CONFIG_ENV] = str(path)
    return path


def four_outcomes(case: unittest.TestCase) -> dict[str, subprocess.CompletedProcess]:
    """Run four real calls ending committed, nothing_to_commit, refused, hook_failed."""
    out: dict[str, subprocess.CompletedProcess] = {}
    sc = scenario3(case)
    out["committed"] = sc.run_raw(["--message-file", str(sc.message_file), "a.py"])
    sc = StepScenario(case)
    sc.seed_and_commit({"a.py": "a\n"})
    out["nothing_to_commit"] = sc.run_raw(["--message-file", str(sc.message_file), "a.py"])
    sc = scenario3(case)
    out["refused"] = sc.run_raw(["--message-file", str(sc.message_file)])
    sc = scenario3(case)
    install_checks(sc, JUDGE_FAILS)
    out["hook_failed"] = sc.run_raw(["--message-file", str(sc.message_file), "a.py"])
    return out


def _function(name: str, score: int) -> str:
    body = "".join(f"    if x == {i}:\n        pass\n" for i in range(score - 1))
    return f"def {name}(x):\n{body}    return x\n"


def complexity_scenario(case: unittest.TestCase) -> StepScenario:
    """Repo wired with the real commit_guardian and a real over-limit complexity change."""
    sc = StepScenario(case)
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
    return sc
