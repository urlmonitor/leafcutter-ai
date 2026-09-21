#!/usr/bin/env python3
"""
MODULE: _gtfa_paths
GOAL: Answer the two location questions the ticket generator keeps asking —
    "where is the root of this checkout?" and "what is this ticket path,
    written the one canonical way?" — and name the generated ticket file.
BUSINESS CONTEXT: An ``implemented_by`` entry is an identifier other tooling
    reads back, so two spellings of the same ticket (``./tickets/x.md`` and
    ``/home/u/wt/tickets/x.md``) must canonicalise to one string or the AC
    store accumulates duplicate back-references that no dedup can see. Root
    discovery has the same property one level up: every config read, every
    components.json read, and the prose path-existence gate all resolve
    against it, so a root resolved two different ways is a silent behaviour
    fork.
ARCHITECTURE: Leaf module — depends only on ``_gtfa_seams`` (for the shared
    logger name), so every other sibling can depend on it. ``_find_worktree_root``
    is DEFINED here but must always be CALLED through
    ``_gtfa_seams.find_worktree_root`` by the other siblings:
    ``unit_tests/ac_store/test_tkt_500f_17.py`` patches it on the
    ``generate_ticket_from_ac`` shell, and a direct call to the definition here
    would ignore that patch.
"""

from __future__ import annotations

import importlib
import logging
import subprocess
from datetime import date
from pathlib import Path

# Siblings are imported under whichever layout THIS module was imported under
# (bare, after a sys.path insert of scripts/ac_store; or dotted, as
# scripts.ac_store.*). See the "Sibling wiring" note in
# generate_ticket_from_ac.py for why the prefix is derived rather than fixed.
_PKG = __name__.rpartition(".")[0]
_gtfa_seams = importlib.import_module(f"{_PKG}._gtfa_seams" if _PKG else "_gtfa_seams")

#: Log under the SHELL's name, not this module's — the test suites capture and
#: assert on ``generate_ticket_from_ac``'s logger. See _gtfa_seams.logger_name.
logger = logging.getLogger(_gtfa_seams.logger_name())


# ---------------------------------------------------------------------------
# Worktree root detection
# ---------------------------------------------------------------------------


def _find_worktree_root(start: Path) -> Path:
    """Walk up from *start* until a directory containing a .git file/dir is found.

    Args:
        start: Starting path for the upward search.

    Returns:
        The worktree root path.

    Raises:
        FileNotFoundError: When no .git marker is found before the filesystem root.

    DECISION HISTORY:
        H-2 reorder (2026-07-21): Moved before ``_load_migration_map`` and the
        module-level ``_COMPONENT_MIGRATION_MAP`` assignment so the fallback branch
        inside ``_load_migration_map`` can call this function at import time without
        a ``NameError``. The definition was previously at ~line 271, AFTER the
        module-level call that could trigger the fallback path.
    """
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    raise FileNotFoundError(  # noqa: TRY003
        f"Could not locate worktree root from {start}"
    )


# ---------------------------------------------------------------------------
# Ticket path canonicalisation
# ---------------------------------------------------------------------------


def _normalise_repo_relative(path: str) -> str:
    """Strip leading ``./`` or ``/`` and normalise separators for dedup comparison.

    Produces a canonical repo-relative form used only inside
    :func:`_write_implemented_by` to compare a candidate path against existing
    ``implemented_by`` entries.  The stored AC YAML value is never modified —
    only the comparison is normalised so that ``./tickets/foo.md`` and
    ``tickets/foo.md`` are treated as the same entry.

    Args:
        path: A raw path string, potentially prefixed with ``./`` or ``/``.

    Returns:
        The normalised repo-relative path with any leading ``./`` or ``/``
        stripped and path separators unified to ``/``.
    """
    normalised = path.replace("\\", "/")
    normalised = normalised.lstrip("/")
    while normalised.startswith("./"):
        normalised = normalised[2:]
    return normalised


