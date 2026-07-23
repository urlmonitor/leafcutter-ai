"""
MODULE: scripts/agent-health/agent_telemetry.py
GOAL: Append one structured telemetry JSONL record per agent invocation so
      operators can compare fast-lane vs heavy-pipeline cost and time per unit.
BUSINESS CONTEXT: Powers the retrospective-agent's Subagent Quality Trends
      section and the lane comparison report (BO-2400d-3). Fail-loud-not-fatal:
      sink errors are logged and counted but never propagate to the caller so
      the build always continues even when telemetry is unreachable.
ARCHITECTURE: Standalone module; no external dependencies beyond the standard
      library. Called by phase agents after completion. Module-level counter
      (_failed_write_count) surfaces dropped events for operator inspection.

Usage:
    from agent_telemetry import emit_agent_telemetry, get_failed_write_count

    emit_agent_telemetry(
        {"lane": "fast", "agent": "python-coder", "duration_ms": 1200,
         "tokens_in": 500, "tokens_out": 300, "cache_read_tokens": 100},
        sink_path=Path("debugging/logs/agent_telemetry.jsonl"),
    )
"""

from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level failed-write counter
# ---------------------------------------------------------------------------

_failed_write_count: int = 0


def get_failed_write_count() -> int:
    """Return the number of sink writes that have failed since the last reset.

    Returns:
        int: Current count of failed sink writes.
    """
    return _failed_write_count


def reset_failed_write_count() -> None:
    """Reset the failed-write counter to 0.

    Intended for test isolation only — call in setUp() so each test case
    starts with a clean counter.
    """
    global _failed_write_count
    _failed_write_count = 0


# ---------------------------------------------------------------------------
# Emitter
# ---------------------------------------------------------------------------


def emit_agent_telemetry(record: dict, *, sink_path: Path) -> None:
    """Append one telemetry record to sink_path as a newline-terminated JSON line.

    Adds a "ts" key (ISO-8601 UTC timestamp) to the written record if one is
    not already present. All caller-supplied fields are written as-is.

    On OSError (e.g. the sink is a directory or is otherwise unwritable):
    - Logs a WARNING via the module-level logger.
    - Increments the module-level _failed_write_count.
    - Does NOT re-raise — telemetry emission is best-effort and the build
      must continue even when the sink is unreachable.

    Args:
        record: Telemetry dict. Required keys: lane, agent, duration_ms,
            tokens_in, tokens_out, cache_read_tokens. Optional: unit_id.
            Additional keys are written through unchanged.
        sink_path: Path to the JSONL sink file. Parent directories are
            created if absent. File is created if it does not yet exist;
            existing content is preserved (open mode "a").
    """
    global _failed_write_count

    payload = dict(record)
    if "ts" not in payload:
        payload["ts"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    try:
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        sink_path.parent.mkdir(parents=True, exist_ok=True)
        with open(sink_path, "a", encoding="utf-8") as fh:
            fh.write(line)
    except (OSError, TypeError) as exc:
        logger.warning(
            "emit_agent_telemetry: failed to write to sink %s — record dropped: %s",
            sink_path,
            exc,
        )
        _failed_write_count += 1


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-07-21 [BO-2400d-1/BO-2400d-2/BO-2400d-1-i]: Initial creation.
#   Fail-loud-not-fatal: OSError logged + counted, never re-raised.
#   Module-level counter (_failed_write_count) exposed via get/reset helpers
#   for operator inspection and test isolation respectively.
# ====================================================================
