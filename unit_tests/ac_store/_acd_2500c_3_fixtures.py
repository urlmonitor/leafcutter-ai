"""
MODULE: unit_tests/ac_store/_acd_2500c_3_fixtures.py
GOAL: Shared record builders and CLI helpers for the ACD-2500c-3 tests, which are split by
    concern over test_acd_2500c_3.py (schema and validators) and test_acd_2500c_3_report.py
    (generator seam, real store, by-author report). Not collected: no test functions.
ARCHITECTURE: Code-aware and legacy records, the shared control/accept helpers, and the
    `design_authors_report.py` subprocess runner. Moved verbatim from the original single file.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "ac_store"))

from _acd_2500_schema_probe import (  # noqa: E402
    SCRIPTS_DIR,
    base_record,
    both_verdicts,
    in_process_verdict,
)

REPORT_CLI = SCRIPTS_DIR / "design_authors_report.py"

STEP = "test-designer"
OPENED = ["scripts/ac_store/_test_intent.py", "unit_tests/ac_store/test_outcome_clauses.py"]
MUST_CATCH = ["revert the fix", "drop the second gate condition (retry_due)"]
CRITERIA = (
    "Given a stored design,\nWhen the record check reads it,\n"
    "Then the design is accepted,\nAnd the author is reported.\n"
)


def entry(name: str, clause: str, **extra) -> dict:
    """One code-aware test_spec entry: the existing keys plus the four per-entry keys."""
    item = {
        "name": name,
        "target_dir": "unit_tests/ac_store/",
        "framework": "pytest",
        "type": "unit",
        "angle": "criterion",
        "description": f"Asserts: {clause}.",
        "proves_clause": clause,
        "code_file": "scripts/ac_store/_test_intent.py",
        "to_be_created": False,
        "convention_test_file": "unit_tests/ac_store/test_outcome_clauses.py",
    }
    item.update(extra)
    return item


def code_aware_spec() -> list[dict]:
    """Two entries: one for existing code, one for a file that does not exist yet."""
    return [
        entry("test_design_is_accepted", "the design is accepted"),
        entry(
            "test_author_is_reported", "the author is reported",
            code_file="scripts/ac_store/design_authors_report.py", to_be_created=True,
        ),
    ]


def code_aware_record(record_id: str = "ZZD-1", **overrides) -> dict:
    """A record both validators must accept once the properties are declared."""
    fields = {
        "criteria": CRITERIA,
        "test_spec": code_aware_spec(),
        "test_design_authorship": {"step": STEP, "date": "2026-10-14"},
        "test_design_opened_files": list(OPENED),
    }
    fields.update(overrides)
    return base_record(record_id, **fields)


def legacy_record(record_id: str = "ZZD-2") -> dict:
    """A planner-style design: test_spec with the old keys only, no mark, no new key."""
    spec = [
        {"name": "test_design_is_accepted", "target_dir": "unit_tests/ac_store/", "framework": "pytest",
         "type": "unit", "description": "The design is accepted."}
    ]
    return base_record(record_id, criteria=CRITERIA, test_spec=spec)


def _control_accepted(tmp_path: Path) -> None:
    """Control row shared by the boundary tests: the well-formed code-aware record is accepted."""
    verdict = in_process_verdict(code_aware_record("ZZD-7"), tmp_path / "control")
    assert verdict.accepted, f"control row (a valid code-aware record) was rejected: {verdict.output}"


def _accepted_by_all(record: dict, tmp_path: Path) -> None:
    cli, hook = both_verdicts(record, tmp_path)
    assert cli.accepted, cli.output
    assert hook.accepted, hook.output


def _test_intent_module():
    return importlib.import_module("_test_intent")



def _run_report(argv: list[str]) -> tuple[int, dict | None, str]:
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, str(REPORT_CLI), *argv],
        capture_output=True, text=True, encoding="utf-8", timeout=60, env=env,
    )
    payload = None
    if "--json" in argv:
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise AssertionError(  # noqa: TRY003
                f"stdout must be exactly one JSON document: {exc}: {proc.stdout[:500]!r}; "
                f"exit={proc.returncode}, stderr={proc.stderr[:300]!r}"
            ) from exc
    return proc.returncode, payload, proc.stdout + proc.stderr


def _write_store(root: Path, records: list[tuple[str, dict]]) -> None:
    for sub, record in records:
        folder = root / sub
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{record['id']}.yaml").write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")

