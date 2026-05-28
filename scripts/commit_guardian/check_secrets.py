"""
MODULE: check_secrets.py
GOAL: Pre-commit hook — scan staged files for secrets before they are committed.
BUSINESS CONTEXT: Projects using this workflow may store sensitive credentials
    such as API keys, SSH credentials, and database passwords. A single committed
    credential causes immediate security and financial risk. This hook is the last
    line of defense before secrets reach git history.
ARCHITECTURE: Thin wrapper around the security-scanner skill's scan_secrets.py.
    Reads staged files from git, delegates to scan_files(), exits 1 on findings.
    Fast by design: regex + entropy only, no network calls. The path to
    scan_secrets.py is read from commit_guardian.json → security_scanner.scripts_dir
    so that consumer projects can point to their own copy of the scanner without
    editing this file. ENTROPY_HIGH findings are post-filtered via _is_prose_exempt()
    to suppress false positives for TICKET-* and EPIC-* identifiers without requiring
    per-line .security-allowlist entries.

# DECISION HISTORY
# - 2026-05-14 09:00 [TICKET-20260514-Fix_Tooling_Gaps]: Added _is_prose_exempt()
#   helper and ENTROPY_HIGH post-filter to eliminate accreting .security-allowlist
#   entries caused by ticket IDs and EPIC names in audit/retrospective documents.
#   See Deliverable 3 in the ticket body.
# - 2026-05-13 15:00 [epic-supervisor/ticket-23]: Initial implementation.
#   Scope intentionally limited to staged files only — full-repo scan is the
#   job of /security-audit, not the pre-commit hot path.
# - 2026-05-13 02:00 [epic-supervisor]: Parameterised security_scanner.scripts_dir
#   path via commit_guardian.json so the hook is portable across consumer projects.
"""

from __future__ import annotations

import math
import re
import subprocess
import sys
from pathlib import Path

from _resolve_root import find_project_root

_project_root = find_project_root()
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.commit_guardian.config import SECURITY_SCANNER_SCRIPTS_DIR  # noqa: E402

_SKILL_SCRIPTS = _project_root / SECURITY_SCANNER_SCRIPTS_DIR

sys.path.insert(0, str(_SKILL_SCRIPTS))

from scan_secrets import scan_files  # noqa: E402

# ---------------------------------------------------------------------------
# Prose-pattern exemption (ENTROPY_HIGH false-positive suppression)
# ---------------------------------------------------------------------------

# Patterns that identify known-benign high-entropy tokens in prose.
_TICKET_ID_RE = re.compile(r"TICKET-\d{8}-\w+")
_EPIC_NAME_RE = re.compile(r"EPIC-[A-Z]\w+")

# Prose-only file prefixes — entire files are exempt from entropy scanning.
_PROSE_FILE_PREFIXES = (
    "tickets/",
    "tickets\\",
    "docs/retrospectives/",
    "docs\\retrospectives\\",
)

# Mirror of scan_secrets entropy constants (kept in sync with the skill).
_ENTROPY_MIN_LEN = 20
_ENTROPY_THRESHOLD = 4.5
_TOKEN_RE = re.compile(r"[A-Za-z0-9+/=_\-]{20,}")


def _shannon_entropy(s: str) -> float:
    """Compute Shannon entropy of a string.

    Args:
        s: The string to compute entropy for.

    Returns:
        Shannon entropy value (bits per character); 0.0 for empty string.
    """
    if not s:
        return 0.0
    counts: dict[str, int] = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    total = len(s)
    return -sum((n / total) * math.log2(n / total) for n in counts.values())


