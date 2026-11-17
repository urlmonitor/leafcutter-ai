"""The one skip reason of a live-database test that found no reachable database (TQ-600a-13-xxiii).

MODULE: _live_skip
GOAL: Give every live-database test the SAME reason to skip for want of a database, defined once
    and imported by the tests and by the live lane's classifier (``scripts/ci/_live_lane.py``) alike.
BUSINESS CONTEXT: A skip is right in the per-PR shards (no database there) and means "the lane failed
    its one job" in the post-merge live-database lane. The lane tells the two skips apart by this
    reason, never by a substring guess or a per-test list.
ARCHITECTURE: ``unreachable_reason(exc)`` returns ``"<UNREACHABLE>: <exc>"``; the prefix is the
    classifier's own constant, imported, so the two cannot drift.
"""

from scripts.ci._live_lane import UNREACHABLE


def unreachable_reason(exc: object) -> str:
    """The skip reason for a test that could not reach its database: the shared prefix, then the cause."""
    return f"{UNREACHABLE}: {exc}"
