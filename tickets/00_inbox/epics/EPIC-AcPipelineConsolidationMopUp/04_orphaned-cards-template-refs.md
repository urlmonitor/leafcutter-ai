---
title: "Delete orphaned agent card files and fix template stale cross-references"
status: todo
components:
  - documentation_system
created: 2026-06-11
depends_on:
  - 03_docs-stale-agent-names.md
priority: medium
source_ac: ACD-1100
requires_diagram: false
requires_adr: false
roadmap_phase: phase_1
advances_current_outcome: false
files_touched:
  - docs/agents/cards/test-planner.card.md
  - docs/agents/cards/product-owner-agent.card.md
  - docs/agents/cards/business-analyst-v2.card.md
  - docs/agents/cards/business-analyst-v3.card.md
  - docs/agents/cards/create-ticket-v2.card.md
  - docs/agents/cards/it-po-v3.card.md
  - docs/agents/cards/product-owner-v3.card.md
  - templates/agents/product-owner.md
  - templates/agents/test-writer.md
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
---

# 04: Delete orphaned agent card files and fix template stale cross-references

## Actor / Goal

In order to keep the agent cards directory and active agent templates consistent with the v2.0.0 agent roster, we need to delete 7 orphaned card files for removed agents and fix 2 stale cross-references in active agent templates.

## Context

Depends on ticket 03 (doc sweep) completing first to avoid grep-verification overlap: ticket 03 verifies `grep` for `test-planner` returns zero in docs, while this ticket deletes the card files — sequencing avoids a false-positive during ticket 03 verification.

### Orphaned card files (7 to delete)

These agent cards reference agents that were removed in the consolidation. They should not exist:

- `docs/agents/cards/test-planner.card.md`
- `docs/agents/cards/product-owner-agent.card.md`
- `docs/agents/cards/business-analyst-v2.card.md`
- `docs/agents/cards/business-analyst-v3.card.md`
- `docs/agents/cards/create-ticket-v2.card.md`
- `docs/agents/cards/it-po-v3.card.md`
- `docs/agents/cards/product-owner-v3.card.md`

### Stale template cross-references (2 to fix)

- `templates/agents/product-owner.md` line 27: `adopter_notes` references `product-owner-agent.md` (the old filename, now removed). Update to reference the current template path.
- `templates/agents/test-writer.md` description field: references removed `test-planner` agent. Rewrite to describe the current standalone operation (test-writer operates directly, not via test-planner).

## Acceptance Criteria

- [ ] AC-1: None of the 7 listed card files exist in `docs/agents/cards/` after this ticket completes.
- [ ] AC-2: `templates/agents/product-owner.md` contains no reference to `product-owner-agent.md` in any field.
- [ ] AC-3: `templates/agents/test-writer.md` description field contains no reference to `test-planner`.
- [ ] AC-4: A `check_agent_card_registry_parity` check (or equivalent lint) passes — no card file references a non-existent agent.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | ls docs/agents/cards/ check | git rm 7 files | |
| AC-2 | grep check on template | edit product-owner.md line 27 | |
| AC-3 | grep check on template | edit test-writer.md description | |
| AC-4 | parity lint if available | implicit after AC-1 | |

## Sign-offs

- [ ] python-coder
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] Verify ticket 03 is complete (its grep verifications passed) before starting.
- [ ] `git rm` all 7 orphaned card files from `docs/agents/cards/`.
- [ ] Edit `templates/agents/product-owner.md` line 27: replace `product-owner-agent.md` reference with the current canonical template path (verify by reading the file first).
- [ ] Edit `templates/agents/test-writer.md` description: remove the reference to `test-planner`; rewrite to describe test-writer's standalone invocation model.
- [ ] Verify AC-1: `ls docs/agents/cards/` shows none of the 7 deleted filenames.
- [ ] Verify AC-2 and AC-3: grep the two template files confirm zero matches.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Card file deletions are recoverable via `git checkout`. Template edits are text-only and reversible.
- Risk: If any currently-active workflow or doc hard-links to one of the deleted card files by exact path, that link will 404. Verify no incoming links before deleting. (Ticket 03 doc sweep should have already removed the prose references, so this risk is low post-03.)
