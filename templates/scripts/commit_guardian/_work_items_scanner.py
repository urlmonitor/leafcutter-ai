"""
Work-item namespace walk for the whole-collection uniqueness pass.

MODULE: _work_items_scanner
GOAL: Walk the four lifecycle folders declared in ``tickets/ticket_lifecycle.json``
    and produce a NamespaceVerdict naming every work-item identifier
    ("TICKET-*.md" basename) held by two or more of those folders, together
    with each claimant's own declared lifecycle status. Split out of
    check_identifier_uniqueness.py (alongside the sibling
    _uniqueness_scanners.py) to keep every new file under this project's
    400-line-per-new-file limit.
BUSINESS CONTEXT: GE-122a-2 ("one work item cannot exist as two copies free
    to disagree about its state") is the sibling failure shape to GE-122a-1
    ("two unrelated artifacts claim one number"): a reader who follows a
    work-item identifier and lands on two files that disagree has suffered
    the same loss of trust. This module is EXTRACT-AND-HARDEN, not
    greenfield: templates/hooks/check_ticket_state_integrity.py already
    performs basename-duplicate-across-lifecycle-folders detection, but as a
    post-merge, always-exit-0, registered-nowhere watchdog. This module is
    the canonical, ENFORCED (failing) implementation of that same rule,
    feeding the same shared verdict object as GE-122a-1 (GE-122d-1: one rule,
    evaluated once, not two independent definitions of it). See
    templates/hooks/check_ticket_state_integrity.py's own module docstring
    for the disposition of that legacy script now that this module exists.
ARCHITECTURE: Two-step walk, both pure filesystem plus one JSON read:
      - The lifecycle folder list is READ from ``tickets/ticket_lifecycle.json``
        (never restated as a Python literal), per this AC's own
        it_requirement. The ``tickets/`` root itself is deliberately NOT a
        lifecycle folder: a ticket sitting there is unenrolled, not
        uniquely-held, and must never be silently counted as "exactly one
        lifecycle folder".
      - Each lifecycle folder is walked NON-recursively for "TICKET-*.md"
        basenames (never a bare "*.md" basename, which floods the report
        with every epic's Master_Plan.md, and never a recursive walk, which
        would also pick up ordinal-prefixed epic sub-tickets like
        "01_TICKET-...md" that merely share a numeric prefix with an
        unrelated work item -- the exact false-positive class this AC's
        it_requirements call out). A per-file frontmatter read failure is a
        could-not-read condition (logged at WARNING, never a silent skip)
        per CLAUDE.md Rules 1-4, but still counts toward inspected_count
        since the file was genuinely walked.

DOC_LINKS:
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122a-2.yaml
  - tickets/ticket_lifecycle.json

DECISION HISTORY:
  - 2026-08-18 [python-coder/GE-122a-2]: Created. Extracted the
    duplicate-basename-across-lifecycle-folders detection already present
    (dead, always-exit-0) in templates/hooks/check_ticket_state_integrity.py
    into this module as the canonical, ENFORCED implementation feeding
    check_identifier_uniqueness.run_uniqueness_pass's fourth namespace,
    "work-items". Deliberately a fresh implementation rather than a runtime
    import of check_ticket_state_integrity.py's helpers: that script deploys
    to a different directory (.claude/hooks/) than this one
    (scripts/commit_guardian/), and cross-directory imports between the two
    deploy layouts are exactly the ModuleNotFoundError trap CLAUDE.md's "New
    Hook / Gate Dependencies Must Be in the Build Deploy-Manifest" warns
    against.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from _uniqueness_types import Finding, NamespaceVerdict  # type: ignore[import]

_HOOK_PREFIX = "[check_identifier_uniqueness]"

_TICKET_STATUS_RE = re.compile(r"^status:\s*(.+)$", re.MULTILINE)


def _read_lifecycle_folder_names(lifecycle_config_path: Path) -> list[str]:
    """Read the lifecycle folder names from ``tickets/ticket_lifecycle.json``.

    Reads the folder list rather than hard-coding it, per this AC's own
    it_requirement that the allowed-status-per-folder mapping -- and, by
    extension, which folders count as lifecycle locations -- must be read
    from the config file, never restated in code. The ``tickets/`` root
    itself is never included: it is not one of the declared folder entries.

    Args:
        lifecycle_config_path: Path to ``tickets/ticket_lifecycle.json``.

    Returns:
        List of folder basenames (e.g. ``["00_inbox", "01_todo", "99_done",
        "99_rejected"]``), or an empty list if the config is missing,
        unreadable, or unparsable (fail-open: nothing to walk rather than a
        crash).
    """
    try:
        content = lifecycle_config_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: cannot read {lifecycle_config_path}: {exc}",
            file=sys.stderr,
        )
        return []

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: cannot parse {lifecycle_config_path}: {exc}",
            file=sys.stderr,
        )
        return []

    folders = data.get("folders", [])
    return [Path(entry["path"]).name for entry in folders if entry.get("path")]


def _read_ticket_status(ticket_path: Path) -> str | None:
    """Read the declared ``status:`` frontmatter value from a work-item file.

    Fails open per file (returns None so the caller can still count the file
    as inspected) but ALWAYS logs a WARNING on a could-not-read or
    could-not-parse condition -- per CLAUDE.md Rules 1-4 and this AC's own
    it_requirement that a work item whose frontmatter cannot be parsed is a
    could-not-read condition, not a silent skip.

    Args:
        ticket_path: Path to the ticket Markdown file.

    Returns:
        The raw declared status string (e.g. "todo", "done"), or None if the
        file is unreadable or its frontmatter has no status field.
    """
    try:
        content = ticket_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"{_HOOK_PREFIX} WARNING: cannot read {ticket_path}: {exc}", file=sys.stderr)
        return None

    if not content.startswith("---"):
        print(
            f"{_HOOK_PREFIX} WARNING: {ticket_path} has no frontmatter block; "
            "cannot determine its declared status",
            file=sys.stderr,
        )
        return None

    end_idx = content.find("---", 3)
    frontmatter = content[3:end_idx] if end_idx != -1 else content[3:]

    match = _TICKET_STATUS_RE.search(frontmatter)
    if match is None:
        print(
            f"{_HOOK_PREFIX} WARNING: {ticket_path} frontmatter has no status field",
            file=sys.stderr,
        )
        return None
    return match.group(1).strip()


def _collect_work_item_claims(
    tickets_root: Path,
    folder_names: list[str],
) -> tuple[dict[str, list[tuple[Path, str | None]]], int]:
    """Walk every declared lifecycle folder and group files by basename.

    Non-recursive per folder by design: a "TICKET-*.md" file nested under an
    epic's subfolder (e.g. ``00_inbox/epics/EPIC-Foo/01_TICKET-...md``) is
    ordinal-prefixed and therefore already excluded by the basename pattern,
    but walking only the folder's direct children additionally guarantees an
    epic's own Master_Plan.md and sub-tickets are never visited at all.

    Args:
        tickets_root: The ``tickets/`` directory to walk (root itself is
            never scanned directly -- only its declared lifecycle folders).
        folder_names: Lifecycle folder basenames read from
            ticket_lifecycle.json.

    Returns:
        A (claims, inspected_count) tuple. ``claims`` maps each claimed
        basename to the list of (path, declared_status) pairs that claim it.
        ``inspected_count`` is the total number of "TICKET-*.md" files
        walked across all declared folders.
    """
    claims: dict[str, list[tuple[Path, str | None]]] = {}
    inspected_count = 0
    for folder_name in folder_names:
        folder_path = tickets_root / folder_name
        if not folder_path.is_dir():
            continue
        for ticket_path in sorted(folder_path.glob("TICKET-*.md")):
            inspected_count += 1
            status = _read_ticket_status(ticket_path)
            claims.setdefault(ticket_path.name, []).append((ticket_path, status))
    return claims, inspected_count


def _build_work_items_verdict(
    claims: dict[str, list[tuple[Path, str | None]]],
    inspected_count: int,
) -> NamespaceVerdict:
    """Turn a basename -> claimant map into the work-items NamespaceVerdict.

    A basename is only reported when two or more lifecycle folders hold a
    copy of it -- one Finding per contested identifier, never one per
    claimant file.

    Args:
        claims: Mapping of claimed basename to its (path, declared_status)
            claimant list.
        inspected_count: Total "TICKET-*.md" files walked.

    Returns:
        The assembled NamespaceVerdict for the "work-items" namespace.
    """
    findings = []
    for basename, entries in sorted(claims.items()):
        if len(entries) <= 1:
            continue
        identifier = Path(basename).stem
        paths = [str(path) for path, _status in entries]
        declared_states = {str(path): (status or "unknown") for path, status in entries}
        findings.append(Finding(number=identifier, paths=paths, declared_states=declared_states))
    return NamespaceVerdict(passed=not findings, inspected_count=inspected_count, findings=findings)


def scan_work_items(tickets_root: Path, lifecycle_config_path: Path) -> NamespaceVerdict:
    """Walk the work-items namespace and detect cross-folder identifier collisions.

    Args:
        tickets_root: Path to the ``tickets/`` directory.
        lifecycle_config_path: Path to ``tickets/ticket_lifecycle.json``,
            the source of truth for which folders count as lifecycle
            locations.

    Returns:
        The NamespaceVerdict for the "work-items" namespace: passing when no
        identifier is held by two or more lifecycle folders, with
        inspected_count equal to the number of "TICKET-*.md" files walked
        across those folders.
    """
    folder_names = _read_lifecycle_folder_names(lifecycle_config_path)
    if not folder_names:
        return NamespaceVerdict(passed=True, inspected_count=0, findings=[])

    claims, inspected_count = _collect_work_item_claims(tickets_root, folder_names)
    return _build_work_items_verdict(claims, inspected_count)
