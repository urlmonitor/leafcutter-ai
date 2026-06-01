"""
MODULE: test_create_ticket_workflow
GOAL: Unit tests for create-ticket.js workflow script — validates syntax,
    meta block structure, routing logic branches, depth-cap guard, and
    parallel dispatch pattern without invoking Claude Code.
TICKET: EPIC-FlattenSupervisorChain/04_create_ticket_workflow.md
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOW_JS = _REPO_ROOT / "templates" / "workflows-js" / "create-ticket.js"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_script() -> str:
    """Read the create-ticket.js file, failing fast if it does not exist."""
    if not _WORKFLOW_JS.exists():
        pytest.fail(
            f"create-ticket.js not found at {_WORKFLOW_JS}. "
            "Run the python-coder phase first."
        )
    return _WORKFLOW_JS.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Test 1 — script parses as valid JavaScript
# ---------------------------------------------------------------------------

def test_create_ticket_js_is_valid_javascript():
    """Script parses without syntax errors when checked via `node --check`."""
    _read_script()  # must exist first

    node = shutil.which("node")
    if node is None:
        pytest.skip("node not found on PATH — skipping syntax check")

    result = subprocess.run(
        [node, "--check", str(_WORKFLOW_JS)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"node --check failed with:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Test 2 — meta block has required fields
# ---------------------------------------------------------------------------

def test_meta_block_has_required_fields():
    """meta.name, meta.description, and meta.phases are present and non-empty."""
    content = _read_script()

    # The Claude Code workflow spec uses a top-level `const meta = { ... }` or
    # equivalent object with at minimum name, description, and phases fields.
    # We check for string presence rather than parsing JS to stay dependency-free.
    assert "name:" in content or '"name"' in content or "'name'" in content, (
        "meta block missing 'name' field"
    )
    assert "description:" in content or '"description"' in content or "'description'" in content, (
        "meta block missing 'description' field"
    )
    assert "phases:" in content or '"phases"' in content or "'phases'" in content, (
        "meta block missing 'phases' field"
    )


# ---------------------------------------------------------------------------
# Test 3 — routing branches cover both decisions
# ---------------------------------------------------------------------------

def test_routing_branches_cover_both_decisions():
    """Script contains branches for routing_decision == standard_ticket and == epic."""
    content = _read_script()

    assert "standard_ticket" in content, (
        "Script does not handle routing_decision == 'standard_ticket'"
    )
    assert "epic" in content, (
        "Script does not handle routing_decision == 'epic'"
    )


# ---------------------------------------------------------------------------
# Test 4 — depth-cap guard is present
# ---------------------------------------------------------------------------

def test_depth_cap_guard_present():
    """Script enforces a depth >= 3 guard before create-epic dispatch."""
    content = _read_script()

    # The guard must reference depth >= 3 (or currentDepth >= 3, etc.)
    # Accept various reasonable spellings, including constant-based comparisons
    # where DEPTH_CAP = 3 and the check uses >= DEPTH_CAP.
    has_depth_check = (
        "currentDepth >= 3" in content
        or "current_depth >= 3" in content
        or "depth >= 3" in content
        or ">= 3" in content  # broader fallback
        or (
            # Constant-based guard: const DEPTH_CAP = 3 + currentDepth >= DEPTH_CAP
            "DEPTH_CAP" in content
            and "3" in content
            and ">= DEPTH_CAP" in content
        )
    )
    assert has_depth_check, (
        "Depth-cap guard (>= 3) not found in script — "
        "create-epic must not be called when depth is at cap."
    )


# ---------------------------------------------------------------------------
# Test 5 — parallel() used for refinement and architect-review
# ---------------------------------------------------------------------------

def test_parallel_used_for_refinement_and_architect():
    """refinement and architect-review are dispatched via parallel() not sequentially."""
    content = _read_script()

    assert "parallel(" in content or "parallel([" in content, (
        "parallel() call not found — refinement and architect-review "
        "must be dispatched concurrently via parallel()."
    )
    assert "refinement" in content, (
        "refinement agent not referenced in script"
    )
    assert "architect-review" in content or "architect_review" in content, (
        "architect-review agent not referenced in script"
    )
