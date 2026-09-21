r"""
MODULE: unit_tests/workflows/_bo3900e_resolver_harness.py
GOAL: Extract the REAL BO-3900e depends_on resolver — resolveDependsOnPath()
    plus the BO-3900 path helpers it calls (classifyPathForm,
    normalizePathForm, resolvePathOntoRoot, toWorktreePath) — out of
    build-feature.js's own source text and run it via a real Node.js
    subprocess, with a caller-controlled stub for readTicketRecordBack(), so
    the resolver's candidate-order behaviour (including the done/ fallback
    and the ticket-itself-in-done/ case) is exercised precisely against the
    SHIPPED code — never a Python reimplementation that could silently
    drift from it.
BUSINESS CONTEXT: unit_tests/_workflow_engine_harness.py's agent() mock
    gives ONE static reply per label — every readTicketRecordBack()
    dispatch in a harness-driven run receives the SAME object, so a run
    cannot make one candidate path "not found" and a later candidate
    "found". Proving the done/-subfolder and ticket-itself-in-done/
    fallback order (BO-3900e's M3 mutation) needs a per-path-aware stub;
    this module supplies exactly that, scoped to the resolver alone. The
    reachability angle still drives build-feature.js's own top-level body
    through unit_tests/_workflow_engine_harness.py — this module is a
    supplement for the criterion/boundary/failure/seam angles, per
    BO-3900's own test_rationale precedent (see
    unit_tests/portability/_bo3900a_js_classifier.py, which this module is
    a sibling of).
ARCHITECTURE: Same extract-from-source-text-and-run-in-Node pattern as
    unit_tests/portability/_bo3900a_js_classifier.py, applied to a later
    slice of the same file — the resolver immediately follows the BO-3900
    path-helper block, which it also needs, so both are extracted together
    as one contiguous span.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

_START_MARKER = "// BO-3900-PATH-HELPERS-START"
_END_ANCHOR = (
    "\n// ---------------------------------------------------------------------------"
    "\n// driveTicketPhases"
)


def extract_resolver_block(script_path: Path) -> str:
    """Slice the BO-3900 path helpers + BO-3900e resolver out of `script_path`.

    Raises:
        AssertionError: the start marker or end anchor is absent — the
            script does not yet carry resolveDependsOnPath (a legitimate
            RED-baseline state before BO-3900e is implemented).
    """
    text = script_path.read_text(encoding="utf-8")
    start = text.find(_START_MARKER)
    end = text.find(_END_ANCHOR, start if start != -1 else 0)
    if start == -1 or end == -1:
        raise AssertionError(
            f"{script_path} does not carry the BO-3900e resolver block "
            f"(start marker {_START_MARKER!r} or end anchor not found) — "
            "resolveDependsOnPath has not landed yet."
        )
    return text[start:end]


def _run_node(driver_source: str, timeout: int = 10) -> Any:
    try:
        proc = subprocess.run(
            ["node", "-e", driver_source],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AssertionError(f"node resolver driver could not be run: {exc}") from exc
    if proc.returncode != 0:
        raise AssertionError(
            f"node resolver driver failed (exit {proc.returncode}): {proc.stderr}"
        )
    return json.loads(proc.stdout)


def resolve_depends_on_path(
    script_path: Path,
    entry: str,
    ticket_worktree_path: str,
    worktree_path: str,
    readback_by_path: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Call the REAL resolveDependsOnPath(entry, ticketWorktreePath, worktreePath).

    Args:
        script_path: Path to build-feature.js (or any script carrying the
            same BO-3900e resolver block).
        entry: The raw depends_on list entry, verbatim.
        ticket_worktree_path: The dependant ticket's own resolved worktree
            path, exactly as the real call sites compute it.
        worktree_path: The run's worktree root.
        readback_by_path: Maps an EXACT candidate path to the
            readTicketRecordBack reply it should receive. A candidate path
            absent from this map receives ``{"readable": False}`` — nothing
            lives there — matching a real dispatch's own not-found shape.

    Returns:
        The resolver's own ``{resolved, reported, record}`` reply.
    """
    resolver = extract_resolver_block(script_path)
    stub = (
        "\nconst __readbackByPath__ = "
        + json.dumps(readback_by_path)
        + ";\nasync function readTicketRecordBack(p) {"
        + " return Object.prototype.hasOwnProperty.call(__readbackByPath__, p)"
        + " ? __readbackByPath__[p] : { readable: false }; }\n"
    )
    call = (
        "resolveDependsOnPath("
        + json.dumps(entry)
        + ", "
        + json.dumps(ticket_worktree_path)
        + ", "
        + json.dumps(worktree_path)
        + ").then((r) => process.stdout.write(JSON.stringify(r)));\n"
    )
    return _run_node("'use strict';\n" + resolver + stub + call)


# DECISION HISTORY
# ================================================================================
# - 2026-09-16 12:00 [python-coder]: Created to give the BO-3900e test family a
#   per-path-aware readTicketRecordBack stub, since
#   unit_tests/_workflow_engine_harness.py's agent() mock gives one static reply
#   per label and cannot prove the resolver's candidate fallback order.
#   (#TICKETLESS reason=ac-bo-3900e-direct-implementation)
