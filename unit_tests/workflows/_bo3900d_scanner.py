r"""
MODULE: unit_tests/workflows/_bo3900d_scanner.py
GOAL: Test-support scanner for BO-3900d — flag a POSIX-only leading-'/'
    absoluteness test reintroduced into any workflow script, over a set of
    scripts DERIVED from a directory listing rather than hard-coded.
BUSINESS CONTEXT: per BO-3900d.yaml's user decision Q4, this check is a unit
    test only (never a pre-commit hook, never a commit_guardian entry).
    python-coder owns it as test-support code under unit_tests/.
ARCHITECTURE: Text-based on purpose (docs/reference/false-green-mechanisms.md
    M1 — this is why BO-3900d counts for nothing toward BO-3900's own
    coverage). The permitted-home exemption is derived from a PROPERTY of the
    code, never a function-name allowlist: a leading-'/' test is exempt only
    when it sits inside the SAME enclosing `function ... { ... }` block as
    both a drive-letter pattern and a UNC pattern, found by brace-counting
    outward from the match — so renaming the classification function neither
    breaks nor widens the exemption. A "NOT-A-PATH:" comment with non-empty
    reason text, on the flagged line or the line directly above it, is the
    other permitted exemption; an empty or whitespace-only reason is treated
    as absent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_SHAPES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("startsWith-double-quote", re.compile(r'\.startsWith\(\s*"/"\s*\)')),
    ("startsWith-single-quote", re.compile(r"\.startsWith\(\s*'/'\s*\)")),
    ("index-zero", re.compile(r'\[\s*0\s*\]\s*===\s*["\']/["\']')),
    ("charAt-zero", re.compile(r"\.charAt\(\s*0\s*\)\s*===\s*[\"']/[\"']")),
    ("regex-leading-slash-anchor", re.compile(r"/\^\\/")),
)

# A drive-letter character class immediately followed by ':', in either
# letter-order spelling ("[A-Za-z]:" or "[a-zA-Z]:") a classification might
# use.
_DRIVE_LETTER_PATTERN = re.compile(r"\[A-Za-z\]:|\[a-zA-Z\]:")
# Two literal backslashes (a JS UNC prefix, however escaped in source) or two
# literal forward slashes.
_UNC_PATTERN = re.compile(r"\\\\|//")

_NOT_A_PATH_MARKER = re.compile(r"NOT-A-PATH:\s*(\S.*)")


@dataclass
class Finding:
    script: str
    line: int
    expression: str


@dataclass
class ScanResult:
    examined_count: int
    findings: list[Finding] = field(default_factory=list)


def _function_span_around(lines: list[str], match_line_idx: int) -> tuple[int, int] | None:
    """Find the (start, end) 0-based line range of the function enclosing
    `match_line_idx`, by scanning backward for a function declaration and
    then forward counting braces to its matching close. Returns None when no
    enclosing function is found (a top-level statement).
    """
    func_start = None
    for idx in range(match_line_idx, -1, -1):
        if re.match(r"^\s*(async\s+)?function\s+\w+\s*\(", lines[idx]):
            func_start = idx
            break
    if func_start is None:
        return None

    depth = 0
    opened = False
    for idx in range(func_start, len(lines)):
        depth += lines[idx].count("{") - lines[idx].count("}")
        if "{" in lines[idx]:
            opened = True
        if opened and depth <= 0:
            return (func_start, idx)
    return (func_start, len(lines) - 1)


def _has_reasoned_marker(lines: list[str], line_idx: int) -> bool:
    for candidate_idx in (line_idx, line_idx - 1):
        if 0 <= candidate_idx < len(lines):
            m = _NOT_A_PATH_MARKER.search(lines[candidate_idx])
            if m and m.group(1).strip():
                return True
    return False


def _is_exempt_by_shared_classification(lines: list[str], match_line_idx: int) -> bool:
    span = _function_span_around(lines, match_line_idx)
    if span is None:
        return False
    start, end = span
    block_text = "\n".join(lines[start : end + 1])
    return bool(_DRIVE_LETTER_PATTERN.search(block_text)) and bool(
        _UNC_PATTERN.search(block_text)
    )


def scan_workflow_scripts(target_dir: Path) -> ScanResult:
    """Scan every ``*.js`` file directly under `target_dir` for a POSIX-only
    leading-'/' absoluteness test, per BO-3900d's criteria.
    """
    scripts = sorted(target_dir.glob("*.js"))
    findings: list[Finding] = []
    for script_path in scripts:
        text = script_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        for line_idx, line in enumerate(lines):
            for _shape_name, pattern in _SHAPES:
                for m in pattern.finditer(line):
                    if _has_reasoned_marker(lines, line_idx):
                        continue
                    if _is_exempt_by_shared_classification(lines, line_idx):
                        continue
                    findings.append(
                        Finding(
                            script=script_path.name,
                            line=line_idx + 1,
                            expression=m.group(0),
                        )
                    )
    return ScanResult(examined_count=len(scripts), findings=findings)
