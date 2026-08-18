"""
MODULE: scan_secrets.py
GOAL: Detect secrets, API keys, and high-entropy strings in source files.
BUSINESS CONTEXT: The project manages live third-party API keys and database credentials.
    A leaked key causes immediate financial loss. This scanner is the primary
    defense against accidental credential commits.
ARCHITECTURE: Standalone script. Accepts file paths as CLI args. Returns exit
    code 0 (clean) or 1 (findings). Reads .security-allowlist from the project
    root (CWD) to suppress known false positives.

# DECISION HISTORY
# - 2026-05-13 15:00 [epic-supervisor/ticket-23]: Initial implementation.
#   Shannon entropy threshold 4.5 chosen to minimize false positives on
#   base64 test data while catching 36+ char API keys. (#TICKETLESS reason=initial-skill-implementation)
# - 2026-06-03 00:00 [ticket-supervisor]: Append tail-tag to initial-implementation DECISION HISTORY entry to satisfy check_documentation hook. (#EPIC-TemplateDocViolations/01)
# - 2026-08-18 12:00 [python-coder]: A zero-segment allowlist file-path
#   field (empty, ".", "./", or whitespace-only) was trivially a
#   segment-suffix of every finding path, so one malformed line could
#   silently suppress a rule (or, with "*:", the whole scanner) repo-wide.
#   Fixed at two layers: `_load_allowlist` now rejects any entry whose
#   file-path field is not the literal "*" and yields zero `Path(...).parts`
#   segments (and any non-blank, non-comment line with fewer than two
#   colon-separated fields), warning on stderr with the allowlist file path,
#   1-based line number, and offending line text, then skipping the line
#   (never raising); `_is_suppressed` independently guards with an
#   `if not al_parts: continue` so the invariant holds for callers that
#   construct allowlist tuples directly. (#GE-113c-3-v)
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path
from typing import NamedTuple


_ALLOWLIST_FILE = Path(".security-allowlist")

# ---------------------------------------------------------------------------
# Secret detection rules
# ---------------------------------------------------------------------------

_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("PRIVATE_KEY", re.compile(r"-----BEGIN\s+(RSA|EC|OPENSSH)\s+PRIVATE KEY-----")),
    ("AWS_KEY", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("EXCHANGE_API_KEY", re.compile(
        r"(?i)(api_key|apikey|api_secret)[^\n]{0,30}['\"][A-Za-z0-9]{30,}['\"]"
    )),
    ("GENERIC_SECRET", re.compile(
        r"(?i)(password|passwd|secret|token|auth_key)\s*[=:]\s*['\"][^'\"]{8,}['\"]"
    )),
]

_ENV_FILENAME_RE = re.compile(r"(^|[\\/])(\.env(\.[^.]+)?|[^.]+\.env)$", re.IGNORECASE)

_ENTROPY_MIN_LEN = 20
_ENTROPY_THRESHOLD = 4.5
_TOKEN_RE = re.compile(r"[A-Za-z0-9+/=_\-]{20,}")


class Finding(NamedTuple):
    """A single secret-scanner finding."""

    rule_id: str
    file_path: str
    line_no: int
    excerpt: str


# ---------------------------------------------------------------------------
# Allowlist
# ---------------------------------------------------------------------------

def _load_allowlist(root: Path) -> set[tuple[str, str, str]]:
    """Load suppression entries from .security-allowlist.

    A file-path field that yields zero `Path(...).parts` segments (empty,
    ".", "./", or whitespace-only — the latter reaches this state only
    because the whole line is stripped before splitting) never suppresses
    anything: repository-wide suppression must be written as the literal
    wildcard "*". Any line whose file-path field is zero-segment, or that
    is non-blank, non-comment, and has fewer than two colon-separated
    fields, is skipped and reported via a WARNING on stderr (never stdout,
    which carries the findings report `check_secrets` consumes). The
    warning names the allowlist file path, the 1-based line number, and the
    verbatim offending line text. Skipping is warn-and-skip, never fatal —
    `check_secrets` runs on every commit, so raising would turn a cosmetic
    typo into a repository-wide commit outage; skipping fails closed
    because the author still sees the finding they were trying to
    suppress. Blank lines and "#" comment lines are valid content and never
    warn. Skipping is per-line: every other, well-formed entry in the same
    file is still loaded and applied.

    Args:
        root: Project root directory containing the .security-allowlist file.

    Returns:
        Set of (rule_id, file_path, line_no_or_star) tuples.
    """
    entries: set[tuple[str, str, str]] = set()
    path = root / _ALLOWLIST_FILE
    if not path.exists():
        return entries
    lines = path.read_text(encoding="utf-8").splitlines()
    for lineno, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(":", 2)
        if len(parts) < 2:
            print(
                f"WARNING: {path}: line {lineno}: malformed allowlist "
                f"entry (missing rule_id:file_path separator), skipping: "
                f"{line!r}",
                file=sys.stderr,
            )
            continue
        file_path = parts[1].strip()
        if file_path != "*" and not Path(file_path).parts:
            print(
                f"WARNING: {path}: line {lineno}: allowlist entry has a "
                f"zero-segment file path and suppresses nothing (write "
                f"'*' for repository-wide suppression), skipping: "
                f"{line!r}",
                file=sys.stderr,
            )
            continue
        if len(parts) == 3:
            entries.add((parts[0], file_path, parts[2]))
        else:
            entries.add((parts[0], file_path, "*"))
    return entries


def _is_suppressed(
    finding: Finding, allowlist: set[tuple[str, str, str]]
) -> bool:
    """Return True if this finding is covered by an allowlist entry.

    The file_path in an allowlist entry may be a bare filename, a relative
    path, or an absolute path. A finding is suppressed only when one of
    three modes holds:
      - wildcard: the allowlist path is the literal "*" (any finding
        matches),
      - exact-path: the allowlist path segments equal the finding path
        segments exactly, or
      - path-suffix: the allowlist path segments are a true
        segment-by-segment suffix of the finding path segments (this also
        covers bare-filename entries, which suppress by basename at any
        depth since a single segment is trivially a 1-segment suffix).

    Basename equality alone is never sufficient when the allowlist entry
    contains a path separator — only a genuine segment-suffix match
    suppresses in that case.

    A zero-segment allowlist path (one whose `Path(...).parts` is empty —
    e.g. an empty string, ".", or "./") never matches: an empty tuple is
    trivially a suffix of every finding path, so honouring it would
    silently suppress the rule (or, with a "*" rule_id, the whole scanner)
    repository-wide. Repository-wide suppression is available only through
    the literal wildcard file path "*", handled separately above. This
    guard is keyed on `Path(...).parts` emptiness, not on a blacklist of
    specific spellings, and is independent of `_load_allowlist`'s
    parse-time rejection — callers (including this module's own test
    suite) may construct allowlist tuples directly, bypassing the loader.

    Args:
        finding: The Finding to check.
        allowlist: Set of suppression tuples from _load_allowlist.

    Returns:
        True if the finding should be suppressed.
    """
    finding_path = Path(finding.file_path)
    for rule_id, fp, lineno in allowlist:
        if rule_id != finding.rule_id and rule_id != "*":
            continue
        if fp != "*":
            al_parts = Path(fp).parts
            if not al_parts:
                continue
            fp_parts = finding_path.parts
            is_suffix_match = len(fp_parts) >= len(al_parts) and (
                al_parts == fp_parts[len(fp_parts) - len(al_parts):]
            )
            if not is_suffix_match:
                continue
        if lineno == "*" or lineno == str(finding.line_no):
            return True
    return False


# ---------------------------------------------------------------------------
# Entropy helper
# ---------------------------------------------------------------------------

def _shannon_entropy(s: str) -> float:
    """Compute Shannon entropy of string s.

    Args:
        s: The string to compute entropy for.

    Returns:
        Shannon entropy value (bits per character).
    """
    if not s:
        return 0.0
    counts: dict[str, int] = {}
    for c in s:
        counts[c] = counts.get(c, 0) + 1
    total = len(s)
    return -sum((n / total) * math.log2(n / total) for n in counts.values())


# ---------------------------------------------------------------------------
# Per-file scanning
# ---------------------------------------------------------------------------

def scan_file(file_path: Path) -> list[Finding]:
    """Scan a single file for secrets.

    Args:
        file_path: Path to the file to scan.

    Returns:
        List of Finding objects for any detected secrets.
    """
    findings: list[Finding] = []
    path_str = str(file_path)

    # Rule: ENV_FILE — never commit .env files
    if _ENV_FILENAME_RE.search(path_str):
        findings.append(Finding("ENV_FILE", path_str, 0, f"Sensitive filename: {file_path.name}"))
        return findings  # Don't scan content of env files further

    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return findings

    lines = text.splitlines()
    for lineno, line in enumerate(lines, start=1):
        # Regex-based rules
        for rule_id, pattern in _RULES:
            if pattern.search(line):
                excerpt = line.strip()[:120]
                findings.append(Finding(rule_id, path_str, lineno, excerpt))

        # Shannon entropy rule
        for token in _TOKEN_RE.findall(line):
            if len(token) >= _ENTROPY_MIN_LEN and _shannon_entropy(token) > _ENTROPY_THRESHOLD:
                excerpt = line.strip()[:120]
                findings.append(Finding("ENTROPY_HIGH", path_str, lineno, excerpt))
                break  # one entropy finding per line is enough

    return findings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan_files(
    file_paths: list[Path], project_root: Path | None = None
) -> list[Finding]:
    """Scan multiple files, applying the allowlist from project_root.

    Args:
        file_paths: List of file paths to scan.
        project_root: Root directory containing .security-allowlist.
            Defaults to CWD.

    Returns:
        List of non-suppressed Finding objects.
    """
    root = project_root or Path.cwd()
    allowlist = _load_allowlist(root)
    all_findings: list[Finding] = []
    for fp in file_paths:
        for finding in scan_file(fp):
            if not _is_suppressed(finding, allowlist):
                all_findings.append(finding)
    return all_findings


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    """CLI entry point.

    Returns:
        Exit code: 0 = clean, 1 = findings found.
    """
    if len(sys.argv) < 2:
        print("Usage: scan_secrets.py <file1> [file2 ...]")
        return 1

    paths = [Path(p) for p in sys.argv[1:]]
    findings = scan_files(paths)

    if not findings:
        return 0

    for f in findings:
        lineno_str = f":{f.line_no}" if f.line_no else ""
        print(f"[{f.rule_id}] {f.file_path}{lineno_str}: {f.excerpt}")

    print(f"\n{len(findings)} secret(s) detected. Add to .security-allowlist to suppress false positives.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
