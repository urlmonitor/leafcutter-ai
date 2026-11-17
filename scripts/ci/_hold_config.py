"""
MODULE: _hold_config
GOAL: Refuse a tunables file whose staleness bound cannot outlast the heartbeat, before any read is made.
BUSINESS CONTEXT: TQ-600a-13-xiv. With ``staleness_hours <= heartbeat_max_hours`` a healthy heartbeat gap
    reads as stale and every pull request is held; a NaN or non-numeric value makes every comparison
    false and would silently pass. The check fails closed and names the file, both keys and both values.
ARCHITECTURE: ``check_staleness_bounds(tunables)`` is pure and raises ``TunablesError`` (a ``ValueError``)
    whose text is the detail of ``_hold_wording.config_invalid_reason``. A missing key is a ``KeyError``,
    left to the caller's generic handling.
"""

from __future__ import annotations

import math

from scripts.ci._hold_wording import TUNABLES_PATH


class TunablesError(ValueError):
    """The tunables file holds a staleness bound the check cannot safely use."""


def check_staleness_bounds(tunables: dict) -> None:
    """Raise ``TunablesError`` unless ``staleness_hours`` and ``heartbeat_max_hours`` are finite numbers with staleness above the heartbeat."""
    staleness, heartbeat = tunables["staleness_hours"], tunables["heartbeat_max_hours"]
    shown = f"{TUNABLES_PATH} has staleness_hours={staleness!r} and heartbeat_max_hours={heartbeat!r}"
    try:
        stale_value, beat_value = float(staleness), float(heartbeat)
    except (TypeError, ValueError) as exc:
        message = f"{shown}; both must be numbers"
        raise TunablesError(message) from exc
    if not (math.isfinite(stale_value) and math.isfinite(beat_value)):
        message = f"{shown}; both must be finite numbers"
        raise TunablesError(message)
    if stale_value <= beat_value:
        message = f"{shown}; staleness_hours must be greater than heartbeat_max_hours"
        raise TunablesError(message)
