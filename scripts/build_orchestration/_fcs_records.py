"""
MODULE: scripts/build_orchestration/_fcs_records.py
GOAL: Read-only helpers for finalize_closable_set.py -- which paths are ticket or acceptance-
    criterion records, how to read a record's status without a YAML round-trip, how to find a
    ticket's source criterion, and the canonical digest of a closable set.
BUSINESS CONTEXT: BO-400e-3-ii .. -vi. Finalization may close only what the finishing branch was
    built to deliver; the set it may close is computed here, not by an agent reading prose.
ARCHITECTURE: Stdlib plus PyYAML. Pure functions over text and paths; the only I/O is reading a
    record file. Shared by _fcs_derive.py (which records may close) and _fcs_close.py (closing
    them and proving nothing else changed).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

AC_ROOT = "docs/acceptance-criteria"
TICKET_ROOT = "tickets"
_STATUS_LINE = re.compile(r"^status:[ \t]*(.*?)[ \t]*$", re.MULTILINE)
_WORK_STATUS_LINE = re.compile(r"^work_status:[ \t]*(.*?)[ \t]*$", re.MULTILINE)
_NOT_RECORDS = frozenset({"Master_Plan.md", "README.md", "index.yaml"})


def is_ticket_path(rel: str) -> bool:
    """True for a repo-relative ticket markdown path (Master_Plan and README excluded)."""
    return (
        rel.startswith(TICKET_ROOT + "/")
        and rel.endswith(".md")
        and rel.rsplit("/", 1)[-1] not in _NOT_RECORDS
    )


def is_ac_path(rel: str) -> bool:
    """True for a repo-relative acceptance-criterion YAML path (index.yaml excluded)."""
    return (
        rel.startswith(AC_ROOT + "/")
        and rel.endswith(".yaml")
        and rel.rsplit("/", 1)[-1] not in _NOT_RECORDS
    )


def _unquote(value: str) -> str:
    """Strip one pair of matching quotes from a scalar read off a status line."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def frontmatter_block(text: str) -> str:
    """The YAML text between a ticket's first two '---' delimiters ('' when absent)."""
    if not text.startswith("---"):
        return ""
    parts = text.split("---", 2)
    return parts[1] if len(parts) >= 3 else ""


def ticket_status_of(text: str) -> str | None:
    """The ticket's frontmatter ``status:`` value, None when the line is absent."""
    match = _STATUS_LINE.search(frontmatter_block(text))
    return _unquote(match.group(1)) if match else None


def ac_work_status_of(text: str) -> str | None:
    """The record's column-0 ``work_status:`` value, None when the line is absent."""
    match = _WORK_STATUS_LINE.search(text)
    return _unquote(match.group(1)) if match else None


def read_ticket(path: Path) -> dict | None:
    """Parse a ticket's frontmatter into a dict; None when unreadable or not a mapping."""
    try:
        text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(frontmatter_block(text))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        logger.warning("cannot read ticket %s: %s", path, exc)
        return None
    return data if isinstance(data, dict) else None


def ticket_record_status(data: dict) -> str:
    """A ticket's status; an absent one reads as todo, as set_ticket_status.py reads it."""
    return str(data.get("status") or "todo")


def _ac_candidates(ac_root: Path, ac_id: str) -> list[Path]:
    """Files that may hold *ac_id*: by file stem first, else every YAML naming it on an id line."""
    named = sorted(ac_root.rglob(f"{ac_id}.yaml"))
    if named:
        return named
    pattern = re.compile(rf"^id:[ \t]*['\"]?{re.escape(ac_id)}['\"]?[ \t]*$", re.MULTILINE)
    found = []
    for path in sorted(ac_root.rglob("*.yaml")):
        try:
            if pattern.search(path.read_text(encoding="utf-8")):
                found.append(path)
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("cannot scan %s for %s: %s", path, ac_id, exc)
    return found


def find_ac_record(worktree: Path, ac_id: str) -> tuple[str, str] | None:
    """(repo-relative path, work_status) of the criterion *ac_id*, None when it is not in the store."""
    ac_root = worktree / AC_ROOT
    if not ac_root.is_dir():
        return None
    for path in _ac_candidates(ac_root, ac_id):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("cannot read %s: %s", path, exc)
            continue
        return path.relative_to(worktree).as_posix(), ac_work_status_of(text) or "todo"
    return None


def set_digest(records: list[dict]) -> str:
    """sha256 hex of the canonical JSON of the records array (the set's identity)."""
    canonical = json.dumps(records, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def listing_text(records: list[dict]) -> str:
    """The ready-to-show list: a counts header, then '<id>  <path>  <status>' per record."""
    tickets = sum(1 for r in records if r["kind"] == "ticket")
    lines = [f"{tickets} ticket(s), {len(records) - tickets} acceptance criteria"]
    lines.extend(f"{r['id']}  {r['path']}  {r['status']}" for r in records)
    return "\n".join(lines)


# DECISION HISTORY
# ================================================================================
# - 2026-10-16 12:00 [python-coder]: Created shared record helpers for the closable-set CLI. (#BO-400e/3-ii)
