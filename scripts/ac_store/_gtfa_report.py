#!/usr/bin/env python3
"""
MODULE: _gtfa_report
GOAL: Answer, for ``--verify``, the one question an AC author actually needs
    answered before a ticket is built: can agents work from this AC alone?
BUSINESS CONTEXT: Every check here asks whether the AC — the source of truth —
    carries enough for a coder to build and a test-writer to test purely by
    following the generated ticket's pointers. A FAIL means the ticket would be
    blocked or unbuildable and the run exits non-zero; a WARN means it would
    proceed but on thinner ground than the author probably intends.
ARCHITECTURE: One check is deliberately not symmetrical with the others: an
    authored ``test_spec`` counts as a PASS on ANY record, code or not.
    Reporting "no test contract required" on a record that authored one is a
    success-shaped message printed over a silent discard, and that message is
    what let 85 records reach ``approved`` with their contracts being thrown
    away. Each check is a small function taking the shared ``record`` callback,
    so the verdict logic stays in one place and a new check cannot forget to
    set ``has_fail``.
"""

from __future__ import annotations

import importlib
import logging
import re
from typing import Callable

# See the "Sibling wiring" note in generate_ticket_from_ac.py for why the
# sibling package prefix is derived from __name__ rather than hard-coded.
_PKG = __name__.rpartition(".")[0]
_gtfa_seams = importlib.import_module(f"{_PKG}._gtfa_seams" if _PKG else "_gtfa_seams")
_gtfa_constants = importlib.import_module(
    f"{_PKG}._gtfa_constants" if _PKG else "_gtfa_constants"
)
_gtfa_config = importlib.import_module(
    f"{_PKG}._gtfa_config" if _PKG else "_gtfa_config"
)

logger = logging.getLogger(_gtfa_seams.logger_name())

AcRecord = _gtfa_constants.AcRecord

#: Signature of the status-recording callback shared by every check below.
Recorder = Callable[[str, str], None]


def _check_test_contract(
    record: Recorder,
    *,
    has_spec: bool,
    test_spec: list,
    test_required: object,
    is_code_ac: bool,
    criteria: str,
) -> None:
    """Report on the AC's test contract.

    An authored test_spec counts on ANY AC, code or not: reporting "no test
    contract required" on a record that authored one is a success-shaped
    message over a silent discard, and is what allowed 85 records to reach
    `approved` with their contracts being thrown away.

    Args:
        record: The status-recording callback.
        has_spec: Whether the AC authored a non-empty test_spec.
        test_spec: The authored test_spec list (possibly empty).
        test_required: The AC's ``test_required`` value, if any.
        is_code_ac: Whether the computed map has a production_code producer.
        criteria: The AC's criteria text.
    """
    if has_spec:
        record("PASS", f"test_spec authored ({len(test_spec)} test(s)) — precise test contract")
        if test_required is False:
            record(
                "WARN",
                "test_required: false alongside an authored test_spec — the opt-out "
                "wins and the spec is ignored (remove one of the two)",
            )
    elif is_code_ac:
        if test_required is False:
            record("WARN", "test_required: false on a code AC — no tests will be authored (confirm this is intentional)")
        elif criteria:
            record(
                "WARN",
                "no test_spec — Test Requirements will be DERIVED from criteria "
                "Then-clauses (author test_spec on the AC for a precise contract)",
            )
        else:
            record("FAIL", "code AC with neither test_spec nor derivable criteria — test-writer has nothing to write")
    else:
        record("PASS", "non-code AC with no authored test_spec — no test contract required")


