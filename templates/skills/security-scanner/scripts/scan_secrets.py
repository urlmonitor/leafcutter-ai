"""
MODULE: scan_secrets.py
GOAL: Detect secrets, API keys, and high-entropy strings in source files.
BUSINESS CONTEXT: The project manages live Bybit API keys and database credentials.
    A leaked key causes immediate financial loss. This scanner is the primary
    defense against accidental credential commits.
ARCHITECTURE: Standalone script. Accepts file paths as CLI args. Returns exit
    code 0 (clean) or 1 (findings). Reads .security-allowlist from the project
    root (CWD) to suppress known false positives.

# DECISION HISTORY
# - 2026-05-13 15:00 [epic-supervisor/ticket-23]: Initial implementation.
#   Shannon entropy threshold 4.5 chosen to minimize false positives on
#   base64 test data while catching 36+ char API keys.
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
    ("BYBIT_API_KEY", re.compile(
        r"(?i)(bybit|api_key|apikey|api_secret)[^\n]{0,30}['\"][A-Za-z0-9]{30,}['\"]"
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

    Args:
        root: Project root directory containing the .security-allowlist file.

    Returns:
        Set of (rule_id, file_path, line_no_or_star) tuples.
    """
    entries: set[tuple[str, str, str]] = set()
    path = root / _ALLOWLIST_FILE
    if not path.exists():
        return entries
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(":", 2)
        if len(parts) == 3:
            entries.add((parts[0], parts[1], parts[2]))
        elif len(parts) == 2:
            entries.add((parts[0], parts[1], "*"))
    return entries


def _is_suppressed(
    finding: Finding, allowlist: set[tuple[str, str, str]]
) -> bool:
    """Return True if this finding is covered by an allowlist entry.

    The file_path in an allowlist entry may be a bare filename, a relative
    path, or an absolute path. We match if any suffix of the finding's
    file_path equals the allowlist entry (using Path segment matching).

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
            al_path = Path(fp)
            al_parts = al_path.parts
            fp_parts = finding_path.parts
            # Match if allowlist path is a suffix of finding path
            if fp_parts and fp_parts != tuple(fp_parts[-len(al_parts):] if len(fp_parts) >= len(al_parts) else fp_parts):
                # Also try simple name match
                if finding_path.name != al_path.name and finding.file_path != fp:
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
