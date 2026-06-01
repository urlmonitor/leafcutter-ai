---
title: "Reference: Claude Code Agent Teams Constraints"
type: reference
status: active
created: 2026-06-01
last_updated: 2026-06-01
components:
  - "build_pipeline"
related_docs:
  - "docs/reference/claude-code-hooks.md"
  - "docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md"
---

# Claude Code Agent Teams — Constraints and Usage Guide

This reference documents the constraints, requirements, and interaction
patterns for the Claude Code Agent Teams experimental feature as enabled
by `leafcutter` via `templates/settings.json`.

## Experimental Status and Version Requirement

Agent Teams is an **experimental feature** in Claude Code, available from
version **v2.1.32** and later. The feature is enabled by setting:

```json
"env": {
  "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
}
```

in `.claude/settings.json`. The `leafcutter` build pipeline deploys this
setting via `templates/settings.json` → `build_claude_settings.py`.

**On older Claude Code versions** (before v2.1.32): the environment variable
is simply ignored. No negative effects occur — the feature is a no-op on
unsupported versions.

**Stability caveat**: As an experimental feature, Agent Teams may change
behaviour, be renamed, or be removed by Anthropic between Claude Code
releases without prior notice. If the `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`
env var ceases to have effect, it becomes a harmless no-op.

## One Team at a Time

Claude Code supports **at most one active team per session**. You cannot
run two separate epics as parallel teams within the same Claude Code session.
Attempting to start a second team while one is active will either queue or
reject the second start.

**Workaround**: Use separate terminal sessions (one Claude Code instance per
team) if you need to drive multiple epics concurrently. Each session can have
its own team without conflict.

## No Nested Teams

Teammate sessions spawned by the lead session **cannot themselves create
teams**. The nesting depth for teams is exactly 1.

However, teammates CAN spawn sub-agents (using the `Agent` tool at depth 1).
This is the expected pattern for the leafcutter pipeline: the lead session
manages the epic-level parallelism as a team, while each teammate drives its
assigned ticket through its phase agents as sub-agents.

The hierarchy is:
```
Lead session (team coordinator)
  └── Teammate A (drives ticket 02) → sub-agent: python-coder, test-runner, ...
  └── Teammate B (drives ticket 05) → sub-agent: python-coder, test-runner, ...
```

## Token Cost Implications

Each teammate session is a **full independent context window**. Token costs
scale **linearly** with the number of teammates in the team:

- 1 teammate: ~2x the token cost of a solo session (lead + 1 teammate)
- 3 teammates: ~4x the token cost
- N teammates: approximately (N+1)x the token cost

For large epic drives with many parallel tickets, this cost multiplier is
significant. Use teams only for genuinely independent parallel work; avoid
spawning teammates for trivially sequential tasks.

**Token budget guidance:**
- Keep teams small (2–4 teammates) for most epic drives.
- Prefer sequential drives for short tickets (under 10 agent phases each).
- Use teams for wide batches where each ticket is substantial and independent.

## Permission Prompt Bubbling

Permission prompts from teammate sessions **bubble up to the lead session**.
When a teammate encounters a tool call that requires user approval, the
approval request appears in the lead session's interface.

Implications:
- The user must be present and attentive during team operation.
- Long-running unattended team drives may stall waiting for permissions.
- Pre-configuring `allowedTools` in `settings.json` (as leafcutter does) is
  the primary mitigation — tools in the allowlist do not generate prompts.

## Split-Pane Mode Requirements

Agent Teams uses a split-pane display to show the lead session and teammate
sessions simultaneously. This requires:

- **tmux** (terminal multiplexer), OR
- **iTerm2** (macOS terminal with native split-pane support)

Agent Teams in split-pane mode is **not supported in the VS Code integrated
terminal**. If you are using VS Code, run Claude Code in an external terminal
(iTerm2 on macOS, Windows Terminal + tmux on Linux/WSL) to use this feature.

## No Session Resumption

Teammate sessions are **in-process** to the lead session. If the lead session
is interrupted (via `/resume`, `/rewind`, crash, or network disconnect),
all active teammate sessions are lost.

Implications:
- Interrupted team drives require a full restart of the team.
- Save state (via ticket frontmatter sign-offs and Comments) as teammates
  complete each phase, so a resumed drive can pick up from the last signed-off
  agent without replaying completed work.
- The leafcutter ticket phase sign-off system (`signoff` skill) is specifically
  designed to make partial-completion recovery tractable.

## Interaction with Claude Code Workflows

Agent Teams and Claude Code Workflows are **complementary, not competing**.
Use the right tool for the task:

| Dimension | Workflows | Agent Teams |
|---|---|---|
| Control flow | Deterministic JS scripts | Collaborative parallel sessions |
| Best for | Sequential pipelines, known phase order, retry logic | Parallel work, multi-reviewer, research |
| Resumption | Stateless scripts restart cleanly | Teams are lost on interrupt |
| Overhead | Low (script execution) | High (N × context window cost) |
| User interaction | Scriptable, unattended | Requires presence for permission prompts |

**Typical combined usage** in leafcutter:
1. A Workflow script (`/build-feature`) orchestrates the epic loop and
   dispatches ticket batches.
2. For large parallel batches, the workflow spawns an agent that creates a
   team, with one teammate per ready ticket.
3. Each teammate uses sub-agents (via the `Agent` tool) to drive its ticket
   through the phase pipeline.
4. The Workflow collects team results and proceeds to the next batch.

A workflow script can also invoke an agent team for the research/design phase
(competing hypotheses, parallel investigation) before the structured
implementation workflow begins.

## When to Use Teams vs Workflows vs Sub-agents

```
Decision tree:
1. Is the work strictly sequential with known phase order?
   YES → Use a Workflow (or ticket-supervisor sub-agents)
   NO  → Continue to 2.

2. Does the work require parallel independent sessions (each with full context)?
   YES → Consider Agent Teams
   NO  → Continue to 3.

3. Do you need depth-1 sub-agents for bounded tasks?
   YES → Use the Agent tool (sub-agents)
   NO  → Run the work inline in the lead session.
```

In summary:
- **Workflows** for orchestration and retry logic.
- **Agent Teams** for parallel collaborative work across tickets.
- **Sub-agents** for bounded, single-task delegation within a ticket's phase.