def _check_scope_and_eligibility(
    record: Recorder,
    ac: AcRecord,
    is_code_ac: bool,
    files_touched: list[str],
) -> None:
    """Report on implementation constraints, file scope, and scanner eligibility.

    Args:
        record: The status-recording callback.
        ac: Parsed AC record.
        is_code_ac: Whether the computed map has a production_code producer.
        files_touched: Local paths extracted from doc_links.
    """
    # 5. Implementation constraints for the coder.
    if is_code_ac:
        if ac.get("it_requirements"):
            record("PASS", "it_requirements present — coder gets an Implementation Notes section")
        else:
            record("WARN", "no it_requirements — coder has only the criteria to work from")

    # 6. File scope.
    if files_touched:
        record("PASS", f"files_touched has {len(files_touched)} path(s) from doc_links")
    else:
        record("WARN", "files_touched is empty — coder has no file-scope signal (add doc_links to the AC)")

    # 7. Scanner eligibility.
    if ac.get("readiness") == "approved":
        record("PASS", "readiness: approved (scanner-eligible)")
    else:
        record("WARN", f"readiness: {ac.get('readiness')!r} — the AC scanner only surfaces approved ACs")


def _build_verification_report(
    ac: AcRecord,
    ac_id: str,
    agents: dict[str, str],
    ticket_body: str,
    files_touched: list[str],
) -> tuple[str, bool]:
    """Build a readiness report answering "can agents work from this AC alone?".

    Verifies that the AC (the source of truth) carries enough for a coder to
    build and a test-writer to test purely by following the generated ticket's
    pointers. Each line is tagged PASS / WARN / FAIL. Returns the formatted
    report and a boolean indicating whether any FAIL was recorded.

    Args:
        ac: Parsed AC record.
        ac_id: The AC id.
        agents: The computed agents map.
        ticket_body: The generated ticket body (for guard-equivalence checks).
        files_touched: Local paths extracted from doc_links.

    Returns:
        ``(report_text, has_fail)``.
    """
    lines: list[str] = []
    has_fail = False

    def record(status: str, message: str) -> None:
        """Append a status-tagged line to *lines* and set has_fail on FAIL.

        Args:
            status: One of ``"PASS"``, ``"WARN"``, or ``"FAIL"``.
            message: Human-readable description of the check result.
        """
        nonlocal has_fail
        if status == "FAIL":
            has_fail = True
        lines.append(f"  [{status}] {message}")

    is_code_ac = _gtfa_config._computed_map_has_production_code_producer(agents)
    criteria = str(ac.get("criteria") or "").strip()
    raw_spec = ac.get("test_spec")
    test_spec: list = raw_spec if isinstance(raw_spec, list) else []
    has_spec = len(test_spec) > 0
    test_required = ac.get("test_required")

    # 1. Criteria present — a coder and test-writer both need it.
    if criteria:
        record("PASS", "criteria present (behavioural source of truth)")
    else:
        record("FAIL", "criteria is empty — nothing for a coder or test-writer to work from")

    # 2. Assigned agent.
    if ac.get("assigned_agent"):
        record("PASS", f"assigned_agent: {ac.get('assigned_agent')}")
    else:
        record("WARN", "assigned_agent absent — generator defaults to python-coder")

    # 3. Test contract.
    _check_test_contract(
        record,
        has_spec=has_spec,
        test_spec=test_spec,
        test_required=test_required,
        is_code_ac=is_code_ac,
        criteria=criteria,
    )

    # 4. Generated Test Requirements would pass the ticket-level guard.
    if (is_code_ac or has_spec) and test_required is not False:
        if re.search(r"^\s*-\s+name:\s+\S+", ticket_body, re.MULTILINE):
            record("PASS", "generated ## Test Requirements has >=1 test entry (ticket guard passes)")
        else:
            record("FAIL", "generated ## Test Requirements has no test entry — ticket guard would block dispatch")

    # 5-7. Implementation constraints, file scope, scanner eligibility.
    _check_scope_and_eligibility(record, ac, is_code_ac, files_touched)

    verdict = "BLOCKED" if has_fail else ("READY" if all("[WARN]" not in ln for ln in lines) else "READY (with warnings)")
    header = f"=== Ticket readiness report for {ac_id}: {verdict} ==="
    return "\n".join([header, *lines]), has_fail
