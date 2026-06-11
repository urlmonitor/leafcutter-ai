---
title: "Remove stale v3 agent names, test-planner refs, and /create-ac mentions from docs"
status: todo
components:
  - documentation_system
created: 2026-06-11
depends_on: []
priority: medium
source_ac: ACD-1100
requires_diagram: false
requires_adr: false
roadmap_phase: phase_1
advances_current_outcome: false
files_touched:
  - docs/how-to/ac-driven-development.md
  - docs/how-to/approval-gate.md
  - docs/how-to/goal-to-epic.md
  - docs/how-to/build-ac-unified.md
  - docs/architecture/diagrams/c2-002-ac-authoring-pipeline.md
  - docs/architecture/diagrams/c2-003-ac-readiness-states.md
  - docs/architecture/diagrams/c2-005-goal-to-epic-dispatch.md
  - docs/agents/coding/test-planner.md
  - docs/agents/ticket-creation/business-analyst.md
  - docs/agentic-runtime-flow.md
  - docs/testing/README.md
  - docs/explanation/tdd-workflow.md
  - docs/how-to/working-with-leafcutter.md
  - docs/how-to/writing-a-tdd-ticket.md
  - docs/architecture/agent_delivery_workflows.md
  - templates/skills/roadmap-steward/SKILL.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 03: Remove stale v3 agent names, test-planner refs, and /create-ac mentions from docs

## Actor / Goal

In order to keep documentation accurate after the EPIC-AcPipelineConsolidation merge, we need to sweep ~85 stale references across doc files and skill templates so that new contributors do not follow outdated instructions pointing at removed agents or deprecated command names.

## Context

The v2.0.0 consolidation removed or renamed several agents. Three classes of stale references remain:

### Class A: v3 agent names (~35 occurrences)

The pipeline no longer uses the `-v3` suffixed agent names. Canonical names are now `product-owner`, `business-analyst`, `it-po` (no suffix). These must be updated in:

- `docs/how-to/ac-driven-development.md` (~16 references)
- `docs/how-to/approval-gate.md` (~7 references)
- `docs/how-to/goal-to-epic.md` (~3 references)
- `docs/how-to/build-ac-unified.md` (~4 references)
- `docs/architecture/diagrams/c2-002-ac-authoring-pipeline.md`
- `docs/architecture/diagrams/c2-003-ac-readiness-states.md`
- `docs/architecture/diagrams/c2-005-goal-to-epic-dispatch.md`

### Class B: test-planner as active agent (~50 occurrences)

`test-planner` was removed in the consolidation. Its doc file is now orphaned. References to it as an active spawned agent must be removed or replaced with the current TDD workflow description. Files affected:

- `docs/agents/coding/test-planner.md` — delete the entire file (orphaned doc for a removed agent)
- `docs/agents/ticket-creation/business-analyst.md` — remove the section describing test-planner spawn
- `docs/agentic-runtime-flow.md` — remove test-planner diagram nodes
- `docs/testing/README.md` — update TDD section
- `docs/explanation/tdd-workflow.md` — remove test-planner from the explained workflow
- `docs/how-to/working-with-leafcutter.md` — remove test-planner references
- `docs/how-to/writing-a-tdd-ticket.md` — update to reflect current TDD flow without test-planner
- `docs/architecture/agent_delivery_workflows.md` lines 141, 151-155, 164, 235 — remove test-planner nodes/edges
- `templates/skills/roadmap-steward/SKILL.md` — 4 references to `product-owner-agent` (the old name)

### Class C: /create-ac command name (3 occurrences)

`docs/architecture/agent_delivery_workflows.md` lines 1403, 1414, 1477 still reference `/create-ac`. The canonical command is now `/plan-feature`.

## Acceptance Criteria

- [ ] AC-1: `grep -r "product-owner-v3\|business-analyst-v3\|it-po-v3" docs/ templates/skills/` returns zero matches.
- [ ] AC-2: `grep -r "test-planner" docs/ templates/skills/` returns zero matches, and `docs/agents/coding/test-planner.md` does not exist on disk.
- [ ] AC-3: `grep -r "/create-ac" docs/architecture/` returns zero matches (all three occurrences replaced with `/plan-feature`).
- [ ] AC-4: No valid cross-references are broken: any doc that linked to `test-planner` now either omits the link or links to the current test-writer doc.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | grep verification | bulk find-replace in 7 files | |
| AC-2 | grep verification + ls check | remove file, update 8 files | |
| AC-3 | grep verification | update 3 lines in agent_delivery_workflows.md | |
| AC-4 | manual cross-ref check | verify linked targets exist | |

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] Class A: In each of the 7 doc files listed above, replace all occurrences of `product-owner-v3` → `product-owner`, `business-analyst-v3` → `business-analyst`, `it-po-v3` → `it-po`.
- [ ] Class B: Delete `docs/agents/coding/test-planner.md`. In each of the 8 remaining files, remove or rewrite sections that describe test-planner as an active spawned agent; reference `test-writer` where a replacement is needed.
- [ ] Class B (SKILL.md): In `templates/skills/roadmap-steward/SKILL.md`, replace 4 references to `product-owner-agent` with the canonical `product-owner`.
- [ ] Class C: In `docs/architecture/agent_delivery_workflows.md` lines 1403, 1414, 1477, replace `/create-ac` with `/plan-feature`.
- [ ] Run grep verifications for AC-1, AC-2, AC-3 to confirm zero matches.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Documentation-only changes; fully reversible.
- Risk: Diagram files (c2-002, c2-003, c2-005) may have mermaid/C4 node IDs that need careful renaming — do not break diagram syntax while updating agent names. Verify mermaid renders correctly after edit.
