"""
MODULE: capture_write
GOAL: Write a routed learning's text to its destination knowledge surface --
    the append-only production half of the capture-learning write protocol
    that ``harvest_learnings.harvest()`` invokes for every routable event.
BUSINESS CONTEXT: This is the mirror-image concern of ``sink_resolution``:
    that module resolves where the harvester READS from; this one is where a
    routed learning is WRITTEN to, once ``harvest()`` has already decided a
    record is eligible and knows its destination. Kept separate from routing
    decisions and from ``HarvestResult`` reporting so each concern has one
    file to read to understand it.
ARCHITECTURE: Helper module for the Knowledge System component
    (docs/architecture/components/knowledge-system.md). Loaded by
    ``harvest_learnings.py`` as a required sibling module (see that file's
    ``_load_required_sibling_module``) rather than a bare top-level import,
    since ``harvest_learnings.py`` is itself loaded via
    ``importlib.util.spec_from_file_location`` by several pre-existing tests
    that do not add ``scripts/knowledge/`` to ``sys.path`` first. The
    ``logger`` here deliberately shares the name ``"harvest_learnings"`` with
    the logger in that file, so a write-failure warning is byte-for-byte
    identical to before the extraction.

    In tests, ``harvest()``'s ``capture_fn`` parameter is replaced by a
    lightweight stub so the suite never writes to the real filesystem; this
    module's ``default_capture`` is exercised only by the small number of
    real-artifact round-trip tests that deliberately use the production path.

# DECISION HISTORY
# - 2026-09-14 [python-coder/GE-127b-1 fix]: Extracted verbatim from
#   harvest_learnings.py (renamed from ``_default_capture`` to
#   ``default_capture``, its new module's public API) to relieve the
#   GE-127b-1 file-size ratchet, which refused a legitimate INF-400c-5-i fix
#   because it left that already-oversized file longer than it stood before.
#   No test accesses this function via a module attribute (only via
#   ``harvest()``'s ``capture_fn`` parameter, which harvest_learnings.py
#   still binds to this function by reference), so the rename is invisible
#   to every existing test. (#INF-400c-5, GE-127b-1)
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("harvest_learnings")


def default_capture(learning_text: str, destination_path: str) -> None:
    """Write *learning_text* to *destination_path* (append-only).

    This is the production capture-learning write protocol.  In tests, this
    function is replaced by a lightweight stub so the test suite does not
    write to the real filesystem.
    """
    dest = Path(destination_path)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "a", encoding="utf-8") as fh:
            fh.write(learning_text + "\n")
    except OSError as exc:
        logger.warning(
            "Failed to write learning to %s: %s",
            destination_path,
            exc,
        )
        raise
