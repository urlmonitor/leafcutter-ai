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
# Test 4 — epic routing returns an instructional error (no agent dispatch)
# ---------------------------------------------------------------------------

def test_epic_routing_returns_instructional_error():
    """Epic path returns an instructional error instead of dispatching create-epic.

    In EPIC-AcPipelineConsolidation v2.0.0, create-epic was removed as a
    registered agent.  The script must detect routing_decision == 'epic' and
    return a status:'error' message directing the user to run /create-epic
    directly.  No depth-cap guard is needed because there is no agent dispatch.
    """
    content = _read_script()

    # The epic branch must set status: "error"
    assert '"error"' in content or "'error'" in content, (
        "Script does not contain a status:'error' return for the epic path"
    )
    # The instructional message must mention /create-epic so the user knows
    # what to do next.
    assert "/create-epic" in content, (
        "Script epic-path error message does not mention /create-epic — "
        "users need to know the correct fallback command."
    )
    # create-epic must NOT be dispatched as an agent() call (it was removed).
    assert 'agentType: "create-epic"' not in content, (
        "Script still dispatches create-epic as an agent — it was removed in v2.0.0"
    )


# ---------------------------------------------------------------------------
# Test 5 — architect-review dispatched sequentially; refinement removed
# ---------------------------------------------------------------------------

def test_architect_review_dispatched_sequentially_no_refinement():
    """architect-review is called via agent() sequentially; refinement is absent.

    In EPIC-AcPipelineConsolidation v2.0.0, refinement and ticket-wiring agents
    were removed and their responsibilities merged into business-analyst.
    architect-review is now invoked via a single agent() call (not parallel()),
    conditional on the BA output flagging architectural impact.
    """
    content = _read_script()

    # architect-review must still be referenced (it is not removed, only sequential)
    assert "architect-review" in content or "architect_review" in content, (
        "architect-review agent not referenced in script"
    )
    # architect-review must be called via agent(), not parallel()
    assert 'agentType: "architect-review"' in content, (
        "architect-review is not dispatched via agent() — expected sequential dispatch"
    )
    # refinement agent must be absent (intentionally removed in v2.0.0)
    assert '"refinement"' not in content and "'refinement'" not in content, (
        "refinement agent reference still present — it was removed in v2.0.0"
    )


# ---------------------------------------------------------------------------
# Test 6 — retirement contract: retirement guard is present (AC-6 / AC-7)
# ---------------------------------------------------------------------------

def test_create_ticket_retired():
    """create-ticket.js has a retirement guard that emits an error and exits.

    AC-6 (Option C): When create-ticket.js is invoked, it must emit a clear
    error message: "create-ticket.js is retired. Use /plan-feature + /build-ac
    instead." and return exit_code 1 so there is no silent-continuation mode.

    AC-7 (Option C): Unit test verifies the retirement contract: the guard is
    present, names the canonical replacement, and exits with code 1.
    """
    content = _read_script()

    # The retirement guard must be the FIRST real statement in `run()` —
    # i.e., it must return before any agent dispatch call.  We confirm this
    # by checking that the return statement containing exit_code:1 appears
    # in the file and comes before any `await agent(` call.
    assert "exit_code: 1" in content or '"exit_code": 1' in content or "exit_code:1" in content, (
        "create-ticket.js retirement guard must return exit_code 1"
    )

    # The retirement message must name the canonical replacement path.
    assert "/plan-feature" in content, (
        "Retirement error message must mention /plan-feature as the canonical replacement"
    )
    assert "/build-ac" in content, (
        "Retirement error message must mention /build-ac as the canonical replacement"
    )

    # The retirement message must be a status: "error" return.
    assert '"error"' in content or "'error'" in content, (
        "Retirement guard must return status: 'error'"
    )

    # The guard must appear before the first agent dispatch in run().
    # Find the positions of the guard return and the first agent() call.
    guard_marker = "exit_code: 1"
    agent_dispatch_marker = 'agentType: "business-analyst"'

    guard_pos = content.find(guard_marker)
    dispatch_pos = content.find(agent_dispatch_marker)

    assert guard_pos != -1, (
        f"guard marker '{guard_marker}' not found in create-ticket.js"
    )
    assert dispatch_pos != -1, (
        f"dispatch marker '{agent_dispatch_marker}' not found in create-ticket.js — "
        "the dead-code section should still be present for archaeological reference"
    )
    assert guard_pos < dispatch_pos, (
        "Retirement guard (exit_code 1) must appear BEFORE the business-analyst "
        "dispatch in the file — the guard short-circuits execution before any "
        "agent is invoked"
    )


# ---------------------------------------------------------------------------
# Test 7 — no active routing dispatches to create-ticket.js (AC-6-Edge)
# ---------------------------------------------------------------------------

def test_create_ticket_dispatch_blocked():
    """No active routing path dispatches to a live create-ticket.js invocation.

    AC-6-Edge: A grep across templates/, skills/, agents/, and docs/ must show
    that every reference to 'create-ticket.js' is either a comment, a
    documentation link, or a deprecated-dispatch error message — not active
    routing code.

    This test checks the templates/ tree (the source of deployed artefacts).
    It excludes the file itself and known-safe ADR / reference doc locations.
    """
    templates_root = _REPO_ROOT / "templates"

    # Patterns that constitute ACTIVE routing — i.e., something that would
    # dispatch a live create-ticket.js invocation at runtime.
    active_routing_patterns = [
        'require("./create-ticket")',
        "require('./create-ticket')",
        'import("./create-ticket")',
        "import('./create-ticket')",
        'import * from "./create-ticket"',
        "import * from './create-ticket'",
        'run("create-ticket")',
        "run('create-ticket')",
    ]

    violations: list[str] = []

    for js_file in templates_root.rglob("*.js"):
        # Skip the retired file itself — it's the subject of this test, not a
        # caller.
        if js_file.name == "create-ticket.js":
            continue
        file_content = js_file.read_text(encoding="utf-8")
        for pattern in active_routing_patterns:
            if pattern in file_content:
                violations.append(
                    f"{js_file.relative_to(_REPO_ROOT)}: contains active routing "
                    f"pattern {pattern!r}"
                )

    assert not violations, (
        "Active routing to create-ticket.js detected in templates/:\n"
        + "\n".join(f"  - {v}" for v in violations)
    )
