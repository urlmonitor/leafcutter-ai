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
  - 2026-08-19 [python-coder/GE-122a-2, bug-fix]: Fixed a lifecycle-folder
    -discovery defect found by pr-reviewer (feedback-id
    fb_2026-08-19_e1c1912f). ``_read_lifecycle_folder_names`` collapsed each
    declared ``folders[].path`` to ``Path(entry["path"]).name`` (its last
    component only) and relied on the caller rejoining that bare name under
    ``tickets_root``; a folder declared more than one level deep silently
    vanished from the walk (false negative), and two distinct declared
    paths sharing a basename silently collapsed onto the same physical
    directory (false positive: one file walked twice and reported as a
    self-collision). Replaced with ``_resolve_lifecycle_folder_paths``,
    which resolves each declared path to its full real directory relative
    to the repository root (``lifecycle_config_path.parent.parent`` --
    declared paths are documented as repo-root-relative, e.g.
    ``"tickets/00_inbox"``, never ``tickets_root``-relative) and returns
    that resolved ``Path`` directly; ``_collect_work_item_claims`` now
    walks each resolved path as-is instead of rejoining a basename.
    Defensively rejects (WARNING + skip, fail-open, never a crash) a
    declared path that is absolute, or one that resolves outside the
    repository root via ``../`` segments. See
    unit_tests/commit_guardian/test_ge_122a_2_lifecycle_folder_paths.py for
    the regression coverage (nested-folder false negative, shared-basename
    false positive, flat-layout regression anchor, missing-folder
    fail-open).
  - 2026-08-25 [python-coder/GE-122e-3, bug-fix]: Fixed a fail-open defect
    found by pr-reviewer (feedback-id fb_2026-08-24_94dc4ba4, finding
    [H-3]): ``_resolve_lifecycle_folder_paths`` returned an empty list for
    THREE different situations that ``scan_work_items`` then collapsed
    onto one identical ``passed=True, inspected_count=0`` outcome: (1) a
    missing/unreadable ``ticket_lifecycle.json`` (misconfiguration -- the
    config was never resolved), (2) unparsable JSON (same), and (3) a
    present, valid config that explicitly declares zero folders (a
    legitimately empty, resolved configuration). Per the contract fixed in
    unit_tests/commit_guardian/test_ge_122e_3_root_resolution.py's module
    docstring ("THE CONTRACT DECISION"), only case (3) may report
    passed=True. ``_resolve_lifecycle_folder_paths`` now returns ``None``
    (not ``[]``) for cases (1) and (2) -- config could not be resolved at
    all -- while still returning ``[]`` for case (3), so ``scan_work_items``
    can tell "nothing to walk because there is nothing declared" apart
    from "nothing to walk because the config itself could not be read".
    ``scan_work_items`` reports passed=False (empty findings -- the config
    itself is the finding) only for the ``None`` case; the declared-empty
    case is unchanged and still passes cleanly.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from _uniqueness_types import Finding, NamespaceVerdict  # type: ignore[import]

_HOOK_PREFIX = "[check_identifier_uniqueness]"

_TICKET_STATUS_RE = re.compile(r"^status:\s*(.+)$", re.MULTILINE)


def _resolve_one_folder_path(raw_path: str, repo_root: Path, repo_root_resolved: Path) -> Path | None:
    """Resolve a single declared ``folders[].path`` entry to a real directory path.

    Declared paths (e.g. ``"tickets/00_inbox"``) are documented as relative
    to the REPOSITORY ROOT (the parent of the ``tickets/`` directory that
    holds ``ticket_lifecycle.json``), never to ``tickets_root`` itself --
    joining under ``tickets_root`` would double the ``tickets/`` segment
    (``tickets/tickets/00_inbox``).

    Args:
        raw_path: The entry's own ``"path"`` string, exactly as declared.
        repo_root: The repository root (``lifecycle_config_path.parent.parent``),
            unresolved -- used to build the candidate path.
        repo_root_resolved: ``repo_root.resolve()``, precomputed once by the
            caller so every entry is checked against the same containment
            boundary.

    Returns:
        The resolved absolute directory path, or None if the declared path
        is rejected (defensive): an absolute path (declared paths are
        documented as repo-root-relative, so an absolute entry is treated
        as a misconfiguration, not honored verbatim) or a path that
        resolves outside the repository root (e.g. via ``../`` segments).
        Both cases are logged at WARNING and skipped -- fail-open per
        malformed entry, consistent with this module's missing-config and
        missing-folder fail-open conventions, never a crash.
    """
    candidate = Path(raw_path)
    if candidate.is_absolute():
        print(
            f"{_HOOK_PREFIX} WARNING: lifecycle folder path {raw_path!r} is absolute; "
            "declared folder paths must be relative to the repository root. Skipping.",
            file=sys.stderr,
        )
        return None

    resolved = (repo_root / candidate).resolve()
    if not resolved.is_relative_to(repo_root_resolved):
        print(
            f"{_HOOK_PREFIX} WARNING: lifecycle folder path {raw_path!r} resolves to "
            f"{resolved}, outside the repository root {repo_root_resolved}. Skipping.",
            file=sys.stderr,
        )
        return None
    return resolved


