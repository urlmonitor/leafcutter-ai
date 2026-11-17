"""
MODULE: test_bo2200c5vii_doc_expert_leaf_mode_dispatch
GOAL: Regression test for BO-2200c-5-vii -- build-feature.js dispatches
    documentation-expert as a flat depth-1 agent() call, which has no Agent
    tool, so the orchestrator template (which forbids authoring doc files
    itself) always returns blocker. The dispatch prompt must carry a
    leaf-mode instruction for documentation-expert ONLY.

Drives the REAL build-feature.js through the Node-backed engine harness
(unit_tests/_workflow_engine_harness.py) and asserts on the prompt actually
sent to the documentation-expert dispatch; a negative control proves another
phase (pr-reviewer) does not receive the leaf-mode text.
"""

from __future__ import annotations

import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2, workspace_ensure_reply  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_BUILD_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "build-feature.js"

_TIMEOUT = 30

_TICKET_ABS_PATH = "/tmp/bo2200c5vii-worktree/tickets/01_todo/05_ticket.md"
_WORKTREE_ABS_PATH = "/tmp/bo2200c5vii-worktree"

_SPECIALISTS = (
    "how-to-author",
    "reference-author",
    "explanation-author",
    "adr-author",
    "architecture-diagram-author",
    "architecture-author",
)


def _drive() -> HarnessResult:
    label_responses = {
        "resolve-target": {
            "target_type": "ticket",
            "ticket_path": _TICKET_ABS_PATH,
            "worktree_path": _WORKTREE_ABS_PATH,
        },
        # BO-4300c-3: the workspace is the maker's answer (one workspace-ensure step), not a facts lookup.
        "workspace-ensure": workspace_ensure_reply(_WORKTREE_ABS_PATH, branch="fixture"),
        "ticket-planner": {
            "ticket_path": _TICKET_ABS_PATH,
            "title": "BO-2200c-5-vii leaf-mode fixture ticket",
            "files_touched": ["docs/how-to/thing.md"],
            "has_test_requirements": True,
            "existing_test_files": ["unit_tests/some_module/test_thing.py"],
            "ordered_phases": [
                {"agent": "documentation-expert", "status": "needed"},
                {"agent": "pr-reviewer", "status": "needed"},
            ],
        },
        "documentation-expert": {"status": "ok"},
        "pr-reviewer": {"status": "ok"},
    }
    result = run_workflow_under_e2(
        _BUILD_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=label_responses,
        args={"target": _TICKET_ABS_PATH},
    )
    assert result.error == "", f"Harness error: {result.error}"
    return result


def _prompt_for(result: HarnessResult, label: str) -> str:
    calls = [c for c in result.agent_calls if c.label == label]
    assert calls, (
        f"Expected a {label} dispatch. Labels: "
        f"{[c.label for c in result.agent_calls]}"
    )
    prompt = calls[0].prompt
    assert isinstance(prompt, str) and _TICKET_ABS_PATH in prompt, (
        f"{label} prompt is not a live capture of the ticket dispatch: {prompt!r}"
    )
    return prompt


def test_documentation_expert_dispatch_prompt_carries_leaf_mode_instruction():
    # covers: BO-2200c-5-vii
    # angle: reachability
    """The documentation-expert dispatch prompt must say it cannot spawn
    sub-agents, tell it to author docs itself (overriding 'never author'),
    name the specialists and template locations, and forbid handing off to a
    specialist outside the ticket's agents map.

    RED today: the prompt carries no leaf-mode instruction at all.
    """
    prompt = _prompt_for(_drive(), "documentation-expert")
    lowered = prompt.lower()

    assert "leaf mode" in lowered or "leaf-mode" in lowered, (
        f"No leaf-mode instruction in documentation-expert prompt:\n{prompt}"
    )
    assert "cannot spawn" in lowered or "can not spawn" in lowered or (
        "no agent tool" in lowered
    ), f"Prompt does not say sub-agents cannot be spawned:\n{prompt}"
    for specialist in _SPECIALISTS:
        assert specialist in prompt, (
            f"Prompt does not name specialist {specialist!r}:\n{prompt}"
        )
    assert ".claude/agents/" in prompt and "templates/agents/" in prompt, (
        f"Prompt must point at the specialist templates (.claude/agents/ with "
        f"templates/agents/ fallback):\n{prompt}"
    )
    assert "Agent Contracts" in prompt, (
        f"Prompt must reference the '## Agent Contracts -> ### "
        f"documentation-expert' block:\n{prompt}"
    )
    assert "never author" in lowered or "overrid" in lowered, (
        f"Prompt must explicitly override the 'never author yourself' rule "
        f"for this dispatch:\n{prompt}"
    )
    assert "agents map" in lowered, (
        f"Prompt must forbid handoff to a specialist that is not a key of "
        f"the ticket's agents map:\n{prompt}"
    )


def test_other_phases_do_not_receive_leaf_mode_text():
    # covers: BO-2200c-5-vii
    # angle: discrimination
    """Negative control: pr-reviewer, driven in the same run, must not get the
    leaf-mode text (a fix that appended it to every phase would fail here),
    and the pr-reviewer prompt is a live capture so this is not vacuous.
    """
    result = _drive()
    doc_prompt = _prompt_for(result, "documentation-expert")
    pr_prompt = _prompt_for(result, "pr-reviewer").lower()

    # Tie the control to the fix: the doc-expert prompt must have the text...
    assert "leaf" in doc_prompt.lower(), (
        "documentation-expert prompt lacks leaf-mode text, so the negative "
        f"control below is not tied to the fix:\n{doc_prompt}"
    )
    # ...and pr-reviewer must not.
    assert "leaf mode" not in pr_prompt and "leaf-mode" not in pr_prompt
    assert "how-to-author" not in pr_prompt
    assert "reference-author" not in pr_prompt
