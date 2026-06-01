---
title: "Enable Claude Code Agent Teams via settings.json template"
status: todo
components:
  - build_pipeline
created: 2026-06-01
depends_on:
  - 07_settings_allowlist.md
priority: medium
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/settings.json
  - scripts/build_claude_settings.py
  - docs/reference/agent-teams-constraints.md
agents:
  architect-review: needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
user_facing_surface: null
---

# 08: Enable Claude Code Agent Teams via settings.json template

## Actor / Goal

In order to allow the leafcutter agentic pipeline to use parallel teammate
sessions for epic drives (multiple tickets worked simultaneously by independent
Claude Code instances), we need to enable the experimental Agent Teams feature
via the `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` environment variable in the
deployed `settings.json`.

## Context

Claude Code Agent Teams (experimental, requires v2.1.32+) allow a lead session
to spawn teammate sessions — each with its own full context window and access to
the Agent tool. Unlike sub-agents (depth-1 limit), teammates are independent
sessions that can themselves spawn sub-agents.

This complements the Workflows conversion (tickets 02-04): workflows handle
deterministic orchestration; agent teams handle collaborative parallel work where
teammates need to communicate, share findings, or coordinate on shared state.

### Use cases enabled by agent teams in leafcutter

- **Epic parallel ticket work**: lead spawns one teammate per ready ticket in a
  batch; each teammate drives its ticket through phase agents (using sub-agents).
- **Parallel code review**: multiple reviewer teammates each audit a different
  dimension (security, performance, correctness).
- **Research and design**: competing hypothesis investigation for design decisions.

### Known limitations to document

- **Experimental**: disabled by default; may change or break between versions.
- **One team at a time**: cannot run two epics as separate teams concurrently.
- **No nested teams**: teammates cannot spawn their own teams (but CAN spawn sub-agents).
- **Token cost**: each teammate is a full context window — scales linearly.
- **Permission prompts**: bubble up from all teammates to the lead session.
- **No session resumption**: in-process teammates are lost on /resume or /rewind.
- **Split panes**: require tmux or iTerm2; not supported in VS Code terminal.

### Interaction with Workflows

Agent teams and workflows are complementary, not competing:
- **Workflows** = deterministic JS script controlling agent dispatch. Best for
  sequential pipelines, known phase ordering, retry logic.
- **Agent Teams** = parallel independent sessions that communicate. Best for
  collaborative work where teammates share findings or challenge each other.

A workflow script could spawn an agent that creates a team, or the user could
manually start a team for collaborative exploration before running a workflow for
the structured implementation.

## Acceptance Criteria

```gherkin
Given templates/settings.json deployed by build.py
When the file is inspected
Then it contains "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" }
 And the env block is at the top level of the JSON object

Given a user starts Claude Code in a project with the deployed settings.json
When they ask Claude to "create a team" or describe collaborative work
Then Claude Code allows team creation (the feature is enabled)

Given docs/reference/agent-teams-constraints.md
When a user or agent reads it
Then it documents: experimental status, one-team-at-a-time, no nested teams,
 token cost implications, permission prompt bubbling, version requirement (v2.1.32+),
 and the interaction with workflows

Given the onboard wizard output (from ticket 05)
When the user completes onboarding
Then the output includes a note about agent teams being enabled and a pointer
 to the constraints reference doc
```

## Test Requirements

Tests live in `unit_tests/test_enable_agent_teams.py` and must pass via
`pytest unit_tests/test_enable_agent_teams.py` in the worktree.

```json
{
  "rationale": "Validate that the settings.json template has the env var set, that build_claude_settings deploys it correctly, and that the reference doc exists with required sections.",
  "tests": [
    {
      "name": "test_settings_template_contains_agent_teams_env_var",
      "covers": "templates/settings.json has CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS set to '1' in the env block",
      "location": "unit_tests/test_enable_agent_teams.py"
    },
    {
      "name": "test_settings_json_is_valid_json_after_env_addition",
      "covers": "templates/settings.json remains valid JSON after adding the env block",
      "location": "unit_tests/test_enable_agent_teams.py"
    },
    {
      "name": "test_build_claude_settings_deploys_env_block",
      "covers": "build_claude_settings() copies the env block to the target settings.json",
      "location": "unit_tests/test_enable_agent_teams.py"
    },
    {
      "name": "test_reference_doc_covers_all_constraints",
      "covers": "docs/reference/agent-teams-constraints.md contains headings for: experimental status, one team at a time, no nested teams, token cost, permission prompts, version requirement, workflow interaction",
      "location": "unit_tests/test_enable_agent_teams.py"
    }
  ]
}
```

## Sign-offs

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### python-coder

- [ ] Add `"env"` block to `templates/settings.json`:
  ```json
  {
    "env": {
      "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
    },
    "hooks": { ... existing hooks ... }
  }
  ```
- [ ] Verify `scripts/build_claude_settings.py` already copies the full
  `templates/settings.json` (it does — no code change needed if so). If it
  selectively copies keys, update it to include the `env` block.

### documentation-expert

- [ ] Create `docs/reference/agent-teams-constraints.md` with sections covering:
  - Experimental status and version requirement (v2.1.32+)
  - One team at a time limitation
  - No nested teams (but teammates CAN spawn sub-agents)
  - Token cost implications (linear scaling per teammate)
  - Permission prompt bubbling behaviour
  - Split-pane mode requirements (tmux/iTerm2)
  - Interaction with Claude Code Workflows (complementary, not competing)
  - When to use teams vs workflows vs sub-agents (decision matrix)

### architect-review

- [ ] Confirm that enabling the env var by default is safe (it's experimental —
  does it cause any issues if the user's Claude Code version doesn't support it?
  The feature is simply ignored on older versions.)
- [ ] Confirm the env block placement in settings.json (top-level, alongside hooks).

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Fully reversible — remove the `env` block from settings.json.
  The feature is opt-in by Claude at runtime (Claude proposes a team, user
  confirms before it starts). Enabling the env var does NOT auto-start teams.
- The feature is experimental and may be removed or changed by Anthropic. If
  removed, the env var becomes a no-op (harmless). Document this risk in the
  reference doc.
