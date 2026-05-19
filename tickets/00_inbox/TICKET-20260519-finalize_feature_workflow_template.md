---
title: "Add finalize-feature workflow template so build.py generates the slash command"
status: todo
components:
  - build_system
created: 2026-05-19
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/templates/workflows/finalize-feature.md
agents:
  architect-review: not_needed
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
user_facing_surface: slash_command
actuation_contract: "Invokes the finalize-feature agent, which orchestrates the 6-step post-merge feature finalization sequence (open PR if missing, merge, sync main, run tests, close tickets, remove worktree) with confirmation gates on all destructive steps."
roadmap_phase: phase_1
advances_current_outcome: true
---

# Add finalize-feature workflow template so build.py generates the slash command

## Actor / Goal

As a **developer using leafcutter**, I need a `/finalize-feature` slash command
so that I can invoke the post-merge finalization sequence directly from the
Claude Code CLI without manually dispatching the `finalize-feature` agent.

## Context

The `finalize-feature` agent template already exists at
`leafcutter-ai/templates/agents/finalize-feature.md` and `build.py` deploys it
to `.claude/agents/finalize-feature.md`. However, there is no corresponding
workflow template at `leafcutter-ai/templates/workflows/finalize-feature.md`.

`build_workflows` in `leafcutter-ai/scripts/build_phases.py` globs
`templates/workflows/*.md` and copies each file to `.claude/commands/`. Because
`finalize-feature.md` is absent from that directory, `build.py` never emits
`.claude/commands/finalize-feature.md`, which means `/finalize-feature` does
not appear as a slash command.

Every other user-facing agent in the package has a matching workflow template
(e.g. `commit.md`, `pull-request.md`, `build-feature.md`). This ticket closes
the gap for `finalize-feature`.

## Acceptance Criteria

```gherkin
Given leafcutter-ai/templates/workflows/finalize-feature.md exists
When python leafcutter-ai/scripts/build.py --target-dir <project> is run
Then .claude/commands/finalize-feature.md is written to the target project

Given .claude/commands/finalize-feature.md is present in a target project
When a user types /finalize-feature in Claude Code
Then the finalize-feature agent is invoked with $ARGUMENTS forwarded verbatim
```

## Smoke Fixture

```yaml
surface: finalize-feature
fixture_input: |
  (no arguments — agent performs its own pre-flight branch detection)
assertion: "finalize-feature|post-merge|Step [1-6]|Pre-Flight"
placeholder_signature: "TODO|PLACEHOLDER|not implemented"
```

## Sign-offs

- [ ] user-surface-smoker
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] Create `leafcutter-ai/templates/workflows/finalize-feature.md` following
  the same minimal pattern as `pull-request.md` and `commit.md`:
  a YAML frontmatter block with `description:` and a one-liner body that
  forwards `$ARGUMENTS` to the `finalize-feature` agent.
- [ ] Run `python leafcutter-ai/scripts/build.py --target-dir .` and confirm
  `.claude/commands/finalize-feature.md` is generated.
- [ ] Verify the generated file's content matches the template (substitutions
  applied, no raw `{{` placeholders remaining).

## Out of Scope

- Modifying the `finalize-feature` agent itself (`templates/agents/finalize-feature.md`).
- Adding unit tests for `build_workflows` (no logic change — the function
  already handles all `*.md` files; the template is the only addition).

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Fully reversible — deleting the template file and re-running
  `build.py` removes the generated slash command.
