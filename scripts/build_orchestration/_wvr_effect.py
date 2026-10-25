"""
MODULE: scripts/build_orchestration/_wvr_effect.py
GOAL: The effect check's pure functions (TQ-500g-1-xiv): the as-written line numbers a wrong
    version changes, and whether a test ran any of them.
BUSINESS CONTEXT: A test held to a wrong version that changes no line the test runs is reported
    ``not_executed`` (unfinished), never as a survivor.
ARCHITECTURE: Skeleton only. The test-writer phase declared this module (``declared_files``:
    to_be_created) with a must_catch test on ``changed_lines``; the red-baseline reader refuses an
    import-error red for such a test, so the module exists with the agreed signature and the
    python-coder phase writes the body.
"""

from __future__ import annotations


def changed_lines(as_written: bytes, altered: bytes) -> set[int]:
    """Return the 1-based as-written line numbers *altered* changes (not yet written)."""
    raise NotImplementedError("TQ-500g-1-xiv: changed_lines is written by the python-coder phase")


# ================================================================================
# DECISION HISTORY
# ================================================================================
# - 2026-10-25 18:50 [coordinator]: Skeleton so the declared must_catch test fails by reaching the code,
#   not by failing to import it (red-baseline reader, TQ-500f-3-i). (#EPIC-OnceANamedWrongVersionIsPreparedAnd/04)
