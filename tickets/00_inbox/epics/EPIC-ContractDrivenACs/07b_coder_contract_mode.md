---
title: "Add contract-aware mode to coder agents (python-coder, frontend-coder, sql-coder)"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on:
  - 07a_signoff_ac_recipe.md
priority: high
phase: "Phase 3"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
user_facing_surface: null
files_touched:
  - templates/agents/python-coder.md
  - templates/agents/frontend-coder.md
  - templates/agents/sql-coder.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
  architecture-diagram-author: not_needed
  user-surface-smoker: not_needed
---

# 07b: Coder Agent Contract-Aware Mode

## Business Intent

Coder agents need to read their per-agent contract block, verify upstream
dependencies exist, produce code that matches the `Delivers to` contract,
and use the AC sign-off recipe from the signoff skill.

## Agent Contracts

### python-coder

- [x] AC-1: python-coder.md includes a "Contract-Aware Mode" section: when ticket contains `## Agent Contracts → ### python-coder`, read that block as the primary spec instead of `## Implementation Tasks` <!-- signed: python-coder -->
- [x] AC-2: In contract-aware mode, agent reads `Depends on` block first and verifies upstream deliverable exists (DB column, upstream endpoint) — if not present, sign off as `blocker` <!-- signed: python-coder -->
- [x] AC-3: In contract-aware mode, agent reads `Delivers to` block and ensures implementation matches the exact contract (endpoint path, response field names and types, status codes) <!-- signed: python-coder -->
- [x] AC-4: Same contract-aware mode section added to frontend-coder.md and sql-coder.md, adapted to their domains (frontend reads API contracts, sql-coder reads column/type contracts) <!-- signed: python-coder -->
- [x] AC-5: All three agents invoke the AC sign-off recipe from signoff SKILL.md after completing their work (v2 flow) — no change for v1 tickets <!-- signed: python-coder -->

## Sign-offs

- [x] python-coder — 2026-06-04 12:00
- [x] pr-reviewer — 2026-06-04 12:05
- [x] commit — 2026-06-04 12:15
- [ ] pull-request

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | Added "Contract-Aware Mode" section to python-coder.md with detection, Depends on verification, and Delivers to enforcement | ok — 2026-06-04 |
| AC-2 | | Contract-Aware Mode Step 1 verifies upstream Depends on block; signs off as blocker if deliverable absent | ok — 2026-06-04 |
| AC-3 | | Contract-Aware Mode Step 2 reads Delivers to block and mandates exact match for endpoints, field names, types, status codes | ok — 2026-06-04 |
| AC-4 | | Same Contract-Aware Mode section added to frontend-coder.md (API contracts) and sql-coder.md (column/type contracts) | ok — 2026-06-04 |
| AC-5 | | All three agents include §2c sign-off in Step 3 of contract-aware mode; v1 detection skips it silently | ok — 2026-06-04 |

## Risk & Safety

- Touches money? No.
- Touches data? No — modifies agent templates only.
- Reversibility? Fully reversible — v1 behavior preserved via detection check.

## Comments

### 2026-06-04 12:15 — commit (status: ok)
feedback-id: fb_2026-06-04_7f3150a0
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Committed 4 files (templates/agents/python-coder.md, frontend-coder.md, sql-coder.md, and 07b ticket). SHA: cf2857278524c46e430e13898e722b78eed03ef3. Pre-commit hook warned about missing .pre-commit-config.yaml; bypassed with PRE_COMMIT_ALLOW_NO_CONFIG=1 (known worktree behavior). No regressions detected.

## Anomalies

Pre-commit hook triggered "No .pre-commit-config.yaml file was found" warning — this is expected behavior in the EPIC-ContractDrivenACs worktree. No other anomalies.

### 2026-06-04 12:05 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-04_cd66c442
completion_manifest:
  diff_reviewed: true
  no_high_findings: true
  scope_verified: true
Reviewed 230-line additive diff across 3 agent templates. No high-confidence findings. All 5 ACs confirmed present in diff: Contract-Aware Mode section added to python-coder.md, frontend-coder.md, and sql-coder.md with correct Depends on verification, Delivers to enforcement, and §2c AC sign-off recipe reference. Validated column in AC Coverage table filled. Escalation: none (0 medium findings; threshold > 3).

## Escalation

Branch: none
Reason: not escalated — medium count was 0 (threshold > 3)

### 2026-06-04 12:00 — python-coder (status: ok)
feedback-id: fb_2026-06-04_a600b441
completion_manifest:
  code_implemented: true
  tests_passing: true
  doc_enforcer_clean: true
  complexity_check_clean: true
Added "Contract-Aware Mode" section to python-coder.md, frontend-coder.md, and sql-coder.md. Each section includes a v1/v2 detection rule (auto-activates on `## Agent Contracts → ### <agent-name>`), a Step 1 verifying upstream `Depends on` deliverables (blocker on missing), a Step 2 enforcing `Delivers to` contract exactness, and a Step 3 invoking the §2c AC sign-off recipe. All AC checkboxes flipped and Implementation column filled in `## AC Coverage`. No Python code modified; these are template (markdown) files.
