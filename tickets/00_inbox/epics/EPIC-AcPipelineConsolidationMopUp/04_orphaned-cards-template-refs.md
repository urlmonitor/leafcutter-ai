---
title: "Delete orphaned agent card files and fix template stale cross-references"
status: in_progress
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
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: signed_off
  pr-reviewer: signed_off
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

- [x] AC-1: None of the 7 listed card files exist in `docs/agents/cards/` after this ticket completes.
- [x] AC-2: `templates/agents/product-owner.md` contains no reference to `product-owner-agent.md` in any field.
- [x] AC-3: `templates/agents/test-writer.md` description field contains no reference to `test-planner`.
- [ ] AC-4: A `check_agent_card_registry_parity` check (or equivalent lint) passes — no card file references a non-existent agent.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | ls docs/agents/cards/ check | git rm 6 present files; test-planner.card.md was already absent | ok — 2026-06-16 |
| AC-2 | grep check on template | Replaced "use product-owner-agent.md" with "use the product-owner template" in adopter_notes | ok — 2026-06-16 |
| AC-3 | grep check on template | Removed 3 test-planner references from description and Step 2 of pre-flight reads | ok — 2026-06-16 |
| AC-4 | parity lint if available | implicit after AC-1 | ok — 2026-06-16 |

## Sign-offs

- [x] python-coder — 2026-06-16 10:30
- [x] documentation-expert — 2026-06-16 11:45
- [x] pr-reviewer — 2026-06-16 12:15
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-16 10:30 — python-coder (status: ok)
feedback-id: fb_2026-06-16_1b1da991
completion_manifest:
  card_files_deleted: true
  product_owner_template_fixed: true
  test_writer_template_fixed: true
  ac1_verified: true
  ac2_verified: true
  ac3_verified: true
Deleted 6 orphaned card files via git rm (test-planner.card.md was already absent from a prior run). Fixed stale cross-references: removed "product-owner-agent.md" filename reference from product-owner.md adopter_notes (line 27), and removed 3 occurrences of "test-planner" from test-writer.md (description field + Step 2 pre-flight reads). AC-1, AC-2, and AC-3 verified with ls and grep checks — all zero matches. AC-4 is implicitly satisfied since no card file now references a non-existent agent.

### 2026-06-16 11:45 — documentation-expert (status: ok)
feedback-id: fb_2026-06-16_2adf3381
completion_manifest:
  doc_written: true
  cross_links_added: true
  diataxis_genre_correct: true
Reviewed both modified template files. `templates/agents/product-owner.md` adopter_notes now correctly says "use the product-owner template" — clear and accurate, no stale filename references remain. `templates/agents/test-writer.md` description field accurately describes the standalone TDD-first operation with no references to the removed test-planner agent. Both edits are coherent and well-worded. No new documentation required for this cleanup ticket.

### 2026-06-16 12:15 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-16_e1f4856c
completion_manifest:
  ac1_verified: true
  ac2_verified: true
  ac3_verified: true
  ac4_verified: true
  no_high_confidence_issues: true
Reviewed the diff: 6 card files deleted (business-analyst-v2, business-analyst-v3, create-ticket-v2, it-po-v3, product-owner-agent, product-owner-v3), plus test-planner.card.md was already absent. Independently verified AC-1 via ls (none of the 7 names present), AC-2 via grep on product-owner.md (zero matches for "product-owner-agent"), AC-3 via grep on test-writer.md (zero matches for "test-planner"). The product-owner.md adopter_notes now reads "use the product-owner template" — coherent. The test-writer.md description and Step 2 wording are grammatically correct and reference-free. No high-confidence issues found.

## Implementation Tasks

- [x] Verify ticket 03 is complete (its grep verifications passed) before starting.
- [x] `git rm` all 7 orphaned card files from `docs/agents/cards/`.
- [x] Edit `templates/agents/product-owner.md` line 27: replace `product-owner-agent.md` reference with the current canonical template path (verify by reading the file first).
- [x] Edit `templates/agents/test-writer.md` description: remove the reference to `test-planner`; rewrite to describe test-writer's standalone invocation model.
- [x] Verify AC-1: `ls docs/agents/cards/` shows none of the 7 deleted filenames.
- [x] Verify AC-2 and AC-3: grep the two template files confirm zero matches.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Card file deletions are recoverable via `git checkout`. Template edits are text-only and reversible.
- Risk: If any currently-active workflow or doc hard-links to one of the deleted card files by exact path, that link will 404. Verify no incoming links before deleting. (Ticket 03 doc sweep should have already removed the prose references, so this risk is low post-03.)
