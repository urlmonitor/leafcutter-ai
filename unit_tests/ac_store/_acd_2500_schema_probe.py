"""
MODULE: unit_tests/ac_store/_acd_2500_schema_probe.py
GOAL: Run ONE AC record through the store's two record validators and report both
    verdicts, so a test can assert that they agree and that the offending key is named.
BUSINESS CONTEXT: ACD-2500b-1-i (test_intent) and ACD-2500c-3 (per-entry keys and
    provenance) both extend config/ac_store_schema.json. ADR-071 and the architect
    notes require that the standalone validator and the commit-time hook read that
    one file and give IDENTICAL verdicts. Shared here so the two test files probe
    the validators the same way.
ARCHITECTURE: Records are serialised with the REAL serializer (yaml.safe_dump), never
    typed as YAML text. Both validators run as real subprocesses (their production
    entry points): `scripts/ac_store/validate_ac_schema.py <file>` and the commit
    hook `scripts/commit_guardian/check_ac_schema.py` (HOOK_ROOT pointed at a tmp repo
    that holds a verbatim copy of config/ac_store_schema.json; the harness of
    unit_tests/commit_guardian/test_tq_500f_check_ac_schema_entry_naming.py).
    `in_process_verdict` calls `validate_ac_schema._validate_file` for the many
    boundary cases where a subprocess per case would be wasteful.

PUBLIC API:
    base_record(record_id="ZZI-1", **overrides) -> dict   (a record both validators accept)
    cli_verdict(record, tmp_path) -> Verdict
    hook_verdict(record, tmp_path) -> Verdict
    in_process_verdict(record, tmp_path) -> Verdict
    both_verdicts(record, tmp_path) -> tuple[Verdict, Verdict]
    Verdict: .accepted (bool), .output (stdout + stderr text), .exit_code
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, NamedTuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts" / "ac_store"
SCHEMA_FILE = REPO_ROOT / "config" / "ac_store_schema.json"
CLI_SCRIPT = SCRIPTS_DIR / "validate_ac_schema.py"
HOOK_SCRIPT = REPO_ROOT / "scripts" / "commit_guardian" / "check_ac_schema.py"


class Verdict(NamedTuple):
    """One validator's answer for one record."""

    accepted: bool
    output: str
    exit_code: int


def base_record(record_id: str = "ZZI-1", **overrides: Any) -> dict:
    """A record both validators accept today (no test contract: readiness `draft`)."""
    record: dict[str, Any] = {
        "id": record_id,
        "title": f"Schema probe {record_id}",
        "component": "ac-driven-dev",
        "components": ["ac_driven_dev"],
        "status": "active",
        "created_by": "tickets/test.md",
        "priority": "medium",
        "readiness": "draft",
        "criteria": "Given a fixture record,\nWhen the check runs,\nThen it is a valid requirement.\n",
    }
    record.update(overrides)
    return record


def _dump(record: dict) -> str:
    return yaml.safe_dump(record, sort_keys=False, allow_unicode=True)


def cli_verdict(record: dict, tmp_path: Path) -> Verdict:
    """`python scripts/ac_store/validate_ac_schema.py <record file>` in a subprocess."""
    folder = Path(tmp_path) / "cli"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{record['id']}.yaml"
    target.write_text(_dump(record), encoding="utf-8")
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, str(CLI_SCRIPT), str(target)],
        capture_output=True, text=True, encoding="utf-8", cwd=str(REPO_ROOT), timeout=60, env=env,
    )
    return Verdict(proc.returncode == 0, proc.stdout + proc.stderr, proc.returncode)


def hook_verdict(record: dict, tmp_path: Path) -> Verdict:
    """The real commit hook `check_ac_schema.py` over a tmp repo holding one staged record."""
    root = Path(tmp_path) / "hook_repo"
    (root / "config").mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCHEMA_FILE, root / "config" / "ac_store_schema.json")
    store = root / "docs" / "acceptance-criteria"
    store.mkdir(parents=True, exist_ok=True)
    target = store / f"{record['id']}.yaml"
    target.write_text(_dump(record), encoding="utf-8")
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "HOOK_ROOT": str(root),
        "HOOK_TEST_STAGED_FILES": str(target),
        "HOOK_NO_GIT": "1",
    }
    proc = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        capture_output=True, text=True, encoding="utf-8", cwd=str(REPO_ROOT), timeout=60, env=env,
    )
    return Verdict(proc.returncode == 0, proc.stdout + proc.stderr, proc.returncode)


def in_process_verdict(record: dict, tmp_path: Path) -> Verdict:
    """`validate_ac_schema._validate_file` with the real schema loaded (many cheap cases)."""
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    import validate_ac_schema  # noqa: PLC0415 - scripts/ac_store is put on sys.path just above

    folder = Path(tmp_path) / "inproc"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{record['id']}.yaml"
    target.write_text(_dump(record), encoding="utf-8")
    schema, warning = validate_ac_schema.load_ac_store_schema(SCHEMA_FILE)
    assert schema is not None, warning
    errors = validate_ac_schema._validate_file(target, schema=schema)
    return Verdict(not errors, "\n".join(errors), 0 if not errors else 1)


def both_verdicts(record: dict, tmp_path: Path) -> tuple[Verdict, Verdict]:
    """(standalone CLI verdict, commit hook verdict) for `record`."""
    return cli_verdict(record, tmp_path), hook_verdict(record, tmp_path)
