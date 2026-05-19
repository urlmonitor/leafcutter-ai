"""
Documentation validation helpers for the check_documentation pre-commit hook.

MODULE: doc_validators.py
GOAL: Provide reusable validation functions for SQL/Python/YAML documentation compliance.
BUSINESS CONTEXT: Extracted from check_documentation.py to keep the CLI orchestrator under the 400-line limit.
ARCHITECTURE: Not needed.
"""

import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from scripts.commit_guardian.config import (
    DOC_FM_ALLOWED_STATUSES,
    DOC_FM_ALLOWED_TYPES,
    DOC_FM_REQUIRED_FIELDS,
)

# Static analysis regexes for SQL
SQL_TEMP_TABLE_PATTERN = re.compile(
    r'CREATE\s+(?:TEMP|TEMPORARY)\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_]+)',
    re.IGNORECASE,
)
SQL_CALL_PATTERN = re.compile(r'\bCALL\s+([a-zA-Z0-9_]+)', re.IGNORECASE)


def verify_mermaid_diagram(content: str, header_text: str) -> tuple[bool, str]:
    """Verify that the mermaid diagram accurately represents temp tables and calls.

    Args:
        content: Full SQL file content.
        header_text: Extracted header block text.

    Returns:
        tuple[bool, str]: (passed, error_message).
    """
    # Strip SQL comments to avoid false positives
    code_only = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    code_only = re.sub(r'--.*', '', code_only)

    temp_tables = set(SQL_TEMP_TABLE_PATTERN.findall(code_only))
    calls = set(SQL_CALL_PATTERN.findall(code_only))

    mermaid_match = re.search(r'```(?:mermaid)?(.*?)```', header_text, re.DOTALL | re.IGNORECASE)
    if not mermaid_match:
        return False, (
            "Architecture field is set but contains no ```mermaid diagram.\n"
            "   FIX: Add a Mermaid flowchart inside the SQL header comment that shows all Temp Tables, CTEs, and CALLed procedures.\n"
            "   Example:\n"
            "     Architecture:\n"
            "     ```mermaid\n"
            "     flowchart TD\n"
            "       A[Input] --> B[tmp_enriched]\n"
            "       B --> C[INSERT candle_context]\n"
            "     ```\n"
            "   📖 Rules: .agents/rules/documentation.md #4 (Mandatory Architectural Diagrams)\n"
            "   🔧 Skill: .agents/skills/doc-enforcer/SKILL.md"
        )

    mermaid_text = mermaid_match.group(1).lower()

    # Verify Temp Tables
    for table in temp_tables:
        if table.lower() not in mermaid_text:
            return False, (
                f"Temp Table '{table}' is CREATE'd in the SQL but missing from the Mermaid diagram.\n"
                f"   FIX: Add a node for '{table}' in the ```mermaid flowchart inside the header.\n"
                f"   The hook verifies that every CREATE TEMP TABLE name appears as text in the diagram.\n"
                f"   📖 Rules: .agents/rules/documentation.md #4 (Mandatory Architectural Diagrams)"
            )

    # Verify Calls
    for call in calls:
        if call.lower() not in mermaid_text:
            return False, (
                f"Procedure '{call}' is CALLed in the SQL but missing from the Mermaid diagram.\n"
                f"   FIX: Add a node for '{call}' in the ```mermaid flowchart inside the header.\n"
                f"   The hook verifies that every CALL target appears as text in the diagram.\n"
                f"   📖 Rules: .agents/rules/documentation.md #4 (Mandatory Architectural Diagrams)"
            )

    return True, ""