def _canonicalise_to_repo_relative(path: str, repo_root: "Path | None" = None) -> str:
    """Canonicalise a ticket path to its repo-relative form.

    Uses a three-tier strategy so that absolute paths, cross-worktree paths,
    and cosmetically-prefixed relative paths all resolve to the same canonical
    ``tickets/…`` string:

    1. **repo_root relativisation** — when *repo_root* is provided and *path* is
       absolute, ``Path.relative_to(repo_root)`` is attempted.  Falls through to
       tier 2 on ``ValueError`` (path is outside the given root).
    2. **tickets-segment extraction** — after stripping any leading ``/``, the
       leftmost ``tickets/`` segment is located.  Everything from that segment
       onward is returned.  Handles absolute legacy paths and cross-worktree
       absolute paths where the exact repo root is unknown.
    3. **Simple strip** — strip any remaining leading ``./`` or ``/`` characters
       for already-relative paths with cosmetic prefixes.

    Args:
        path: A raw path string — absolute, relative, or prefixed with ``./``.
        repo_root: Optional repo root ``Path``.  When provided and *path* is
            absolute, ``relative_to`` is attempted before any segment extraction.

    Returns:
        A repo-relative path string with no leading ``/`` and no absolute
        filesystem prefix (e.g. ``tickets/00_inbox/TICKET-test.md``).

    DECISION HISTORY:
    - 2026-07-21 [ACD-1200a-13]: Introduced to extend ``_normalise_repo_relative``
      with tickets-segment extraction, enabling dedup of legacy absolute entries
      against canonical repo-relative incoming paths without a git subprocess call.
    - 2026-07-21 [ACD-1200a-14]: Added *repo_root* parameter so callers can inject
      a known repo root for relativisation, producing identical canonical strings
      regardless of checkout location.
    """
    normalised = path.replace("\\", "/")

    # Tier 1: repo_root-based relativisation
    if repo_root is not None and Path(normalised).is_absolute():
        try:
            return str(Path(normalised).relative_to(repo_root)).replace("\\", "/")
        except ValueError:
            pass  # Fall through to tier 2

    # Tier 2 & 3: strip leading characters, then extract tickets/ segment
    normalised = normalised.lstrip("/")
    while normalised.startswith("./"):
        normalised = normalised[2:]

    # Tier 2: extract everything from the first 'tickets/' segment when the
    # cleaned string still has a non-trivial prefix before 'tickets/'
    tickets_idx = normalised.find("tickets/")
    if tickets_idx > 0:
        return normalised[tickets_idx:]

    return normalised


def _derive_repo_root_from_git() -> "Path | None":
    """Derive the git repository root via ``git rev-parse --show-toplevel``.

    Returns ``None`` and logs a ``WARNING`` when the command fails (e.g. the
    working directory is not inside a git repository, or git is not installed).
    Never raises — callers must handle the ``None`` case via the fallback
    canonicaliser.

    Returns:
        The repo root as a ``Path``, or ``None`` when git cannot resolve it.

    DECISION HISTORY:
    - 2026-07-21 [ACD-1200a-14]: Introduced to derive repo root for absolute-path
      canonicalisation when neither a worktree nor an explicit *repo_root* is
      provided to ``_write_implemented_by``.
    - 2026-07-21 [ACD-1200a-14-i]: Wrapped subprocess call with specific exception
      types (``CalledProcessError``, ``FileNotFoundError``) per Error Handling Policy
      Rule 1; always logs ``WARNING`` on failure and never re-raises so that the
      caller's fallback path can succeed.
    - 2026-07-21 [M-1/M-2 review findings]: Broadened except to
      ``(subprocess.CalledProcessError, OSError)`` — ``FileNotFoundError`` and
      ``PermissionError`` are both ``OSError`` subclasses, so the narrower form
      missed ``PermissionError`` on restricted filesystems (M-1). Added
      ``timeout=5`` to the ``subprocess.run`` call to prevent indefinite hangs on
      network/degenerate filesystems, and added ``subprocess.TimeoutExpired`` to the
      except clause (M-2).
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired) as exc:
        logger.warning(
            "git rev-parse --show-toplevel failed — falling back to tickets-segment "
            "canonicalisation for implemented_by path normalisation: %s",
            exc,
        )
        return None


# ---------------------------------------------------------------------------
# Ticket filename
# ---------------------------------------------------------------------------


def _ticket_filename(ac_id: str) -> str:
    """Return the ticket filename for the given AC id.

    Args:
        ac_id: The AC id.

    Returns:
        Filename string of the form ``TICKET-YYYYMMDD-<ac_id>.md``.
    """
    today = date.today().strftime("%Y%m%d")
    return f"TICKET-{today}-{ac_id}.md"
