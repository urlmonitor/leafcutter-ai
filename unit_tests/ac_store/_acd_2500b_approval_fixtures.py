"""
MODULE: unit_tests/ac_store/_acd_2500b_approval_fixtures.py
GOAL: Shared record builders and real-CLI runners for the G3 part-2 tests (ACD-2500b-2, -2-i,
    -3): the approval step (`approve_acs.py`), the readiness scan (`scan_ac_store.py`), the
    by-author report and the generator. Not collected: no test functions live here.
BUSINESS CONTEXT: ADR-071 and the G3 architect note. A leaf code requirement carries test
    intent (what to prove) and, later, a test design (how); intent alone is never a test contract.
    Tickets 23, 24 and 25 drive the same store shapes, so the records and the subprocess plumbing
    live here once.
ARCHITECTURE: Records are written with the REAL serializer (yaml.safe_dump) through
    `_rule_check_fixtures.make_store`, in a tmp repo laid out like a consumer repo
    (<tmp>/docs/acceptance-criteria/ac-driven-dev/rule-check-demo/<ID>.yaml). The CLIs run as real
    subprocesses with cwd = the tmp repo root, so the approval step's default `--ac-root`
    (docs/acceptance-criteria/) resolves inside the tmp store and a repo-relative `file` is
    exactly `store.rel(<id>)`. The shipped store is never written.

PUBLIC API: TWO, PENDING, design_for, reviewed_intent, reviewed_no_tests, goal, legacy_leaf,
    legacy_spec, Run, run_approve, run_scan, run_report, run_generator, json_of, build,
    read_bytes, holds_module.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "ac_store"))

from _acd_2500c_3_fixtures import STEP, entry  # noqa: E402
from _rule_check_fixtures import (  # noqa: E402
    REPO_ROOT,
    Store,
    intent_record,
    make_store,
    valid_record,
)

SCRIPTS = REPO_ROOT / "scripts" / "ac_store"
APPROVE_CLI = SCRIPTS / "approve_acs.py"
SCAN_CLI = SCRIPTS / "scan_ac_store.py"
REPORT_CLI = SCRIPTS / "design_authors_report.py"
GENERATOR_CLI = SCRIPTS / "generate_ticket_from_ac.py"

#: Two plain outcome clauses (note section 6, item 15: fixtures use plain Then/And clauses).
TWO = ("the first outcome holds", "the second outcome holds")
PENDING = "test design pending"

__all__ = [
    "GENERATOR_CLI", "PENDING", "Run", "STEP", "Store", "TWO", "build", "design_for", "entry",
    "goal", "holds_module", "json_of", "legacy_leaf", "legacy_spec", "read_bytes",
    "reviewed_intent", "reviewed_no_tests", "run_approve", "run_generator", "run_report",
    "run_scan", "valid_record",
]


# --------------------------------------------------------------------------
# records
# --------------------------------------------------------------------------
def design_for(clauses: tuple[str, ...] | list[str], prefix: str = "test_proves") -> list[dict]:
    """A code-aware design: one test_spec entry per clause, linked through `proves_clause`."""
    return [entry(f"{prefix}_{index}", clause) for index, clause in enumerate(clauses, start=1)]


def reviewed_intent(
    record_id: str,
    clauses: tuple[str, ...] | list[str] = TWO,
    entries: list[dict] | None = None,
    spec: list[dict] | None = None,
    **overrides: Any,
) -> dict:
    """A leaf at readiness `reviewed` carrying test intent (every clause needs a test by default).

    `spec` (when given) is the record's test_spec: the design the intent is waiting for.
    """
    extra: dict[str, Any] = {"readiness": "reviewed"}
    extra.update(overrides)
    if spec is not None:
        extra["test_spec"] = spec
    return intent_record(record_id, list(clauses), entries, **extra)


def reviewed_no_tests(record_id: str, **overrides: Any) -> dict:
    """A prompt/docs leaf recorded as requiring no tests (note section 6, conflict 10)."""
    fields: dict[str, Any] = {
        "readiness": "reviewed",
        "change_target": "prompt",
        "assigned_agent": "llm-expert",
        "test_required": False,
    }
    fields.update(overrides)
    return valid_record(record_id, **fields)


def goal(goal_id: str, leaf_ids: list[str] | tuple[str, ...]) -> dict:
    """The goal (L1) record whose `covered_by` the approval step walks."""
    return valid_record(goal_id, level="L1", readiness="approved", covered_by=list(leaf_ids))


def legacy_spec() -> list[dict]:
    """A planner-written design: the old keys only, no per-entry clause link, no mark."""
    return [
        {
            "name": "test_legacy_behaviour",
            "target_dir": "unit_tests/ac_store/",
            "framework": "pytest",
            "type": "unit",
            "description": "The legacy design asserts the behaviour.",
        }
    ]


def legacy_leaf(record_id: str, readiness: str = "approved", **overrides: Any) -> dict:
    """A record whose design predates the change: test_spec, no mark, no test_intent."""
    return valid_record(record_id, readiness=readiness, test_spec=legacy_spec(), **overrides)


def build(tmp_path: Path, records: list[dict]) -> Store:
    """Write `records` into a tmp consumer-style repo (real serializer) and return the store."""
    return make_store(tmp_path, records)


def read_bytes(store: Store, record_id: str) -> bytes:
    """The raw on-disk bytes of one record (byte-identity assertions)."""
    return store.path(record_id).read_bytes()


# --------------------------------------------------------------------------
# running the real CLIs
# --------------------------------------------------------------------------
class Run(NamedTuple):
    exit_code: int
    stdout: str
    stderr: str


def _run(script: Path, argv: tuple[str, ...], cwd: Path | None) -> Run:
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, str(script), *argv],
        cwd=str(cwd) if cwd else None,
        capture_output=True, text=True, encoding="utf-8", timeout=90, env=env,
    )
    return Run(proc.returncode, proc.stdout, proc.stderr)


def run_approve(store: Store, *argv: str) -> Run:
    """`python scripts/ac_store/approve_acs.py <argv>` with cwd = the tmp repo root."""
    return _run(APPROVE_CLI, argv, store.repo_root)


def run_scan(store: Store, *argv: str) -> Run:
    """`python scripts/ac_store/scan_ac_store.py --json --ac-root <tmp store> <argv>`."""
    root = str(store.repo_root / "docs" / "acceptance-criteria")
    return _run(SCAN_CLI, ("--json", "--ac-root", root, *argv), store.repo_root)


def run_report(store: Store) -> Run:
    """`python scripts/ac_store/design_authors_report.py --json --ac-root <tmp store>`."""
    root = str(store.repo_root / "docs" / "acceptance-criteria")
    return _run(REPORT_CLI, ("--json", "--ac-root", root), store.repo_root)


def run_generator(argv: list[str]) -> Run:
    """`python scripts/ac_store/generate_ticket_from_ac.py <argv>`."""
    return _run(GENERATOR_CLI, tuple(argv), None)


def json_of(run: Run) -> Any:
    """Parse stdout as exactly one JSON document; the failure message carries stderr."""
    try:
        return json.loads(run.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(  # noqa: TRY003
            f"stdout must be exactly one JSON document ({exc}); exit={run.exit_code}; "
            f"stdout={run.stdout[:400]!r}; stderr={run.stderr[:400]!r}"
        ) from exc


def holds_module():
    """Import scripts/ac_store/_approval_holds.py (absent until ticket 23 ships it)."""
    return importlib.import_module("_approval_holds")