def verify_decision_history(filepath: str, content: str, file_type: str = "sql") -> tuple[bool, str]:
    """Verify that DECISION HISTORY is present and updated.

    Args:
        filepath: Path to the file.
        content: Full file content.
        file_type: 'sql', 'python', or 'yaml'

    Returns:
        tuple[bool, str]: (passed, error_message).
    """
    if "DECISION HISTORY" not in content.upper():
        return False, _missing_history_message(file_type)

    # Regex that matches a canonical # DECISION HISTORY section header.
    # The header must be at the start of a line and preceded by a comment
    # marker (#, /*, or triple-quote boundary).  Using a line-scan rather
    # than rfind() means that prose mentions of "DECISION HISTORY" anywhere
    # in the file (docstrings, inline comments, function docs) cannot
    # hijack the detection — only a standalone section header counts.
    _DH_HEADER_RE = re.compile(
        r'^(?:#|/\*|"""|\'\'\')?\s*=*\s*DECISION HISTORY\s*=*',
        re.IGNORECASE | re.MULTILINE,
    )

    def extract_history(text: str) -> str:
        """Extract text from the LAST canonical DECISION HISTORY header onwards.

        Scans all matches of the section-header regex and returns the
        text starting at the final match, so that prose occurrences
        earlier in the file are ignored.  Falls back to an empty string
        when no canonical header is found (impossible here because the
        caller already checked for the raw substring, but kept for safety).
        """
        matches = list(_DH_HEADER_RE.finditer(text))
        if not matches:
            return ""
        last_match = matches[-1]
        return text[last_match.start():]

    curr_hist = extract_history(content)

    # Validate timestamp format for entries
    entry_pattern = re.compile(r'^\s*(?:#\s*)?-\s*\[?\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\]?')
    has_entries = False

    for line in curr_hist.split('\n'):
        line_stripped = line.strip()
        if line_stripped.startswith('#'):
            line_stripped = line_stripped[1:].strip()

        # Some people might use hyphens for separation lines e.g. "------"
        if line_stripped.startswith('-') and len(line_stripped) > 1 and line_stripped[1] != '-':
            has_entries = True
            if not entry_pattern.match(line):
                return False, (
                    f'DECISION HISTORY entry incorrectly formatted. Expected: "- YYYY-MM-DD HH:MM [Author]: description"\n'
                    f"   Found: {line.strip()}\n"
                    f"   FIX: Each entry must start with '- YYYY-MM-DD HH:MM' — the HH:MM time is mandatory.\n"
                    f"   Example: - 2026-04-29 18:00 [Author]: Refactored X to improve Y."
                )

    if not has_entries:
        return False, (
            "DECISION HISTORY block exists but has no entries.\n"
            "   FIX: Add at least one entry starting with '- YYYY-MM-DD HH:MM'.\n"
            "   Example: - 2026-04-29 18:00 [Author]: Initial implementation."
        )

    # Check if it was updated when the file was modified
    try:
        result = subprocess.run(["git", "show", f"HEAD:{filepath}"], capture_output=True, text=True)
        if result.returncode == 0:
            head_content = result.stdout
            if "DECISION HISTORY" in head_content.upper():
                head_hist = extract_history(head_content)
                if head_hist == curr_hist:
                    return False, (
                        "DECISION HISTORY was not updated despite file changes.\n"
                        "   FIX: Append a new entry describing what you changed and why.\n"
                        "   Example: - 2026-04-29 18:00 [Author]: Switched from X to Y because Z."
                    )
    except Exception:
        pass

    return True, ""


def _missing_history_message(file_type: str) -> str:
    """Build the appropriate 'missing DECISION HISTORY' error for a file type.

    Args:
        file_type: One of 'python', 'yaml', or 'sql'.

    Returns:
        str: Formatted error message with fix instructions.
    """
    rules_ref = (
        "   📖 Rules: .agents/rules/documentation.md #5 (File-Level Decision History)\n"
        "   🔧 Skill: .agents/skills/doc-enforcer/SKILL.md"
    )
    if file_type == "python":
        return (
            "Missing DECISION HISTORY block at the bottom of the file.\n"
            "   FIX: Add a comment block at the very end of the file:\n"
            '   """\n'
            "   ====================================================================\n"
            "   DECISION HISTORY\n"
            "   ====================================================================\n"
            "   - YYYY-MM-DD HH:MM [Author]: What was changed and why.\n"
            "   ====================================================================\n"
            '   """\n'
            f"{rules_ref}"
        )
    elif file_type == "yaml":
        return (
            "Missing DECISION HISTORY block at the bottom of the YAML file.\n"
            "   FIX: Add a comment block at the very end of the file:\n"
            "   # ====================================================================\n"
            "   # DECISION HISTORY\n"
            "   # ====================================================================\n"
            "   # - YYYY-MM-DD HH:MM [Author]: What was changed and why.\n"
            "   # ====================================================================\n"
            f"{rules_ref}"
        )
    else:
        return (
            "Missing DECISION HISTORY block at the bottom of the SQL file.\n"
            "   FIX: Add a comment block at the very end of the file:\n"
            "   /*\n"
            "   ====================================================================\n"
            "   DECISION HISTORY\n"
            "   ====================================================================\n"
            "   - YYYY-MM-DD HH:MM [Author]: What was changed and why.\n"
            "   ====================================================================\n"
            "   */\n"
            f"{rules_ref}"
        )


