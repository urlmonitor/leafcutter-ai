"""
MODULE: _lint_report
GOAL: Hold the lint gate's verdict as one value (`Report`) and turn it into the
    two things callers read: the human lines a developer sees (ending in
    `RESULT: <outcome>`) and the `--json` payload other runners parse.
BUSINESS CONTEXT: BP-1300e-1. The verdict must be visible on EVERY path and
    must never read as a pass when nothing was checked: pre-commit prints
    "Passed" beside any hook that exits 0 whatever the hook writes, so the
    exit status and the text are decided together here. Refusal text names
    each finding as `<path>:<line>:<col>: <CODE> <message> [step: <name>]`,
    marks one that predates the change, and states why that does not change
    the verdict (CI's required check rejects the file whichever change
    introduced the finding).
ARCHITECTURE: Pure functions over plain dataclasses; no I/O, no subprocess.
    Outcome names come from check_outcome.py (the one vocabulary); this
    module only adds the `could_not_check` reason names, declared once below.

DECISION HISTORY
- 2026-10-12 [python-coder/BP-1300e-1]: Created. Exit status: 0 for ok and
    nothing_to_inspect, 1 for refused and could_not_check; consumers tell the
    two non-zero outcomes apart by `outcome`, never by exit code.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import check_outcome as co

REASONS = (
    "ruff_not_installed",
    "ruff_failed_to_start",
    "ruff_config_unreadable",
    "declaration_unreadable",
    "ruff_config_partially_staged",
    "ruff_config_outside_project",
    "linter_version_mismatch",
    "linter_version_source_unreadable",
    "no_repository",
    "internal_error",
)

PREDATES_NOTE = (
    "Findings marked 'predates this change' were already present before this commit, but they "
    "are in a file this commit modifies, and CI's required lint check rejects the file "
    "whichever change introduced it."
)


@dataclass
class Finding:
    """One lint finding, reported as CI's lint check would report it."""

    path: str
    line: int
    col: int
    code: str
    message: str
    step: str
    predates_change: bool = False

    def key(self) -> tuple[str, int, str]:
        """Identity used to dedupe the same finding reported by two steps."""
        return (self.path, self.line, self.code)


@dataclass
class Report:
    """The gate's single verdict, whatever path produced it."""

    mode: str = "staged"
    outcome: str = co.OUTCOME_OK
    reason: str | None = None
    detail: str = ""
    fix: str = ""
    ruff_version: str | None = None
    required_ruff_version: str | None = None
    version_source: str | None = None
    version_check: str = "not_reached"
    version_note: str = ""
    files_inspected: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    considered: int = 0


def exit_code(report: Report) -> int:
    """0 for a clean or empty verdict, 1 for refused and could_not_check."""
    return 0 if report.outcome in (co.OUTCOME_OK, co.OUTCOME_NOTHING_TO_INSPECT) else 1


def to_payload(report: Report) -> dict:
    """Build the documented --json payload (a stable, parseable contract)."""
    return {
        "outcome": report.outcome,
        "reason": report.reason,
        "detail": report.detail,
        "mode": report.mode,
        "ruff_version": report.ruff_version,
        "required_ruff_version": report.required_ruff_version,
        "version_source": report.version_source,
        "version_check": report.version_check,
        "files_inspected": list(report.files_inspected),
        "findings": [asdict(f) for f in report.findings],
    }


def finding_line(finding: Finding) -> str:
    """Format one finding for a refusal (path:line:col: CODE message [step: name])."""
    text = f"{finding.path}:{finding.line}:{finding.col}: {finding.code} {finding.message}"
    text += f" [step: {finding.step}]"
    return text + (" [predates this change]" if finding.predates_change else "")


def _version_lines(report: Report) -> list[str]:
    if report.ruff_version is None:
        return []
    line = f"lint gate: linter version used: ruff {report.ruff_version}"
    if report.version_check == "matched":
        line += f" (matches the version CI installs, {report.version_source})"
    if report.version_check == "not_declared":
        line += f"; {report.version_note}"
    return [line]


def _noun(report: Report) -> str:
    return {"staged": "staged files", "files": "named files"}.get(report.mode, "files")


def _ok_lines(report: Report) -> list[str]:
    count = len(report.files_inspected)
    lines = _version_lines(report)
    lines.append(f"lint gate: inspected {count} {_noun(report)}, found no violation CI would reject.")
    if report.mode == "full":  # the whole declared scope: a count is the readable summary
        return lines
    return [*lines, *(f"  {rel}" for rel in report.files_inspected)]


def _refused_lines(report: Report) -> list[str]:
    lines = _version_lines(report)
    lines += [finding_line(f) for f in report.findings]
    files = len({f.path for f in report.findings})
    lines.append(
        f"lint gate: {len(report.findings)} finding(s) in {files} file(s) that CI's required lint "
        "check would also reject; the commit is refused."
    )
    if any(f.predates_change for f in report.findings):
        lines.append(f"lint gate: {PREDATES_NOTE}")
    return lines


def _nothing_lines(report: Report) -> list[str]:
    return [
        f"lint gate: nothing to inspect: 0 of {report.considered} {_noun(report)} are in the "
        "declared lint scope (and admitted by the ruff configuration)."
    ]


def _could_not_lines(report: Report) -> list[str]:
    lines = [f"lint gate: could not check this commit: {report.detail} (reason: {report.reason})"]
    if report.fix:
        lines.append(f"lint gate: {report.fix}")
    return lines


_RENDERERS = {
    co.OUTCOME_OK: _ok_lines,
    co.OUTCOME_REFUSED: _refused_lines,
    co.OUTCOME_NOTHING_TO_INSPECT: _nothing_lines,
    co.OUTCOME_COULD_NOT_CHECK: _could_not_lines,
}


def render_human(report: Report) -> list[str]:
    """The lines a developer reads; the caller prints them, then the RESULT line."""
    return _RENDERERS[report.outcome](report)
