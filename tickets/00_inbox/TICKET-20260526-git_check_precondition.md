---
title: "Add git-check precondition to git-dependent workflows"
status: todo
components:
  - build_pipeline
created: 2026-05-26
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
files_touched:
  - templates/agents/finalize-feature.md
  - templates/agents/changelog-agent.md
agents:
  architect-review: needed
  python-coder: not_needed
  test-writer: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  change-scope-reviewer: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  sql-coder: not_needed
  sql-query: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: needed
user_facing_surface: agent_orchestrated
actuation_contract: "Invokes finalize-feature (or changelog-agent) in a non-git directory; agent emits a user-friendly warning identifying the missing git context and skips all git-dependent steps without throwing a fatal error."
roadmap_phase: phase_1
advances_current_outcome: true
---

# Add git-check precondition to git-dependent workflows

## Actor / Goal

In order to operate reliably in worktrees with unusual layouts, simulated
environments, and non-git testing setups, we need a git-check precondition
at the entry point of `finalize-feature` and `changelog-agent` so that
operators receive a clear warning and graceful degradation instead of a
`fatal: not a git repository` crash.

## Context

From the 2026-05-22 EPIC-AntigravitySupport retrospective
(`docs/retrospectives/2026-05-22-epic-antigravity-support.md`), the
`finalize-feature` and `changelog` workflows shell out to git heavily.
When invoked in environments without a properly initialized git context
— worktrees with unusual layouts, simulated CI environments, or local
non-git testing setups — those calls throw `fatal: not a git repository`,
which bubbles up as an unhandled crash and forced the epic to close
manually.

This is the second unchecked action item from that retrospective. It is
a targeted, low-risk change: add a guard at the top of each affected
agent template, keep the happy path unchanged, and degrade gracefully
when the guard fails.

**Scope**: `finalize-feature` and `changelog-agent` are the two agents
explicitly identified in the retrospective. Any other agent that shells
out to git as its first meaningful action should apply the same guard
during the same pass.

## Acceptance Criteria

```gherkin
Given the finalize-feature agent is invoked
When git rev-parse --is-inside-work-tree returns a non-zero exit code
Then the agent emits a user-friendly warning naming the missing git context
 And the agent skips all git-dependent steps
 And the agent exits cleanly without a fatal error

Given the changelog-agent is invoked
When git rev-parse --is-inside-work-tree returns a non-zero exit code
Then the agent emits a user-friendly warning naming the missing git context
 And the agent skips all git-dependent steps
 And the agent exits cleanly without a fatal error

Given the finalize-feature agent is invoked inside a valid git worktree
When git rev-parse --is-inside-work-tree returns true
Then the agent proceeds with all steps unchanged
```

## Smoke Fixture

```yaml
surface: finalize-feature
fixture_input: |
  (invoke from a temp directory with no .git; expect warning output)
assertion: "git repository|not a git|git context|warning|skipping"
placeholder_signature: "TODO|PLACEHOLDER|not implemented"
```

## Sign-offs

- [ ] architect-review
- [ ] user-surface-smoker
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] In `templates/agents/finalize-feature.md`: add a Step 0 (pre-flight
  git check) that runs `git rev-parse --is-inside-work-tree` before any
  other action. On failure, emit: "Warning: not inside a git work tree.
  git-dependent steps will be skipped. To fix, run this command from within
  your repository root." then stop or skip git steps gracefully.
- [ ] In `templates/agents/changelog-agent.md`: apply the same Step 0
  git-check guard with identical messaging conventions.
- [ ] Audit both templates for any secondary git calls that could fire
  before the guard and move or gate them accordingly.
- [ ] Verify the happy path (valid git context) is unchanged in both
  templates: no new prompts, no altered step numbering beyond the added
  Step 0.
- [ ] Run `python scripts/build.py --target-dir ..` to confirm the
  deployed agent files in `.claude/agents/` reflect the updated templates.

## Out of Scope

- Modifying agents other than `finalize-feature` and `changelog-agent`
  unless they are found to shell out to git before any guard during the
  audit step above.
- Introducing a shared git-check utility script (may be a follow-up if
  more than 2 agents need the pattern).
- Changing the concurrency throttler / retry-with-backoff for subagent
  spawning (that is the other unchecked action item from the same
  retrospective and should be a separate ticket).

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Fully reversible — the guard is additive. Removing it
  restores the original behavior. No schema or data changes involved.