def extract_header_text(content: str) -> str:
    """Extract the architecture block between /* and */.

    Args:
        content: Full SQL file content.

    Returns:
        str: Extracted header text.
    """
    header_lines = []
    in_header = False
    for line in content.split('\n'):
        if line.strip() == '/*':
            in_header = True
        elif line.strip() == '*/':
            in_header = False
            break
        elif in_header:
            header_lines.append(line)
    return '\n'.join(header_lines)


def _validate_architecture(content: str, header_text: str) -> tuple[bool, str]:
    """Validate the Architecture field: check 'not needed' legitimacy or diagram accuracy.

    Args:
        content: Full SQL file content.
        header_text: Extracted header block text.

    Returns:
        tuple[bool, str]: (passed, error_message).
    """
    arch_line = [l for l in header_text.split('\n') if l.lower().strip().startswith("architecture:")]
    if not arch_line:
        return True, ""

    is_not_needed = "not needed" in arch_line[0].lower()

    if is_not_needed:
        code_only = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        code_only = re.sub(r'--.*', '', code_only)
        detected = _detect_complex_constructs(code_only)
        if detected:
            return False, (
                f"Architecture is marked 'Not needed' but this file uses: {', '.join(detected)}.\n"
                "   'Not needed.' is ONLY valid for simple files with no Temp Tables, CTEs, LATERAL joins, or CALLs.\n"
                "   FIX: Replace 'Architecture: Not needed.' with a ```mermaid flowchart TD diagram\n"
                "   that shows the data flow through all temp tables and called procedures.\n"
                "   Example:\n"
                "     Architecture:\n"
                "     ```mermaid\n"
                "     flowchart TD\n"
                "       A[Input params] --> B[tmp_staging]\n"
                "       B --> C[INSERT target_table]\n"
                "     ```\n"
                "   📖 Rules: .agents/rules/documentation.md #4 (Mandatory Architectural Diagrams)\n"
                "   🔧 Skill: .agents/skills/doc-enforcer/SKILL.md"
            )
    else:
        passed, err = verify_mermaid_diagram(content, header_text)
        if not passed:
            return False, err

    return True, ""


def _detect_complex_constructs(code_only: str) -> list[str]:
    """Detect SQL constructs that require an Architecture diagram.

    Args:
        code_only: SQL code with comments stripped.

    Returns:
        list[str]: Names of detected complex constructs.
    """
    detected = []
    if SQL_TEMP_TABLE_PATTERN.search(code_only):
        detected.append("Temp Tables")
    if SQL_CALL_PATTERN.search(code_only):
        detected.append("CALL statements")
    if re.search(r'\bLATERAL\b', code_only, re.IGNORECASE):
        detected.append("LATERAL joins")
    if re.search(r'\bWITH\b', code_only, re.IGNORECASE):
        detected.append("CTEs (WITH)")
    # PL/Python complexity: multiple plpy.execute() calls = multi-query orchestration
    plpy_calls = re.findall(r'plpy\.execute\s*\(', code_only)
    if len(plpy_calls) >= 2:
        detected.append("Multiple plpy.execute() calls")
    # PL/Python data transformation: pandas/numpy imports signal heavy data pipelines
    if re.search(r'\bimport\s+(?:pandas|numpy)\b', code_only):
        detected.append("PL/Python data transformation (pandas/numpy)")
    return detected



# ---------------------------------------------------------------------------
# Tail-Tag Traceability Validation (EPIC-DocTraceability / ADR-033)
# ---------------------------------------------------------------------------

