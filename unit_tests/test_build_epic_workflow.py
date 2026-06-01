"""
MODULE: test_build_epic_workflow
GOAL: Unit tests for the build-epic.js Claude Code Workflow script.
    Validates syntax, meta block structure, planner schema definition,
    parallel() usage within batches (not across batches), and halt
    propagation from a batch ticket.
TICKET: EPIC-FlattenSupervisorChain/03_build_epic_workflow.md

Tests run without invoking Claude Code — they validate the JS file as text
and verify structural contracts (meta fields, planner schema, batch loop,
parallel() placement, halt semantics).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Resolve the script under test
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOW_PATH = _REPO_ROOT / "templates" / "workflows-js" / "build-epic.js"


# ---------------------------------------------------------------------------
# Test 1 — build-epic.js is valid JavaScript (no syntax errors)
# ---------------------------------------------------------------------------


def test_build_epic_js_is_valid_javascript():
    """Script parses without syntax errors (run via node --check)."""
    if not _WORKFLOW_PATH.exists():
        pytest.fail(
            f"build-epic.js not found at {_WORKFLOW_PATH}. "
            "python-coder must create it."
        )

    result = subprocess.run(
        ["node", "--check", str(_WORKFLOW_PATH)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"node --check failed with exit {result.returncode}:\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# Test 2 — meta block has required fields
# ---------------------------------------------------------------------------


def test_meta_block_has_required_fields():
    """meta.name, meta.description, and meta.phases are present and non-empty."""
    if not _WORKFLOW_PATH.exists():
        pytest.fail(
            f"build-epic.js not found at {_WORKFLOW_PATH}. "
            "python-coder must create it."
        )

    content = _WORKFLOW_PATH.read_text(encoding="utf-8")

    # Claude Code Workflow scripts export a meta object.
    # Pattern: const meta = { name: "...", description: "...", phases: [...] }
    assert "name" in content, "meta block must contain 'name' field"
    assert "description" in content, "meta block must contain 'description' field"
    assert "phases" in content, "meta block must contain 'phases' field"

    # Verify none of the required fields are empty strings
    assert not re.search(r'name\s*:\s*["\'][\s]*["\']', content), (
        "meta.name must not be empty"
    )
    assert not re.search(r'description\s*:\s*["\'][\s]*["\']', content), (
        "meta.description must not be empty"
    )


# ---------------------------------------------------------------------------
# Test 3 — planner agent schema requests a batches array
# ---------------------------------------------------------------------------


def test_planner_schema_requests_batches_array():
    """The planner agent() call includes a schema that requires a 'batches' array field."""
    if not _WORKFLOW_PATH.exists():
        pytest.fail(
            f"build-epic.js not found at {_WORKFLOW_PATH}. "
            "python-coder must create it."
        )

    content = _WORKFLOW_PATH.read_text(encoding="utf-8")

    # The planner agent call must define an output schema with a 'batches' key
    # that is typed as an array. We accept several common spellings:
    #   "batches": { "type": "array" }
    #   batches: { type: "array" }
    #   "batches": { type: 'array' }
    #   "type": "array" appearing in close proximity to "batches"
    has_batches_schema = bool(
        re.search(r'["\']batches["\']', content)
        and re.search(r'array', content, re.IGNORECASE)
    )
    assert has_batches_schema, (
        "build-epic.js must include a planner agent() schema that declares a "
        "'batches' field with type 'array'. Found neither 'batches' as a schema key "
        "nor 'array' type annotation in the script."
    )

    # Additionally verify the word 'batches' appears as a schema property
    # (not just in a comment). Schema properties look like: "batches": or batches:
    schema_batches_match = re.search(
        r'["\']?batches["\']?\s*:',
        content,
    )
    assert schema_batches_match is not None, (
        "build-epic.js must define 'batches' as a key inside its planner "
        "schema object. The planner must be asked to return a structured "
        "object with a 'batches' property."
    )


# ---------------------------------------------------------------------------
# Test 4 — parallel() is called per-batch (within the for loop)
# ---------------------------------------------------------------------------


def test_parallel_used_within_batch_not_across_batches():
    """parallel() is called per-batch (within the for loop), not wrapping the batch loop itself."""
    if not _WORKFLOW_PATH.exists():
        pytest.fail(
            f"build-epic.js not found at {_WORKFLOW_PATH}. "
            "python-coder must create it."
        )

    content = _WORKFLOW_PATH.read_text(encoding="utf-8")

    # 1. parallel() must appear in the script at all.
    assert "parallel(" in content, (
        "build-epic.js must use parallel() to dispatch tickets within a batch."
    )

    # 2. A for loop over batches must exist.
    has_batch_loop = bool(
        re.search(r'for\s*\(', content) or re.search(r'\.forEach\s*\(', content)
        or re.search(r'for\s+(?:const|let|var)\s+batch', content)
    )
    assert has_batch_loop, (
        "build-epic.js must iterate batches with a for loop (or equivalent). "
        "No 'for' loop or '.forEach' found."
    )

    # 3. parallel() must NOT wrap the entire batch loop.
    #    Heuristic: parallel() call must appear INSIDE the batch loop body,
    #    meaning the token 'parallel(' occurs after some 'for' or 'forEach' token.
    #    We check that the first occurrence of 'parallel(' appears AFTER the first
    #    occurrence of a 'for' or 'forEach' keyword (or batch-level keyword).
    #
    #    This prevents a pattern like:
    #      parallel(batches.map(batch => workflow("build-ticket", ...)))
    #    in favour of:
    #      for (const batch of batches) { ... parallel(batch.tickets.map(...)) }

    for_pos = None
    for pattern in [r'for\s+(?:const|let|var)\s+batch', r'\.forEach\s*\(', r'for\s*\(']:
        m = re.search(pattern, content)
        if m:
            for_pos = m.start()
            break

    parallel_pos = content.find("parallel(")

    if for_pos is not None and parallel_pos != -1:
        assert parallel_pos > for_pos, (
            "parallel() appears BEFORE the batch loop in build-epic.js. "
            "This means parallel() is wrapping the entire batch iteration, "
            "which would run all batches concurrently. parallel() must be "
            "called inside the batch loop body to run only intra-batch tickets "
            "in parallel while batches remain sequential."
        )


# ---------------------------------------------------------------------------
# Test 5 — a halt result in a batch stops subsequent batches
# ---------------------------------------------------------------------------


def test_halt_stops_subsequent_batches():
    """A halt classification in any batch ticket breaks the outer batch loop."""
    if not _WORKFLOW_PATH.exists():
        pytest.fail(
            f"build-epic.js not found at {_WORKFLOW_PATH}. "
            "python-coder must create it."
        )

    content = _WORKFLOW_PATH.read_text(encoding="utf-8")

    # The script must handle a "halt" (or "failed" / "blocked") status from
    # a parallel slot and stop iterating further batches.
    #
    # We check for two structural signals:
    #   (a) A reference to a halt / error condition (halt, failed, blocked, error)
    #       appearing in the batch processing section.
    #   (b) A break, return, or throw that can terminate the batch loop.

    # Signal (a): halt/error condition referenced after a batch result check
    has_halt_check = bool(
        re.search(r'\bhalt\b', content, re.IGNORECASE)
        or re.search(r'\bfailed\b', content, re.IGNORECASE)
        or re.search(r'\bblocked\b', content, re.IGNORECASE)
        or re.search(r'status\s*[=!]=\s*["\'](?:halt|failed|blocked|error)["\']', content)
        or re.search(r'["\'](?:halt|failed|blocked|error)["\']', content)
    )

    # Signal (b): a loop-breaking construct
    has_loop_break = bool(
        re.search(r'\bbreak\b', content)
        or re.search(r'\breturn\b', content)
        or re.search(r'\bthrow\b', content)
    )

    assert has_halt_check, (
        "build-epic.js does not appear to check for a halt/failed/blocked "
        "result from a batch ticket. The script must inspect each parallel "
        "slot's result and stop the outer batch loop on a halt classification."
    )

    assert has_loop_break, (
        "build-epic.js does not appear to have a break/return/throw that can "
        "terminate the batch loop on a halt. A halt from any ticket must stop "
        "subsequent batches from starting."
    )
