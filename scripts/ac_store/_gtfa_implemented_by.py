#!/usr/bin/env python3
"""
MODULE: _gtfa_implemented_by
GOAL: Append the generated ticket's path to the source AC's ``implemented_by``
    list, without disturbing anything else in the file.
BUSINESS CONTEXT: ``implemented_by`` is the AC store's back-reference to the
    work that implements a criterion — the link the AC-fulfillment gate and the
    coverage resolver follow. Two things make it fragile: the same ticket can
    be written in several spellings (``./tickets/x.md``, an absolute path from
    another worktree, a Windows path with backslashes), and the AC file is
    hand-edited YAML that a full ``yaml.dump`` round-trip would reformat
    wholesale.
ARCHITECTURE: Hence a TARGETED line-level rewrite rather than a round-trip: the
    ``implemented_by`` block is replaced in place and every other byte of the
    file is preserved, which keeps the store's diffs reviewable. Dedup
    canonicalises BOTH the incoming path and every existing entry through the
    same canonicaliser, so a legacy absolute entry is recognised as a duplicate
    of a canonical repo-relative incoming path instead of being appended twice;
    the write-back then normalises those legacy entries in place. When the
    normalised list is byte-identical to what is on disk, nothing is written —
    a true no-op, which is what makes a re-run idempotent.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

import yaml

# See the "Sibling wiring" note in generate_ticket_from_ac.py for why the
# sibling package prefix is derived from __name__ rather than hard-coded.
_PKG = __name__.rpartition(".")[0]
_gtfa_seams = importlib.import_module(f"{_PKG}._gtfa_seams" if _PKG else "_gtfa_seams")
_gtfa_paths = importlib.import_module(f"{_PKG}._gtfa_paths" if _PKG else "_gtfa_paths")

logger = logging.getLogger(_gtfa_seams.logger_name())

_canonicalise_to_repo_relative = _gtfa_paths._canonicalise_to_repo_relative
_derive_repo_root_from_git = _gtfa_paths._derive_repo_root_from_git


def _effective_repo_root(
    ticket_path: str,
    worktree: "Path | None",
    repo_root: "Path | None",
) -> tuple[str, "Path | None"]:
    """Resolve the repo root to canonicalise against, and pre-relativise the path.

    Three tiers, in the order the caller's arguments authorise: an explicit
    *repo_root* wins outright; otherwise a *worktree* is tried by
    ``relative_to`` (cheap, no subprocess); otherwise — and only for an
    absolute path that neither covered — ``git rev-parse`` is consulted.

    Args:
        ticket_path: The raw ticket path as given.
        worktree: Optional worktree root.
        repo_root: Optional explicit repo root; takes precedence.

    Returns:
        ``(ticket_path, effective_repo_root)`` — the path possibly already
        relativised against *worktree*, and the root to canonicalise against
        (``None`` when the tickets-segment fallback must handle it).
    """
    path_obj = Path(ticket_path)
    effective: "Path | None" = repo_root

    if path_obj.is_absolute() and effective is None:
        if worktree is not None:
            try:
                ticket_path = str(path_obj.relative_to(worktree))
                # Successfully relativised against worktree; no git call needed.
            except ValueError:
                # Ticket lies outside the worktree — derive root from git.
                effective = _derive_repo_root_from_git()
        else:
            effective = _derive_repo_root_from_git()

    return ticket_path, effective


def _read_ac_implemented_by(ac_path: Path) -> tuple[str, list[str]]:
    """Read the AC file and parse its current ``implemented_by`` list.

    Args:
        ac_path: Absolute path to the source AC YAML file.

    Returns:
        ``(raw_file_content, implemented_by_entries)``.

    Raises:
        OSError: When the file cannot be read.
        yaml.YAMLError: When the YAML cannot be parsed.
    """
    try:
        content = ac_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot read AC YAML %s: %s", ac_path, exc)
        raise
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        logger.warning("Cannot parse AC YAML %s: %s", ac_path, exc)
        raise
    return content, (data.get("implemented_by") or [])


def _replace_implemented_by_block(content: str, normalised_list: list[str]) -> str:
    """Return *content* with its ``implemented_by`` block replaced in place.

    Walks the file line by line and swaps only the ``implemented_by:`` key and
    the list items beneath it, leaving every other line byte-identical. When
    the key is absent entirely the new block is appended instead.

    Args:
        content: The AC file's current text.
        normalised_list: The canonicalised entries to write.

    Returns:
        The new file content.
    """
    new_value_yaml = yaml.dump(
        {"implemented_by": normalised_list},
        default_flow_style=False,
        allow_unicode=True,
    ).strip()
    # new_value_yaml is e.g. "implemented_by:\n- tickets/foo/bar.md"

    lines = content.splitlines(keepends=True)
    result_lines: list[str] = []
    i = 0
    replaced = False
    while i < len(lines):
        line = lines[i]
        if not replaced and line.startswith("implemented_by:"):
            # Emit the new (normalised) block, then skip the old list items.
            result_lines.append(new_value_yaml + "\n")
            i += 1
            while i < len(lines) and (
                lines[i].startswith(" ")
                or lines[i].startswith("\t")
                or lines[i].strip() == "-"
                or (
                    lines[i].startswith("- ")
                    and not lines[i - 1].startswith(" ")
                )
            ):
                if lines[i].startswith("- ") or lines[i].startswith("  - "):
                    i += 1
                else:
                    break
            replaced = True
        else:
            result_lines.append(line)
            i += 1

    if not replaced:
        # implemented_by key not present in file — append the new block.
        return content.rstrip("\n") + "\n" + new_value_yaml + "\n"
    return "".join(result_lines)


def _write_implemented_by(
    ac_path: Path,
    ticket_path: str,
    ac_id: str,
    worktree: Path | None = None,
    repo_root: "Path | None" = None,
) -> None:
    """Append *ticket_path* to the implemented_by list in the source AC YAML.

    Uses a targeted field update (not a full yaml.dump round-trip) to minimise
    diff noise in the AC store.  Both the incoming path and every existing
    ``implemented_by`` entry are canonicalised through a shared
    ``_canonicalise_to_repo_relative`` call before comparison, so legacy
    absolute entries are recognised as duplicates of canonical repo-relative
    incoming paths and no duplicate is appended.

    The update strategy:
    1. Determine the effective repo root (from *repo_root*, worktree fallback, or
       ``git rev-parse --show-toplevel``; logs WARNING on git failure).
    2. Canonicalise *ticket_path* to a clean ``tickets/…`` repo-relative form.
    3. Read the full file content and parse ``implemented_by`` from the YAML.
    4. Canonicalise every existing entry through the same canonicaliser.
    5. If the canonical incoming is already present, skip appending (idempotent).
    6. Rewrite the ``implemented_by`` block only when the normalised list differs
       from the original (write-back normalises legacy absolute entries in place).

    Args:
        ac_path: Absolute path to the source AC YAML file.
        ticket_path: Path of the generated ticket to record.  May be absolute
                     or relative; will be normalised to repo-relative form
                     before writing.
        ac_id: The AC id (for diagnostic messages).
        worktree: Optional worktree root.  When provided and *ticket_path* is
                  absolute and *repo_root* is absent, the worktree prefix is
                  stripped via ``Path.relative_to`` to produce a clean
                  repo-relative path.
        repo_root: Optional repository root ``Path``.  When provided, all path
                   canonicalisation uses ``Path.relative_to(repo_root)``.  Takes
                   precedence over *worktree*-based relativisation.  When absent
                   and *ticket_path* is absolute, ``git rev-parse --show-toplevel``
                   is attempted; on failure a WARNING is logged and the
                   tickets-segment fallback is used.

    Raises:
        OSError: When the file cannot be read or written.
        yaml.YAMLError: When the YAML cannot be parsed.

    DECISION HISTORY:
    - 2026-07-21 [ACD-1200a-13]: Switched dedup to use ``_canonicalise_to_repo_relative``
      on BOTH incoming and existing entries so that legacy absolute entries are
      recognised as duplicates of canonical repo-relative incoming paths.  Existing
      entries are retroactively normalised on every write-back so no absolute path
      survives in the stored list.
    - 2026-07-21 [ACD-1200a-14]: Added *repo_root* parameter; when provided, all
      canonicalisation uses ``Path.relative_to(repo_root)`` producing identical
      stored strings regardless of checkout or worktree location.
    - 2026-07-21 [ACD-1200a-14-i]: When *repo_root* is absent and the path is
      absolute, git rev-parse is attempted via ``_derive_repo_root_from_git``; on
      failure a WARNING is logged and the tickets-segment fallback handles the path.
    """
    # Step 1: Determine the effective repo root for canonicalisation.
    ticket_path, effective_repo_root = _effective_repo_root(
        ticket_path, worktree, repo_root
    )

    # Step 2: Canonicalise the incoming ticket path.
    canonical_incoming = _canonicalise_to_repo_relative(
        str(Path(ticket_path)), effective_repo_root
    )

    # Step 3: Read the file and parse existing implemented_by entries.
    content, implemented_by = _read_ac_implemented_by(ac_path)

    # Step 4: Normalise all existing entries through the shared canonicaliser
    # and check whether the incoming is already represented.
    normalised_list: list[str] = [
        _canonicalise_to_repo_relative(entry, effective_repo_root)
        for entry in implemented_by
    ]
    already_recorded = canonical_incoming in normalised_list
    if not already_recorded:
        normalised_list.append(canonical_incoming)

    # If the normalised list is byte-for-byte identical to what is on disk,
    # no write is necessary (true no-op; covers the idempotent re-run case).
    if normalised_list == implemented_by:
        return

    # Step 5: Targeted rewrite — replace only the implemented_by block.
    new_content = _replace_implemented_by_block(content, normalised_list)

    try:
        ac_path.write_text(new_content, encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot write AC YAML %s: %s", ac_path, exc)
        raise
