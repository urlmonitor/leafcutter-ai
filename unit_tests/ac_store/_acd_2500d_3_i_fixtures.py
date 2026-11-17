"""
MODULE: unit_tests/ac_store/_acd_2500d_3_i_fixtures.py
GOAL: Shared builders for the ticket 39 (ACD-2500d-3-i) tests: file-finding and decision records, the
    reviewed leaf that carries them, and a tmp consumer repo with real files for the "file findings
    consistency" rule family. Not collected: no test functions live here.
BUSINESS CONTEXT: G4 architect note (ticket 29), sections 3 to 5. The record shape is the d-1 / d-3-i
    contract: `file_findings` is a list of {file, verdict, line_range, found_in, reason, decision} and
    `file_findings_opened_files` lists the files the code-aware step opened. A decision is
    {choice, reason, by: "it-po"} or null; only a non-"consistent" verdict needs one.
ARCHITECTURE: Records are written by the real serializer through `_rule_check_fixtures.make_store`.
    `code_repo` adds REAL files under the tmp repo root (the rule check judges existence against its
    own `--repo-root`), so a finding about an existing file and one about a missing file are both
    exercised against a real tree.

PUBLIC API: FINDINGS, OPENED, UNDECIDED, FAMILY, EXISTING, MISSING, finding, decision, leaf,
    code_repo, family_findings.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "ac_store"))

from _acd_2500b_approval_fixtures import reviewed_no_tests  # noqa: E402
from _rule_check_fixtures import check_store, make_store, valid_record  # noqa: E402

FINDINGS = "file_findings"
OPENED = "file_findings_opened_files"
UNDECIDED = "file finding undecided"
FAMILY = "file findings consistency"
EXISTING = "scripts/ac_store/existing_mod.py"  # exists in `code_repo`
OTHER = "scripts/ac_store/other_mod.py"  # exists in `code_repo` too
MISSING = "scripts/ac_store/never_written.py"  # exists nowhere
STAND = "assignment stands"

__all__ = [
    "EXISTING", "FAMILY", "FINDINGS", "MISSING", "OPENED", "OTHER", "STAND", "UNDECIDED", "code_repo",
    "decision", "family_findings", "finding", "leaf", "make_store", "valid_record",
]


def decision(choice: str = STAND, reason: str = "The assignment is right as it stands.") -> dict:
    """A recorded planner decision."""
    return {"choice": choice, "reason": reason, "by": "it-po"}


def finding(
    file: str = EXISTING,
    verdict: str = "consistent",
    reason: str = "The file already holds this behaviour.",
    *,
    line_range: str | None = None,
    found_in: str | None = None,
    decided: dict | None = None,
) -> dict:
    """One file-findings entry; `decided=None` is the "no decision yet" state."""
    return {
        "file": file, "verdict": verdict, "line_range": line_range, "found_in": found_in,
        "reason": reason, "decision": decided,
    }


def leaf(record_id: str, findings: list[dict], opened: list[str] | None = None, **overrides: Any) -> dict:
    """A reviewed leaf (no tests required) carrying `findings`; `opened` defaults to every named file."""
    named = [item["file"] for item in findings]
    fields: dict[str, Any] = {FINDINGS: findings, OPENED: named if opened is None else opened}
    fields.update(overrides)
    return reviewed_no_tests(record_id, **fields)


def code_repo(store) -> Path:
    """Create the real source file EXISTING under the store's tmp repo root; return the root."""
    target = store.repo_root / EXISTING
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("def existing():\n    return 1\n", encoding="utf-8")
    return store.repo_root


def family_findings(tmp_path: Path, record: dict, stage: str = "itpo") -> tuple[int, list[dict]]:
    """Run the rule check over one record in a tmp repo; return (exit code, this family's findings)."""
    store = make_store(tmp_path, [record])
    code_repo(store)
    code, report = check_store(store, stage=stage)
    return code, [f for f in report["findings"] if f["rule_family"] == FAMILY]