def _is_prose_exempt(line: str, file_path: Path) -> bool:
    """Return True when the line/file qualifies for ENTROPY_HIGH exemption.

    Exemption rules (checked in order):
    1. File is under tickets/ or docs/retrospectives/ — entire file is prose-only;
       entropy scan would only produce false positives.
    2. The line contains a TICKET-YYYYMMDD-* or EPIC-[A-Z]* token AND after
       removing those known-benign tokens, no remaining token exceeds the entropy
       threshold.  This allows a line like "see TICKET-20260514-Foo for context"
       to pass, while a line like "TICKET-20260514-Foo apikey=aB3kXm9..." is still
       flagged because the apikey token survives the removal.

    Note: This function only suppresses ENTROPY_HIGH findings.  Regex-based
    rules (PRIVATE_KEY, AWS_KEY, BYBIT_API_KEY, GENERIC_SECRET) are never
    suppressed by this function.

    Args:
        line: The source line being evaluated.
        file_path: Absolute or relative path to the file containing the line.

    Returns:
        True when the line should be exempt from ENTROPY_HIGH detection.
    """
    # Rule 1: prose-only file path
    path_str = str(file_path).replace("\\", "/")
    for prefix in _PROSE_FILE_PREFIXES:
        normalised_prefix = prefix.replace("\\", "/")
        if path_str.startswith(normalised_prefix) or ("/" + normalised_prefix) in path_str:
            return True

    # Rule 2: line contains a TICKET-* or EPIC-* token — check residual entropy
    has_known_token = bool(_TICKET_ID_RE.search(line) or _EPIC_NAME_RE.search(line))
    if not has_known_token:
        return False

    # Remove the known-benign patterns, then check for remaining high-entropy tokens
    scrubbed = _TICKET_ID_RE.sub("", line)
    scrubbed = _EPIC_NAME_RE.sub("", scrubbed)
    for token in _TOKEN_RE.findall(scrubbed):
        if len(token) >= _ENTROPY_MIN_LEN and _shannon_entropy(token) > _ENTROPY_THRESHOLD:
            # A genuine high-entropy token survives — do NOT exempt
            return False

    return True


def _filter_prose_findings(findings: list, file_path: Path) -> list:
    """Remove ENTROPY_HIGH findings that are prose-exempt for the given file.

    Regex-based rule findings (rule_id != 'ENTROPY_HIGH') are never removed.

    Args:
        findings: List of Finding namedtuples from scan_files().
        file_path: The file that was scanned (used for file-level exemption).

    Returns:
        Filtered list with prose-exempt ENTROPY_HIGH findings removed.
    """
    result = []
    for finding in findings:
        if finding.rule_id == "ENTROPY_HIGH" and _is_prose_exempt(
            finding.excerpt, file_path
        ):
            continue
        result.append(finding)
    return result


def _get_staged_files() -> list[Path]:
    """Return a list of staged files from git diff --cached.

    Returns:
        List of Path objects for currently staged files.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMRT"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [
        Path(line)
        for line in result.stdout.splitlines()
        if line.strip() and Path(line.strip()).exists()
    ]


def main() -> int:
    """Pre-commit hook entry point.

    Returns:
        Exit code: 0 = clean, 1 = secrets found (blocks commit).
    """
    staged = _get_staged_files()
    if not staged:
        return 0

    raw_findings = scan_files(staged, project_root=_REPO_ROOT)

    # Post-filter ENTROPY_HIGH findings for known-benign prose patterns.
    # Regex-based findings (PRIVATE_KEY, AWS_KEY, etc.) are never filtered.
    findings = []
    for fp in staged:
        fp_findings = [f for f in raw_findings if f.file_path == str(fp)]
        findings.extend(_filter_prose_findings(fp_findings, fp))

    if not findings:
        return 0

    print("\n[check_secrets] SECRETS DETECTED — commit blocked\n")
    for f in findings:
        lineno_str = f":{f.line_no}" if f.line_no else ""
        print(f"  [{f.rule_id}] {f.file_path}{lineno_str}")
        print(f"    {f.excerpt[:100]}")
    print(
        f"\n{len(findings)} finding(s). To suppress a false positive, add an entry to "
        f".security-allowlist:\n"
        f"  {findings[0].rule_id}:{findings[0].file_path}:{findings[0].line_no}"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
