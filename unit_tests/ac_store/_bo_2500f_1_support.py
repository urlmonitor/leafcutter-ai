"""
MODULE: unit_tests/ac_store/_bo_2500f_1_support.py
GOAL: Shared helpers for the BO-2500f-1 / BO-2500f-1-i test files: import the
    verification-record validator lazily (so a missing module is a per-test red,
    not a collection error) and run every real write-time check on one record.

PART-NAME VOCABULARY (the contract the coder must match; see test_bo_2500f_1.py):
    verified_by, verified_by.method, verified_by.check, verified_by.wired_as,
    verified_by.gate_run, verified_by.statement, verified_by.inspected,
    change_target.
"""
from __future__ import annotations

import copy
import importlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_AC_STORE = REPO_ROOT / "scripts" / "ac_store"
HOOK_SCRIPT = REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_ac_schema.py"
DONE_PROOF_SCRIPT = REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_done_proof.py"
VALIDATE_SCRIPT = SCRIPTS_AC_STORE / "validate_ac_schema.py"

if str(SCRIPTS_AC_STORE) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_AC_STORE))
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

RECORD_ID = "BO-9999f-1"
BLOB = "0123456789abcdef0123456789abcdef01234567"


def validator():
    """Import and return validate_verification_record (ModuleNotFoundError while absent)."""
    module = importlib.import_module("_verification_record")
    return module.validate_verification_record


def check_form() -> dict:
    return {"method": "check", "check": "templates/scripts/commit_guardian/check_x.py",
            "wired_as": "pre-commit:check-x"}


def inspection_form() -> dict:
    return {"method": "inspection", "gate_run": "pf-20261025-0912",
            "statement": "Read the prose; it states the rule.",
            "inspected": [{"path": "docs/how-to/x.md", "blob": BLOB}]}


def record(verified_by: Any = "__omit__", change_target: Any = "__omit__", **extra: Any) -> dict:
    """A test-free record mapping carrying the given verified_by / change_target."""
    rec: dict[str, Any] = {"id": RECORD_ID, "test_required": False, **extra}
    if verified_by != "__omit__":
        rec["verified_by"] = copy.deepcopy(verified_by)
    if change_target != "__omit__":
        rec["change_target"] = copy.deepcopy(change_target)
    return rec


def parts(verdict: dict) -> list[str]:
    return [p["part"] for p in verdict["problems"]]


def run_write_checks(tmp_path: Path, record_overrides: dict) -> dict[str, tuple[int, str]]:
    """Stage one unfinished record in a tmp git repo and run every REAL write-time check.

    Returns {check name: (exit code, combined output)}. Checks run: the check-ac-schema
    hook script, validate_ac_schema.py, check_done_proof.py --mode precommit (no switch),
    and requirement_rule_check.py. The record is written by the real serializer.
    """
    from _rule_check_fixtures import (  # noqa: WPS433
        make_store, run_cli_subprocess, cli_argv, valid_record,
    )

    rec = valid_record(
        "BO-9998", level="L0", work_status="in_progress", test_required=False,
        test_rationale="Prose only; no test can prove it.", **record_overrides,
    )
    store = make_store(tmp_path, [rec])
    root = store.repo_root
    path = store.path(rec["id"])
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "add", str(path.relative_to(root))],
                   check=True, capture_output=True)
    results: dict[str, tuple[int, str]] = {}

    env = dict(os.environ, HOOK_ROOT=str(root), HOOK_TEST_STAGED_FILES=str(path))
    proc = subprocess.run([sys.executable, str(HOOK_SCRIPT)], cwd=str(root), env=env,
                          capture_output=True, text=True, timeout=60)
    results["check-ac-schema hook"] = (proc.returncode, proc.stdout + proc.stderr)

    proc = subprocess.run([sys.executable, str(VALIDATE_SCRIPT), str(path)], cwd=str(root),
                          capture_output=True, text=True, timeout=60)
    results["validate_ac_schema.py"] = (proc.returncode, proc.stdout + proc.stderr)

    proc = subprocess.run([sys.executable, str(DONE_PROOF_SCRIPT), "--mode", "precommit",
                           "--test-root", str(root)], cwd=str(root),
                          capture_output=True, text=True, timeout=60)
    results["check_done_proof precommit"] = (proc.returncode, proc.stdout + proc.stderr)

    run = run_cli_subprocess(cli_argv(store), cwd=root)
    results["requirement_rule_check"] = (run.exit_code, run.stdout + run.stderr)
    return results


def assert_all_pass(testcase_fail, label: str, results: dict[str, tuple[int, str]]) -> None:
    bad = {name: out for name, (code, out) in results.items() if code != 0}
    if bad:
        testcase_fail(f"{label}: write-time checks refused an unfinished record: {bad}")


# Verification-record shapes that are missing, incomplete, unknown-method or not a mapping.
INVALID_SHAPES: dict[str, Any] = {
    "missing": "__omit__",
    "null": None,
    "incomplete_check": {"method": "check"},
    "unknown_method": {"method": "analysis"},
    "not_a_mapping": "inspection",
}