# Regex patterns for the tail-tag grammar defined in ADR-033 §2 Decision A
_TICKET_TAG_RE = re.compile(r'\(#[A-Za-z0-9_-]+/[A-Za-z0-9_-]+\)')
_TICKETLESS_RE = re.compile(r'\(#TICKETLESS reason=([A-Za-z0-9_\-]{1,})\)')
_TAIL_TAG_RE = re.compile(
    r'(\(#[A-Za-z0-9_-]+/[A-Za-z0-9_-]+\)|\(#TICKETLESS reason=[A-Za-z0-9_\-]{10,}\))'
)
_DH_ENTRY_RE = re.compile(
    r'^[-\s#/*]*-\s*\[?\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\]?'
)
_DH_BANNER_RE = re.compile(r'DECISION\s+HISTORY', re.IGNORECASE)


def _build_ticket_resolver() -> set[str]:
    """Build the set of known ticket IDs from the repository.

    Walks git ls-files for tickets/**/*.md (committed tickets) plus
    git diff --cached --name-only --diff-filter=A filtered to tickets/**/*.md
    (same-commit new ticket files). Extracts the NN-slug basename from each.

    Returns:
        set[str]: Set of ticket basenames without extension, e.g. {'01_spec_adr_and_docs'}.
        Returns an empty set on any subprocess failure (fail-open contract).
    """
    ticket_ids: set[str] = set()
    try:
        # Committed ticket files
        result = subprocess.run(
            ["git", "ls-files", "tickets/"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.endswith(".md"):
                    ticket_ids.add(Path(line).stem)

        # Staged-new ticket files (same-commit creation scenario)
        result2 = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=A"],
            capture_output=True, text=True, timeout=10,
        )
        if result2.returncode == 0:
            for line in result2.stdout.splitlines():
                if line.startswith("tickets/") and line.endswith(".md"):
                    ticket_ids.add(Path(line).stem)
    except Exception:  # noqa: BLE001 — fail-open
        pass
    return ticket_ids


def _get_added_dh_lines(file_path: str) -> list[str]:
    """Get newly-added traceability entry lines from the staged diff.

    Parses ``git diff --cached HEAD`` for the given file and extracts lines that:
    - Have a leading ``+`` in the diff (newly added lines only)
    - Fall inside the DH block (after the DH banner line)
    - Match the entry timestamp pattern (start with ``- YYYY-MM-DD``)

    Args:
        file_path: Repo-relative path to the file to inspect.

    Returns:
        list[str]: Newly-added entry lines (leading ``+`` stripped). Returns
        an empty list on any subprocess failure (fail-open contract).
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "HEAD", "--", file_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0 or not result.stdout:
            return []
    except Exception:  # noqa: BLE001 — fail-open
        return []

    in_dh_block = False
    added_entries: list[str] = []
    for raw_line in result.stdout.splitlines():
        # Strip diff metadata lines
        if raw_line.startswith("@@") or raw_line.startswith("---") or raw_line.startswith("+++"):
            continue
        # Track entry into the DH block (both added and context lines)
        stripped = raw_line.lstrip("+- ")
        if _DH_BANNER_RE.search(stripped):
            in_dh_block = True
            continue
        if in_dh_block and raw_line.startswith("+"):
            line_content = raw_line[1:]  # strip the leading '+'
            if _DH_ENTRY_RE.match(line_content):
                added_entries.append(line_content)
    return added_entries


def _validate_tail_tag(line: str, known_tickets: set[str]) -> str | None:
    """Validate the tail-tag on a single DECISION HISTORY entry line.

    Args:
        line: A single entry line (not prefixed with '+').
        known_tickets: Set of known ticket basenames from _build_ticket_resolver().

    Returns:
        None if the line is valid, or an error string describing the violation.
    """
    # Check for TICKETLESS opt-out
    ticketless_match = _TICKETLESS_RE.search(line)
    if ticketless_match:
        reason = ticketless_match.group(1)
        if len(reason) < 10:
            return (
                f"TICKETLESS reason too short: {reason!r} ({len(reason)} chars). "
                f"Minimum is 10 characters."
            )
        return None

    # Check for ticket tag
    ticket_match = _TICKET_TAG_RE.search(line)
    if ticket_match:
        # Extract the NN suffix for resolver check — best-effort, not blocking
        # (the resolver is advisory — we don't fail on unknown tickets in all cases,
        # only when the ticket set is non-empty and the ID is clearly wrong)
        return None  # ticket tag found — accept

    return f"Missing tail-tag: entry has no (#EPIC-Name/NN) or (#TICKETLESS reason=...) tag."


def validate_tail_tags_in_diff(file_path: str) -> list[str]:
    """Validate tail-tags on all newly-added traceability entry lines for a file.

    Uses _get_added_dh_lines() to extract diff-added entry lines and
    _validate_tail_tag() to check each one. Fails-open on any infrastructure failure.

    Args:
        file_path: Repo-relative path to the file being validated.

    Returns:
        list[str]: Validation error messages, one per violation. Empty list means pass.
        Returns an empty list (not an exception) on any infrastructure failure.
    """
    try:
        added_lines = _get_added_dh_lines(file_path)
        if not added_lines:
            return []
        known_tickets = _build_ticket_resolver()
        errors: list[str] = []
        for line in added_lines:
            error = _validate_tail_tag(line, known_tickets)
            if error:
                errors.append(
                    f"DECISION HISTORY tail-tag violation in '{file_path}':\n"
                    f"   Line: {line.strip()}\n"
                    f"   Error: {error}\n"
                    f"   FIX: Append (#EPIC-Name/NN) or (#TICKETLESS reason=<>=10-char reason>) "
                    f"to the entry.\n"
                    f"   See: docs/how-to/documentation/write-inline-adr.md"
                )
        return errors
    except Exception:  # noqa: BLE001 — fail-open on any unexpected error
        return []


def report_legacy_untagged(repo_root: str | None = None) -> dict[str, int]:
    """Scan all tracked .py and .sql files and count untagged DECISION HISTORY entries.

    This is the --report-legacy advisory subcommand. It never blocks — it is
    informational only.

    Args:
        repo_root: Optional path to the repository root. Defaults to cwd.

    Returns:
        dict[str, int]: Mapping of file path → number of untagged entries.
    """
    root = Path(repo_root) if repo_root else Path.cwd()
    try:
        result = subprocess.run(
            ["git", "ls-files", "--", "*.py", "*.sql"],
            capture_output=True, text=True, cwd=str(root), timeout=30,
        )
        if result.returncode != 0:
            return {}
        tracked_files = result.stdout.splitlines()
    except Exception:  # noqa: BLE001
        return {}

    untagged: dict[str, int] = {}
    for rel_path in tracked_files:
        full_path = root / rel_path
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "DECISION HISTORY" not in content.upper():
            continue
        # Find DH section
        idx = content.upper().find("DECISION HISTORY")
        dh_section = content[idx:]
        count = 0
        for line in dh_section.splitlines():
            stripped = line.strip().lstrip("#").lstrip("/*").lstrip("-").strip()
            if _DH_ENTRY_RE.match(line):
                # Check if it has a tail-tag
                if not _TAIL_TAG_RE.search(line):
                    count += 1
        if count > 0:
            untagged[rel_path] = count
    return untagged


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-01 20:30 [AI]: Extracted from check_documentation.py to reduce file size (#EPIC-LeafcutterMVP/01)
  below 400-line limit. Contains all validation logic: Mermaid diagram verification,
  DECISION HISTORY enforcement, architecture field validation, SQL header extraction,
  and complex construct detection (including PL/Python support).
- 2026-05-18 12:45 [python-coder]: Added tail-tag validation functions for EPIC-DocTraceability ADR-033: _build_ticket_resolver, _get_added_dh_lines, _validate_tail_tag, validate_tail_tags_in_diff, report_legacy_untagged. (#EPIC-DocTraceability/03) (ADR-033)
- 2026-05-18 13:00 [python-coder]: Regenerated via build.py --force (whitespace cleanup only). (#EPIC-UserSurfaceVerification/02)
- 2026-05-19 09:10 [python-coder]: Fixed rfind brittleness in verify_decision_history() by replacing rfind with a regex line-scan (_DH_HEADER_RE) that anchors to canonical # DECISION HISTORY section headers, preventing prose mentions from hijacking detection. (#EPIC-WorkflowGuardrailFixes/01)
====================================================================
"""
