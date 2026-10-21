"""
MODULE: _approve_support
GOAL: The field-targeted edit, read-back and restore helpers of the approval step (approve_acs.py),
    kept out of that file so it stays under its size limit.
BUSINESS CONTEXT: ACD-300c-4 and its review fixes. The approval step writes readiness, priority and one
    appended amended_by entry in one write per record, then proves the write by reading it back; a write
    that does not read back is undone byte for byte.
ARCHITECTURE: Pure text helpers plus the read-back and restore file operations. Flat sibling module,
    deployed beside approve_acs.py (RULE_CHECK_DEPLOY_MAP, scripts/build_phases_ac_store_rc.py).

DECISION HISTORY:
  - 2026-10-21 [python-coder/ACD-300c-4 review]: Created. set_top_level replaces a top-level scalar line
    whatever its current value, and inserts the line after `id:` (or at the top) when the record has none,
    so a draft record or one without a priority line is approved like a reviewed one (H-1, M-1). The
    read-back also demands the last amended_by entry to be the one just appended (L-4).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional

import yaml

ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def set_top_level(text: str, key: str, value: str, eol: str) -> str:
    """Return *text* with the top-level ``key:`` scalar set to *value*, inserting the line when absent.

    Only the value token is replaced, so a trailing comment survives. A missing key is inserted
    after the ``id:`` line, or at the top of the document when there is none.
    """
    updated, found = re.subn(rf"^{key}:[ \t]*[^\s#]*", f"{key}: {value}", text, count=1, flags=re.MULTILINE)
    if found:
        return updated
    line = f"{key}: {value}{eol}"
    inserted, found = re.subn(r"^(id:[^\r\n]*\r?\n)", lambda m: m.group(1) + line, text, count=1, flags=re.MULTILINE)
    return inserted if found else line + text


def id_matches(path: Path, ac_id: str) -> bool:
    """True when the YAML file at *path* carries ``id: <ac_id>`` (a filename match alone is not enough)."""
    try:
        data = yaml.load(path.read_bytes().decode("utf-8"), Loader=yaml.SafeLoader)
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return False
    return isinstance(data, dict) and data.get("id") == ac_id


def read_back_problem(ac_file: Path, prior: list, priority: Optional[str], new_entry: dict) -> Optional[str]:
    """Re-read *ac_file* and return why its write is not what was meant, or None when it reads back."""
    try:
        data = yaml.load(ac_file.read_bytes().decode("utf-8"), Loader=yaml.SafeLoader)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        return f"write did not re-parse as YAML after promotion: {exc}"
    entries = data.get("amended_by") if isinstance(data, dict) else None
    if not (
        isinstance(entries, list) and entries[:-1] == prior and entries[-1:] == [new_entry] and data.get("readiness") == "approved"
    ):
        return "write did not read back as approved with the earlier amended_by entries intact and the new entry last"
    return None if priority is None or data.get("priority") == priority else "write did not read back with the new priority"


def restore(ac_file: Path, raw_bytes: bytes, problem: str) -> int:
    """Put *raw_bytes* back byte for byte after a write that failed read-back; always returns 1."""
    try:
        ac_file.write_bytes(raw_bytes)
    except OSError as restore_exc:
        print(
            f"ERROR: {ac_file} failed self-validation ({problem}) AND the restore of its original content "
            f"also failed: {restore_exc}. The file on disk may be corrupted — restore it from git.",
            file=sys.stderr,
        )
        return 1
    print(f"ERROR: {ac_file} {problem}; original content restored, promotion aborted", file=sys.stderr)
    return 1
