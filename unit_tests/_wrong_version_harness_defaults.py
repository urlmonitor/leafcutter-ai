"""
MODULE: _wrong_version_harness_defaults
GOAL: Passing default `agent()` label responses for the wrong-version command
    steps that build-feature.js and build-ticket.js dispatch before every commit.
BUSINESS CONTEXT: TQ-500g-1-vi made both routes run the wrong-version sequence
    (recover, list, finish) through command-step-runner and fail closed on any
    reply that is not a passing report. Every pre-existing workflow test that
    reaches the commit dispatch (or a drive on a reused worktree) would
    otherwise meet an unstubbed step and halt. This module supplies the passing
    reply each step's real script prints (recover ok, nothing owed, finish
    gate_passed) wrapped in the executor's reply shape ({"stdout": <JSON>}), so
    those tests keep exercising what they always did. Caller-supplied
    label_responses always take precedence per label, so a test of a refusal
    path overrides the same label. Kept out of
    unit_tests/_workflow_engine_harness.py, which sits at the check-file-size
    ratchet ceiling (same reason as _plan_feature_harness_defaults.py).
ARCHITECTURE: Pure-Python helper; the harness's
    `_default_label_responses_for_script()` merges the one public entry point.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_ROUTE_LABEL_PREFIXES = {"build-feature.js": "bf", "build-ticket.js": "bt"}
_PASSING_STEP_REPLIES: dict[str, dict[str, Any]] = {
    "recover": {"restored": [], "ok": True, "copy_dir": None, "detail": ""},
    "list": {"owed": [], "error": None},
    "finish": {"gate_passed": True, "stopped_at": None, "writer": None, "verdict": None},
}


def wrong_version_default_label_responses(script_path: Path) -> dict[str, Any]:
    """Return passing `<prefix>-wv-*` replies for build-feature.js / build-ticket.js, else `{}`."""
    prefix = _ROUTE_LABEL_PREFIXES.get(script_path.name)
    if prefix is None:
        return {}
    return {
        f"{prefix}-wv-{step}": {"stdout": json.dumps(reply)}
        for step, reply in _PASSING_STEP_REPLIES.items()
    }
