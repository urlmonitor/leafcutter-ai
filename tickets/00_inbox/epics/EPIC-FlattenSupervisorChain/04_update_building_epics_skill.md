---
title: "Update building-epics SKILL.md for flat dispatch model"
status: todo
components:
  - build_pipeline
created: 2026-05-29
depends_on:
  - 01_update_ticket_supervisor_template.md
priority: medium
requires_diagram: false
requires_adr: false
files_touched:
  - templates/skills/building-epics/SKILL.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
roadmap_phase: phase_1
advances_current_outcome: true
---

# 04: Update building-epics SKILL.md for flat dispatch model

## Goal

In order to keep the `building-epics` runbook accurate after the supervisor
chain is flattened, we need to update `templates/skills/building-epics/SKILL.md`
so that §1 (the epic-level algorithm) and any cross-references to
`epic-supervisor` reflect the new dispatch model where `ticket-supervisor`
runs at depth 0.

## Context

`building-epics/SKILL.md` is the operational runbook loaded by both
`epic-supervisor` and `ticket-supervisor` at pre-flight. After the flatten:

- `ticket-supervisor` still loads this skill (unchanged).
- The §1 epic-level algorithm previously described a loop owned by
  `epic-supervisor`. That loop is now either inlined in `/build-feature`
  or removed from `epic-supervisor`'s purview.
- The skill must be accurate so agents reading it do not follow stale
  instructions.

This ticket updates the skill's §1 header and any prose that describes
`epic-supervisor` as the orchestrator of `ticket-supervisor`. It does NOT
change §2 (ticket-level algorithm) or §3 (failure adjudication) — those
are owned by `ticket-supervisor` and are unaffected.

## Acceptance Criteria

```gherkin
Given templates/skills/building-epics/SKILL.md is updated
When §1 is read
Then the orchestrator described is "/build-feature" (or the inline batching logic)
And "epic-supervisor" is referenced only as the deprecated predecessor

Given the skill is updated and build-self.sh is run
When .claude/skills/building-epics/SKILL.md is inspected
Then it matches the template (no stale references to epic-supervisor as primary dispatcher)

Given §2 through §6 of the skill are inspected
When the ticket-level algorithm section is read
Then ticket-supervisor's behaviour description is unchanged
And depth-0 dispatch is explicitly noted
```

## Sign-offs

- [ ] python-coder
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] Read `templates/skills/building-epics/SKILL.md` in full
- [ ] Identify every section that describes `epic-supervisor` as the primary dispatcher of `ticket-supervisor`
- [ ] Update §1 header to state that the epic-level batching is now inlined in `/build-feature` (not in `epic-supervisor`)
- [ ] Add a note at the top of §1: "Note: `epic-supervisor` is deprecated (ADR-006). `/build-feature` now owns the epic-level ticket batching described in this section."
- [ ] Search for "epic-supervisor spawns ticket-supervisor" phrasing and replace with "/build-feature dispatches ticket-supervisor directly (depth 0)"
- [ ] Ensure §2 (ticket-level five-step loop) and §3 (failure adjudication) are UNCHANGED
- [ ] Run `./build-self.sh` and verify `.claude/skills/building-epics/SKILL.md` reflects the updates

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Template edit is fully git-reversible.
- The `building-epics` skill is read on every supervisor invocation. A confusing
  update could cause agents to misread the orchestration model. Review wording
  carefully before merge.