def _resolve_lifecycle_folder_paths(lifecycle_config_path: Path) -> list[Path] | None:
    """Resolve every declared lifecycle folder to its real, full on-disk path.

    Reads the folder list rather than hard-coding it, per this AC's own
    it_requirement that the allowed-status-per-folder mapping -- and, by
    extension, which folders count as lifecycle locations -- must be read
    from the config file, never restated in code. The ``tickets/`` root
    itself is never included: it is not one of the declared folder entries.

    Each entry's ``"path"`` (e.g. ``"tickets/00_inbox"``) is declared
    RELATIVE TO THE REPOSITORY ROOT, not to ``tickets_root`` -- the config
    lives at ``tickets/ticket_lifecycle.json``, so the repository root is
    ``lifecycle_config_path.parent.parent``. Earlier versions of this
    function reduced each path to ``Path(entry["path"]).name`` (its last
    component only) and left the caller to rejoin that bare name under
    ``tickets_root``; that silently broke on any folder declared more than
    one level deep (the parent segment vanished, so the walk missed the
    folder entirely) and could also collapse two DISTINCT declared paths
    that merely share a basename onto the same physical directory (walked
    twice, reported as two folders holding one file). Returning the fully
    resolved path removes both failure modes: there is no longer a
    basename to collide on, and no rejoin step for a caller to get wrong.

    Args:
        lifecycle_config_path: Path to ``tickets/ticket_lifecycle.json``.

    Returns:
        List of resolved absolute directory paths (not required to exist
        on disk -- a missing directory is the caller's fail-open-per-folder
        concern, not this function's). An empty list means the config
        itself WAS resolved (read and parsed successfully) but declares no
        usable folder entries -- a legitimate, deliberately empty
        configuration. ``None`` means the config could NOT be resolved at
        all: the file is missing, unreadable, or not valid JSON -- a
        misconfiguration distinct from a genuinely empty declaration (see
        GE-122e-3 "THE CONTRACT DECISION" in
        unit_tests/commit_guardian/test_ge_122e_3_root_resolution.py).
    """
    try:
        content = lifecycle_config_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: cannot read {lifecycle_config_path}: {exc}",
            file=sys.stderr,
        )
        return None

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: cannot parse {lifecycle_config_path}: {exc}",
            file=sys.stderr,
        )
        return None

    repo_root = lifecycle_config_path.resolve().parent.parent
    repo_root_resolved = repo_root.resolve()
    folders = data.get("folders", [])
    resolved_paths = []
    for entry in folders:
        raw_path = entry.get("path")
        if not raw_path:
            continue
        resolved = _resolve_one_folder_path(raw_path, repo_root, repo_root_resolved)
        if resolved is not None:
            resolved_paths.append(resolved)
    return resolved_paths


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
    folder_paths: list[Path],
) -> tuple[dict[str, list[tuple[Path, str | None]]], int]:
    """Walk every declared lifecycle folder and group files by basename.

    Non-recursive per folder by design: a "TICKET-*.md" file nested under an
    epic's subfolder (e.g. ``00_inbox/epics/EPIC-Foo/01_TICKET-...md``) is
    ordinal-prefixed and therefore already excluded by the basename pattern,
    but walking only the folder's direct children additionally guarantees an
    epic's own Master_Plan.md and sub-tickets are never visited at all.

    Args:
        folder_paths: Fully resolved lifecycle folder directory paths (from
            ``_resolve_lifecycle_folder_paths``) -- each is walked as its
            own distinct directory, so two declared paths that merely share
            a basename can never collide on the same physical directory.

    Returns:
        A (claims, inspected_count) tuple. ``claims`` maps each claimed
        basename to the list of (path, declared_status) pairs that claim it.
        ``inspected_count`` is the total number of "TICKET-*.md" files
        walked across all declared folders.
    """
    claims: dict[str, list[tuple[Path, str | None]]] = {}
    inspected_count = 0
    for folder_path in folder_paths:
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
        tickets_root: Path to the ``tickets/`` directory. Kept for call-site
            and test-signature stability; folder resolution itself no
            longer joins under this argument (see
            ``_resolve_lifecycle_folder_paths``) -- each declared folder is
            resolved to its own full path relative to the repository root
            (``lifecycle_config_path.parent.parent``), which is always
            ``tickets_root``'s parent for every real caller.
        lifecycle_config_path: Path to ``tickets/ticket_lifecycle.json``,
            the source of truth for which folders count as lifecycle
            locations.

    Returns:
        The NamespaceVerdict for the "work-items" namespace: passing when no
        identifier is held by two or more lifecycle folders, with
        inspected_count equal to the number of "TICKET-*.md" files walked
        across those folders. When ``lifecycle_config_path`` itself could
        not be resolved at all (missing, unreadable, or unparsable),
        reports passed=False with inspected_count=0 and an empty findings
        list -- the config was never actually read, so this is a
        misconfiguration, not evidence of a genuinely empty namespace. A
        config that IS resolved but declares zero folders still passes
        cleanly with inspected_count=0 (see GE-122e-3 "THE CONTRACT
        DECISION" in unit_tests/commit_guardian/test_ge_122e_3_root_resolution.py).
    """
    del tickets_root  # See Args note: retained for signature stability only.
    folder_paths = _resolve_lifecycle_folder_paths(lifecycle_config_path)
    if folder_paths is None:
        return NamespaceVerdict(passed=False, inspected_count=0, findings=[])
    if not folder_paths:
        return NamespaceVerdict(passed=True, inspected_count=0, findings=[])

    claims, inspected_count = _collect_work_item_claims(folder_paths)
    return _build_work_items_verdict(claims, inspected_count)
