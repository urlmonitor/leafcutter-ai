---
title: "Eliminate DECISION HISTORY HH:MM + TICKETLESS tail-tag autofix loop"
status: todo
components:
  - build_system
  - agents
created: 2026-05-22
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
roadmap_phase: phase_1
advances_current_outcome: true
files_touched:
  - .claude/skills/signoff/SKILL.md
  - .claude/skills/build-single-ticket/SKILL.md
  - .claude/skills/building-epics/SKILL.md
  - scripts/commit_guardian/commit_guardian.json
agents:
  architect-review: not_needed
  python-coder: needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  test-writer: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  sql-coder: not_needed
  user-surface-smoker: not_needed
---

# 02: Eliminate DECISION HISTORY HH:MM + TICKETLESS tail-tag autofix loop

## Actor / Goal

In order to stop the pre-commit autofix from firing on every agent commit, we need to ensure that agents emit the DECISION HISTORY timestamp format and the TICKETLESS tail-tag correctly the first time, eliminating the mechanical autofix cycle entirely.

## Context

Two pre-commit autofixes fire on nearly every commit that agents produce — 6+ feedback hits confirm the pattern. The autofixes succeed, so there is no hard failure, but each autofix adds a round-trip (write → `git commit` fails → autofix → `git add` → `git commit`). This is pure friction.

**DECISION HISTORY HH:MM**: The `## Decision History` section in Master_Plan / epic docs is supposed to carry timestamps in `YYYY-MM-DD HH:MM` format. Agents write the date only (`YYYY-MM-DD`) or omit the time entirely. The autofix corrects to `HH:MM` but the format spec is not prominently documented in the skills agents read at commit time.

**TICKETLESS tail-tag**: Commits produced by the `commit` phase agent are missing the required `[TICKETLESS]` or `[TICKET-<id>]` tail-tag in their commit messages. The autofix appends `[TICKETLESS]` but the `commit` agent's instruction about commit message format does not enforce this.

Root-cause approach: fix what the agent writes — not what the autofix patches.

## Acceptance Criteria

```gherkin
Given a phase agent (commit) produces a commit for a ticket
When the commit message is written
Then it includes the required tail-tag ([TICKET-<id>] or [TICKETLESS]) without autofix intervention
And git commit exits 0 on the first attempt (no autofix round-trip)

Given an agent writes a DECISION HISTORY entry to a Master_Plan or epic doc
When the entry is staged
Then the timestamp matches the YYYY-MM-DD HH:MM format expected by the pre-commit hook
And no autofix fires for the timestamp format

Given the precommit-autofix loop runs (integration check)
When an agent-produced commit is staged
Then zero autofix events are emitted for DECISION_HISTORY or TICKETLESS categories
```

## Sign-offs

- [ ] python-coder
- [ ] documentation-expert
- [ ] test-writer
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### python-coder
- [ ] Read `scripts/commit_guardian/commit_guardian.json` and locate the rules for DECISION HISTORY timestamp and TICKETLESS tail-tag autofix. Document the exact regex/pattern each autofix uses.
- [ ] Trace which hook or autofix rule fires: identify the `hook_id` in `.pre-commit-config.yaml` or `commit_guardian.json` and confirm what the agent writes vs. what the rule expects.

### documentation-expert
- [ ] Update `.claude/agents/commit.md` commit-message format instructions to explicitly require the tail-tag (`[TICKET-<basename>]` or `[TICKETLESS]`) as part of the canonical commit message template. Make the tail-tag impossible to miss — place it in the fill-in-the-blank template, not as a footnote.
- [ ] Update `.claude/skills/signoff/SKILL.md` (or whichever skill describes `## Decision History` authoring) to specify `YYYY-MM-DD HH:MM` (24-hour clock, UTC, zero-padded) prominently, with a worked example. Remove any ambiguity about the format.
- [ ] If the DECISION HISTORY format rule is in a different skill (e.g. `building-epics`), update it there instead.

### test-writer
- [ ] Write a unit test in `unit_tests/commit_guardian/` that confirms a commit message without the tail-tag is flagged by the relevant hook rule (regression guard so the fix cannot silently revert).

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Skill/agent prompt changes are reverted by editing the file. Unit test additions are low-risk.
- Risk of over-suppression: the fix must NOT disable the autofix rules — it must make agents emit the correct format so the rules have nothing to fix. Verify by running a dry commit through `pre-commit run --all-files` after the change.
