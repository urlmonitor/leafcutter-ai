"""
epic_runtime.py — Shared runtime primitives for the goal-to-epic pipeline.

MODULE: epic_runtime
GOAL: Hold the pipeline's default path constants, its worktree-root detection
      helpers, and the single shared logger name, in a module with no sibling
      dependencies so every other pipeline module can import it freely.
BUSINESS CONTEXT: Extracted from goal_to_epic.py so that file can meet the
      400-line check_file_size limit. The logger accessor exists because the
      logger NAME is observable behaviour: tests assert on
      ``assertLogs("goal_to_epic", ...)``, so a module that logged via
      ``logging.getLogger(__name__)`` after the split would emit records under
      its own module name and silently break that assertion. Every pipeline
      module logs through :func:`get_logger` instead.
ARCHITECTURE: Bottom of the goal-to-epic dependency graph — imports nothing from
      any sibling module. Deployed flat beside goal_to_epic.py in
      <output_root>/scripts/ac_store/ (see AC_STORE_DEPLOY_MAP in
      scripts/build_phases.py).

AC coverage owned by this module:
    BP-901: _derive_worktree_from_inbox() lets main() obtain a worktree root by
            pure path math, so _find_worktree_root() is never called when both
            --store-root and --inbox-dir are supplied explicitly.
    ACD-1200a-9: the derived worktree root is what run() uses to relativise
            loose ticket paths before rewriting implemented_by back-references.
"""

from __future__ import annotations

import logging
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_STORE_ROOT = "docs/acceptance-criteria"
_DEFAULT_INBOX_DIR = "tickets/00_inbox"

#: Logger name shared by every goal-to-epic pipeline module.
#:
#: Before the module split every function logged via
#: ``logging.getLogger(__name__)``, which resolved to ``"goal_to_epic"`` on the
#: import path. That name is asserted on directly by
#: tests/test_goal_to_epic_basename_collision.py
#: (``assertLogs("goal_to_epic", ...)``), so it is observable behaviour, not an
#: implementation detail. Pinning it here keeps every extracted module emitting
#: records under the original name.
LOGGER_NAME = "goal_to_epic"


def get_logger() -> logging.Logger:
    """Return the shared goal-to-epic logger.

    Every pipeline module logs through this accessor rather than
    ``logging.getLogger(__name__)`` so that all records keep the single
    pre-split logger name (:data:`LOGGER_NAME`).

    Returns:
        logging.Logger: The logger named :data:`LOGGER_NAME`.
    """
    return logging.getLogger(LOGGER_NAME)


# ---------------------------------------------------------------------------
# Worktree root detection
# ---------------------------------------------------------------------------


def _find_worktree_root(start: Path) -> Path:
    """Walk up from *start* until a directory containing a .git file/dir is found.

    Args:
        start: Starting path for the upward search (typically the script location).

    Returns:
        The worktree root path.

    Raises:
        FileNotFoundError: When no .git marker is found before the filesystem root.
    """
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    raise FileNotFoundError(  # noqa: TRY003
        f"Could not locate worktree root from {start}"
    )


def _derive_worktree_from_inbox(inbox_dir: Path) -> Path | None:
    """Derive the worktree root from a supplied inbox directory by path math only.

    ``inbox_dir`` is conventionally ``<worktree>/tickets/00_inbox``
    (``_DEFAULT_INBOX_DIR``). When it ends with that suffix, the worktree root is
    the prefix above it. Returns ``None`` when ``inbox_dir`` does not follow the
    convention (or has no prefix above the suffix), in which case callers skip
    path relativisation and ``run()`` degrades gracefully.

    This exists so ``main()`` can satisfy BP-901 — never call
    ``_find_worktree_root()`` (a filesystem walk from ``__file__``) when both
    ``--store-root`` and ``--inbox-dir`` are explicit, so the script works when
    deployed outside a git tree — while still giving ``run()`` the worktree root
    it needs for ACD-1200a-9 loose-ticket-path relativisation. Pure function: no
    filesystem access, so no try/except per the project error-handling policy.

    Args:
        inbox_dir: The tickets inbox directory supplied on the command line.

    Returns:
        The derived worktree root, or ``None`` when *inbox_dir* does not follow
        the ``<worktree>/tickets/00_inbox`` convention.
    """
    suffix_parts = Path(_DEFAULT_INBOX_DIR).parts
    inbox_parts = inbox_dir.parts
    if (
        len(inbox_parts) > len(suffix_parts)
        and inbox_parts[-len(suffix_parts):] == suffix_parts
    ):
        return Path(*inbox_parts[: -len(suffix_parts)])
    return None


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 12:00 [goal-to-epic-decompose]: Extracted from
  scripts/goal_to_epic.py, which exceeded the 400-line check_file_size limit.
  _find_worktree_root() and _derive_worktree_from_inbox() moved verbatim
  (bodies and docstrings unchanged apart from an added Args:/Returns: pair on
  _derive_worktree_from_inbox, which previously documented neither and would
  have failed check_docstrings as a newly-added definition). LOGGER_NAME and
  get_logger() are NEW: before the split every function called
  logging.getLogger(__name__) == "goal_to_epic", and that name is asserted on
  by tests/test_goal_to_epic_basename_collision.py, so the extracted modules
  must not fall back to their own __name__. Pre-split history for the worktree
  helpers lives in goal_to_epic.py's DECISION HISTORY block (the 2026-06-18
  and 2026-06-22 BP-901 entries).
  (#TICKETLESS reason=file-size-decomposition-refactor)
====================================================================
"""
