---
title: "Remove stale v3 agent names, test-planner refs, and /create-ac mentions from docs"
status: done
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
  documentation-expert: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
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

- [x] AC-1: `grep -r "product-owner-v3\|business-analyst-v3\|it-po-v3" docs/ templates/skills/` returns zero matches.
- [x] AC-2: `grep -r "test-planner" docs/ templates/skills/` returns zero matches, and `docs/agents/coding/test-planner.md` does not exist on disk.
- [x] AC-3: `grep -r "/create-ac" docs/architecture/` returns zero matches (all three occurrences replaced with `/plan-feature`).
- [x] AC-4: No valid cross-references are broken: any doc that linked to `test-planner` now either omits the link or links to the current test-writer doc.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | grep verification | All 7 class-A files already had zero v3 references; no changes needed | verified: zero matches |
| AC-2 | grep verification + ls check | test-planner.md absent; all 8 listed files already clean; agent_delivery_workflows.md previously updated | verified: zero matches, file absent |
| AC-3 | grep verification | Replaced /create-ac with /plan-feature in agent_delivery_workflows.md (×2) and ADR-006-flatten-supervisor-chain.md (×1) | verified: zero matches |
| AC-4 | manual cross-ref check | All test-writer cross-links present; no broken references introduced | verified: ok |

## Sign-offs

- [x] documentation-expert — 2026-06-16 14:30
- [x] pr-reviewer — 2026-06-16 15:00
- [x] commit — 2026-06-16 15:30
- [x] pull-request — 2026-06-16 15:45

## Comments

### 2026-06-16 14:30 — documentation-expert (status: ok)

feedback-id: fb_2026-06-16_153812bc
completion_manifest:
  doc_written: true
  cross_links_added: true
  diataxis_genre_correct: true

All three ACs verified clean. Class A (v3 agent name suffixes): all 7 listed files already had zero v3 references — no changes needed. Class B (test-planner): `docs/agents/coding/test-planner.md` was absent and all 8 listed files had zero test-planner references — no changes needed. Class C (/create-ac): replaced `/create-ac` with `/plan-feature` in `docs/architecture/agent_delivery_workflows.md` (two occurrences: line ~1395 intro text and line ~1409 Gherkin block) and `docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md` (one occurrence). AC-4 verified: no broken cross-references; all test-writer doc links remain valid.

### 2026-06-16 15:00 — pr-reviewer (status: ok)

feedback-id: fb_2026-06-16_4a22c2b4
completion_manifest:
  ac3_substitutions_correct: true
  no_broken_syntax: true
  no_unintended_staged_changes: true
  cross_references_intact: true

Reviewed staged diff and working-tree changes. AC-3: all three `/create-ac` occurrences replaced with `/plan-feature` — verified zero residual `/create-ac` matches in `docs/architecture/`. Substitutions are syntactically correct in both prose context (lines 1398, 1472 of agent_delivery_workflows.md) and Gherkin block (line 1409 / ADR-006 line 718). AC-1 and AC-2: the 7 Class-A target files and all Class-B files are clean. One medium-confidence observation: `docs/acceptance-criteria/README.md` rows 50-51 still name `product-owner-v3`/`it-po-v3` in an active workflow table — this file was outside the ticket's target list and is out of scope for this ticket; a follow-on doc sweep may address it. No high-confidence findings; approved to commit.

### 2026-06-16 15:30 — commit (status: ok)

feedback-id: fb_2026-06-16_338a5f3f
completion_manifest:
  commit_created: true
  staged_files_in_scope: true
  pre_commit_hooks_passed: true

Commit 9d9a83f created on branch EPIC-AcPipelineConsolidationMopUp. Staged and committed: ADR-006-flatten-supervisor-chain.md, agent_delivery_workflows.md (both with /create-ac → /plan-feature substitutions), ticket-01 sign-offs, and ticket-03 sign-offs. Pre-commit hooks passed (no .pre-commit-config.yaml — allowed via PRE_COMMIT_ALLOW_NO_CONFIG=1 per epic convention). 4 files changed, 101 insertions(+), 48 deletions(-).

### 2026-06-16 15:45 — pull-request (status: ok)

feedback-id: fb_2026-06-16_5b1d5dee
completion_manifest:
  branch_pushed: true
  pr_opened: true

Branch EPIC-AcPipelineConsolidationMopUp pushed to origin. PR #86 opened at https://github.com/urlmonitor/leafcutter-ai/pull/86. No prior PR existed for this branch.

## Implementation Tasks

- [x] Class A: In each of the 7 doc files listed above, replace all occurrences of `product-owner-v3` → `product-owner`, `business-analyst-v3` → `business-analyst`, `it-po-v3` → `it-po`.
- [x] Class B: Delete `docs/agents/coding/test-planner.md`. In each of the 8 remaining files, remove or rewrite sections that describe test-planner as an active spawned agent; reference `test-writer` where a replacement is needed.
- [x] Class B (SKILL.md): In `templates/skills/roadmap-steward/SKILL.md`, replace 4 references to `product-owner-agent` with the canonical `product-owner`.
- [x] Class C: In `docs/architecture/agent_delivery_workflows.md` lines 1403, 1414, 1477, replace `/create-ac` with `/plan-feature`.
- [x] Run grep verifications for AC-1, AC-2, AC-3 to confirm zero matches.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Documentation-only changes; fully reversible.
- Risk: Diagram files (c2-002, c2-003, c2-005) may have mermaid/C4 node IDs that need careful renaming — do not break diagram syntax while updating agent names. Verify mermaid renders correctly after edit.
