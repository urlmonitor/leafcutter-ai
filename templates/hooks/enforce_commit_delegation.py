"""
MODULE: enforce_commit_delegation.py
GOAL: PreToolUse hook that blocks a ``git commit`` call unless
    ``COMMIT_AGENT_MODE=1`` is present in the environment. This enforces
    the rule that only the ``commit`` agent template is authorised to call
    ``git commit`` directly; all other agent contexts must dispatch the
    ``commit`` agent via the Agent tool instead.
BUSINESS CONTEXT: The main Claude agent occasionally calls ``git commit``
    directly, bypassing the confirmation gate (Step 3 of commit.md), the
    pre-commit hook failure → autofix path (Step 5), the sign-off recording,
    the background-commit safety check, and the anomaly reporting — the entire
    value of having a dedicated commit agent. This hook mechanically enforces
    the delegation contract: every ``git commit`` call must originate from
    within the ``commit`` agent template, which sets ``COMMIT_AGENT_MODE=1``
    before its own call. Any other context is blocked with an actionable error.
ARCHITECTURE: PreToolUse hook on ``Bash`` tool calls containing ``git commit``.
    Checks ``COMMIT_AGENT_MODE`` env var (set only within the commit agent
    template's Step 4). If the env var is absent or not exactly ``"1"``, emits
    a JSON block decision. Fail-open on any exception, malformed stdin, or
    missing command key — identical to the fail-open contract used by
    ``check_commit_ticket_staged.py``.
DOC_LINKS:
  - docs/how-to/agent-commit-discipline.md
  - templates/agents/commit.md

PreToolUse hook contract (Bash tool):
- Exit 0 with no output = silently allow
- Exit 0 with {"decision": "block", "reason": "..."} = block the tool call
- Exit 1 = allow (non-zero exit is not blocking for PreToolUse on Bash)

This hook emits JSON and exits 0 to leverage the block-decision contract.
"""
from __future__ import annotations

import json
import os
import sys


def _is_git_commit_call(payload: dict) -> bool:
    """Return True when the Bash tool input contains ``git commit``.

    Intercepts both ``git commit`` and ``git commit --amend`` — both
    require the commit agent. Non-commit Bash calls (git add, git status,
    etc.) exit 0 immediately.

    Args:
        payload: Parsed PreToolUse JSON payload.

    Returns:
        True when the ``command`` field contains the literal string
        ``git commit``.
    """
    tool_input = payload.get("tool_input") or {}
    command = str(tool_input.get("command") or tool_input.get("cmd") or "")
    return "git commit" in command


def _is_commit_agent_mode(payload: dict | None = None) -> bool:
    """Return True when the call originates from the commit agent.

    Two detection paths are supported:

    1. **Process environment**: ``os.environ["COMMIT_AGENT_MODE"] == "1"``.
       This is set when the harness injects the variable into the Claude Code
       process before spawning the commit agent.

    2. **Inline command prefix**: the Bash command string starts with the
       token ``COMMIT_AGENT_MODE=1`` (shell inline-assignment syntax).  The
       commit agent template uses this form (``COMMIT_AGENT_MODE=1 git …``)
       which sets the variable for the shell child but not for the hook's own
       process (spawned before the shell runs).  Checking the raw command
       covers that case.

    Either path is sufficient — the check is OR-logic.

    Args:
        payload: Optional PreToolUse JSON payload.  When provided, the
            ``command`` field is inspected for the inline prefix.

    Returns:
        True when either detection path matches; False otherwise.
    """
    if os.environ.get("COMMIT_AGENT_MODE", "") == "1":
        return True
    if payload is not None:
        tool_input = payload.get("tool_input") or {}
        command = str(tool_input.get("command") or tool_input.get("cmd") or "")
        # Accept "COMMIT_AGENT_MODE=1 git commit …" (inline env prefix)
        tokens = command.lstrip().split()
        if "COMMIT_AGENT_MODE=1" in tokens:
            return True
    return False


def _build_block_message() -> str:
    """Build the human-readable blocking reason.

    Returns:
        Multi-line string injected back to the agent as a blocking reason,
        covering: (a) what was blocked, (b) why, and (c) the exact corrective
        action.
    """
    return (
        "PreToolUse blocked: direct git commit is not allowed.\n"
        "\n"
        "What was blocked: a `git commit` call was intercepted outside the "
        "commit agent context (COMMIT_AGENT_MODE is not set to '1').\n"
        "\n"
        "Why: calling `git commit` directly bypasses the confirmation gate "
        "(Step 3 of commit.md), the pre-commit hook failure → autofix path "
        "(Step 5), the sign-off recording, and the background-commit safety "
        "checks. These safeguards only run when commits flow through the "
        "dedicated `commit` agent template.\n"
        "\n"
        "Corrective action: Dispatch the commit agent via the Agent tool "
        "instead of calling git commit directly."
    )


def main() -> None:
    """Entry point. Reads the PreToolUse payload from stdin and emits a decision."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (ValueError, UnicodeDecodeError):
        # Malformed or undecodable payload — fail-open, do not block
        sys.exit(0)

    # Only intercept Bash tool calls containing "git commit"
    if not _is_git_commit_call(payload):
        sys.exit(0)

    # Allow when the commit agent has set its sentinel env var (either via
    # process environment or via the inline COMMIT_AGENT_MODE=1 prefix in
    # the command string — the commit agent template uses the latter form).
    if _is_commit_agent_mode(payload):
        sys.exit(0)

    # Block: direct git commit from a non-commit-agent context
    print(json.dumps({"decision": "block", "reason": _build_block_message()}))
    sys.exit(0)


if __name__ == "__main__":
    main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 09:30 [TICKET-20260605-EnforceCommitAgentDelegation]:
  Initial implementation. PreToolUse hook on Bash tool calls containing
  "git commit". Blocks unless COMMIT_AGENT_MODE=1 is present in the
  environment — a sentinel set only within the commit agent template's
  Step 4 before its own git commit call. Fail-open on all exceptions,
  malformed stdin, and missing command key. Mirrors the structure of
  check_commit_ticket_staged.py: same module docstring sections, same
  JSON block-decision contract, same fail-open exit(0) pattern.
  (#TICKET-20260605-EnforceCommitAgentDelegation)
- 2026-06-08 12:00 [commit]: Add inline command-prefix detection path.
  The hook previously only checked os.environ["COMMIT_AGENT_MODE"], but
  the commit agent template uses the shell inline-assignment form
  "COMMIT_AGENT_MODE=1 git commit …", which sets the var for the shell
  child process but NOT for the hook's own Python process (spawned before
  the shell runs). Added a second detection path that inspects the raw
  command string tokens for the inline prefix, so the hook correctly
  passes commits from the commit agent template.
  (#TICKETLESS reason=hook-correctness-fix-no-ticket-needed)
====================================================================
"""
