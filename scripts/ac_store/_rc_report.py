"""
MODULE: _rc_report
GOAL: Own the requirement rule check's report vocabulary and arithmetic -- the
    Finding record, the four dispositions, the rule-family name strings, dedupe,
    ordering, the verdict, the per-family counts and the deterministic JSON dump.
BUSINESS CONTEXT: ACD-2500a-1 makes a script (never a stage agent's prose) decide
    whether an authoring stage is complete. Every rule family reports through the one
    contract defined here, so plan-feature.js and the later groups (ACD-2500b/c/d)
    read one shape: {verdict, location, records_checked, findings, family_counts[, records_to_commit]}.
ARCHITECTURE: Pure data and functions, no I/O, no imports from sibling _rc_ modules
    (everything else imports this one). A finding is hashable by its key
    (file, record_id, rule_family, subject); `subject` and `repair` are internal and
    are NOT part of the emitted JSON. `family_counts` is the one additive key beyond the
    four-key ACD-2500a-1 contract (consumers must ignore unknown keys); `records_to_commit`
    (sorted repo-relative POSIX paths of every record file changed against the rev AFTER the
    run, repaired parents included) is the other, present only in `--changed-since` mode.
    Deployed flat into <root>/scripts/ac_store/ (AC_STORE_DEPLOY_MAP).

DECISION HISTORY:
  - 2026-10-21 [python-coder/ACD-2500a-2-vi, ACD-2500a-2-viii]: Added FAMILY_PROTECTED, `no_write`
    (a repair becomes `needs a decision` when the run has no before-state) and the additive
    top-level `before_state` {given, repairs_applied}, which sorts before family_counts and findings.
  - 2026-10-14 [python-coder/ACD-2500a-1]: Created. Dispositions rank failed >
    needs a decision > fixed > not evaluated when two findings share a key, so dedupe
    never hides a blocker behind a repair note.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any

FAMILY_BACKLINKS = "parent-to-child back-links"
FAMILY_COMPONENTS = "non-empty graph component list"
FAMILY_READINESS = "readiness never raised to approved by an authoring agent"
FAMILY_CONTRACTS = "producer/consumer contract symmetry"
FAMILY_DOC_TRIGGERS = "documentation trigger to documentation requirement mapping"
FAMILY_SURFACE = "specialist versus surface"
FAMILY_MODIFIES = "declared files versus modifies links"
FAMILY_TEST_INTENT = "test intent coverage"
FAMILY_TEST_DESIGN_GROUNDING = "test design grounding"
FAMILY_FILE_FINDINGS = "file findings consistency"
FAMILY_PROTECTED = "protected fields"
FAMILY_RECORD_SCHEMA = "record schema"
FAMILY_RECORD_READABLE = "record readable"

DISPOSITION_FIXED = "fixed"
DISPOSITION_DECISION = "needs a decision"
DISPOSITION_FAILED = "failed"
DISPOSITION_NOT_EVALUATED = "not evaluated"
BLOCKERS = frozenset({DISPOSITION_DECISION, DISPOSITION_FAILED})

_RANK = {
    DISPOSITION_FAILED: 3,
    DISPOSITION_DECISION: 2,
    DISPOSITION_FIXED: 1,
    DISPOSITION_NOT_EVALUATED: 0,
}


@dataclass
class Finding:
    """One report entry. `repair` is the (field, how) a repairing family attaches."""

    file: str
    record_id: str | None
    rule_family: str
    disposition: str
    message: str
    subject: str = ""
    line: int | None = None
    detail: Any = None
    repair: tuple[str, tuple] | None = None

    @classmethod
    def for_record(cls, record: Any, rule_family: str, disposition: str, message: str, **extra: Any) -> Finding:
        """Build a finding for a loaded record (takes `file` and the id from it)."""
        return cls(record.file, str(record["id"]), rule_family, disposition, message, **extra)

    @property
    def key(self) -> tuple[str, str | None, str, str]:
        """The dedupe identity: (file, record_id, rule_family, subject)."""
        return (self.file, self.record_id, self.rule_family, self.subject)

    @property
    def blocks(self) -> bool:
        """True when this finding fails the verdict."""
        return self.disposition in BLOCKERS

    def to_dict(self) -> dict[str, Any]:
        """The emitted JSON shape of the ACD-2500a-1 contract."""
        return {
            "file": self.file,
            "record_id": self.record_id,
            "rule_family": self.rule_family,
            "disposition": self.disposition,
            "message": self.message,
            "line": self.line,
            "detail": self.detail,
        }


def no_write(finding: Finding) -> Finding:
    """A repair finding of a run with no before-state: `needs a decision`, naming what would be written.

    Other findings pass through. The detail carries the field and the (verb, value) the
    repair would have applied, so a person can make the change by hand (ACD-2500a-2-viii).
    """
    if finding.repair is None:
        return finding
    field, how = finding.repair
    verb, value = how
    message = f"no before-state was given, so nothing was repaired; would {verb} {value!r} on {field}: {finding.message}"
    return replace(finding, disposition=DISPOSITION_DECISION, repair=None, message=message,
                   detail={"field": field, verb: value})


def dedupe(findings: list[Finding]) -> list[Finding]:
    """Keep one finding per key: the highest-ranked disposition, the first on a tie."""
    best: dict[tuple, Finding] = {}
    for finding in findings:
        held = best.get(finding.key)
        if held is None or _RANK.get(finding.disposition, 0) > _RANK.get(held.disposition, 0):
            best[finding.key] = finding
    return list(best.values())


def sort_findings(findings: list[Finding]) -> list[Finding]:
    """Order by (file, rule_family, subject, record_id, message) -- deterministic."""
    return sorted(
        findings,
        key=lambda f: (f.file, f.rule_family, f.subject, f.record_id or "", f.message),
    )


def verdict(records_checked: int, findings: list[Finding]) -> str:
    """`passed` iff at least one record was checked and no finding blocks."""
    if records_checked > 0 and not any(f.blocks for f in findings):
        return "passed"
    return "failed"


def family_counts(
    handed: dict[str, int], findings: list[Finding]
) -> dict[str, dict[str, int]]:
    """Per family: records judged and records listed `not evaluated`.

    `handed` is how many records each family was given; a record the family listed
    `not evaluated` was not judged, so it moves from `evaluated` to `not_evaluated`.
    """
    skipped: dict[str, set] = {}
    for finding in findings:
        if finding.disposition == DISPOSITION_NOT_EVALUATED:
            skipped.setdefault(finding.rule_family, set()).add((finding.file, finding.record_id))
    counts: dict[str, dict[str, int]] = {}
    for name, given in handed.items():
        not_evaluated = len(skipped.get(name, ()))
        counts[name] = {"evaluated": max(given - not_evaluated, 0), "not_evaluated": not_evaluated}
    return counts


def build_report(
    location: str,
    records_checked: int,
    findings: list[Finding],
    counts: dict[str, dict[str, int]],
    records_to_commit: list[str] | None = None,
    before_state: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Assemble the report dict (findings already deduped and sorted by the caller)."""
    report: dict[str, Any] = {
        "verdict": verdict(records_checked, findings),
        "location": location,
        "records_checked": records_checked,
        "findings": [f.to_dict() for f in findings],
        "family_counts": counts,
    }
    if records_to_commit is not None:
        report["records_to_commit"] = records_to_commit
    if before_state is not None:
        report["before_state"] = before_state
    return report


def dump_report(report: dict[str, Any]) -> str:
    """Deterministic JSON: sorted keys, ASCII, indent 2, no timestamps or absolute paths."""
    return json.dumps(report, sort_keys=True, ensure_ascii=True, indent=2)
