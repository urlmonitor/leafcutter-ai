"""MODULE: cli_envelope.py
GOAL: Read the headless `claude` CLI's JSON envelope and say why a run failed.
BUSINESS CONTEXT: The CLI reports some failures only on stdout. For example, with no
    credential it exits 1 with EMPTY stderr and prints
    {"is_error":true,"result":"Not logged in · Please run /login"}. An error message built
    from stderr alone is then blank, and a reader cannot tell an outage from a regression.
ARCHITECTURE: Pure helpers over a finished subprocess. Callers pass their own error type,
    so run_agent_eval keeps raising ModelInvocationError without a circular import.
"""
from __future__ import annotations

import json
import logging
import subprocess

logger = logging.getLogger("run_agent_eval")
DETAIL_LIMIT = 400


def failure_detail(stderr: str | None, stdout: str | None) -> str:
    """Return stderr; when it is empty, the stdout envelope's `result` text, else raw stdout."""
    detail = (stderr or "").strip()
    if detail:
        return detail[:DETAIL_LIMIT]
    raw = (stdout or "").strip()
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        return raw[:DETAIL_LIMIT]
    result = envelope.get("result") if isinstance(envelope, dict) else None
    if isinstance(result, str) and result.strip():
        return result.strip()[:DETAIL_LIMIT]
    return raw[:DETAIL_LIMIT]


def envelope_result(completed: subprocess.CompletedProcess, label: str, error: type[Exception]) -> str:
    """Return the envelope's `result` reply; raise `error` naming the real cause otherwise."""
    if completed.returncode != 0:
        detail = failure_detail(completed.stderr, completed.stdout)
        logger.error("%s exited %s: %s", label, completed.returncode, detail)
        msg = f"{label} exited {completed.returncode}: {detail}"
        raise error(msg)
    try:
        envelope = json.loads(completed.stdout or "")
    except json.JSONDecodeError as exc:
        logger.exception("%s returned non-JSON envelope", label)
        msg = f"{label} returned non-JSON envelope"
        raise error(msg) from exc
    result = envelope.get("result") if isinstance(envelope, dict) else None
    if not isinstance(result, str):
        msg = f"{label} envelope has no string 'result'"
        raise error(msg)
    return result


# DECISION HISTORY
# ================================================================================
# - 2026-10-06 [python-coder]: Created. A non-zero CLI exit with empty stderr now reports the
#   stdout envelope's `result` text (e.g. "Not logged in") instead of a blank message; both
#   run_agent_eval invokers share this one envelope reader, which also shrinks that oversized
#   harness under the GE-127b-1 ratchet. (#TICKET-20261006-AgentEvalGateHonestAboutCredentials)
