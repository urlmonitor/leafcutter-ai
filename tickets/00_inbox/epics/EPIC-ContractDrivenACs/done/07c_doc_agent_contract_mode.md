---
title: "Add contract-aware mode to doc-writing agents (adr-author, how-to-author, etc.)"
status: done
components:
  - build_pipeline
  - documentation_system
created: 2026-06-03
depends_on:
  - 07a_signoff_ac_recipe.md
priority: medium
phase: "Phase 3"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
user_facing_surface: null
files_touched:
  - templates/agents/documentation-expert.md
  - templates/agents/adr-author.md
  - templates/agents/how-to-author.md
  - templates/agents/reference-author.md
  - templates/agents/explanation-author.md
  - templates/agents/architecture-diagram-author.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
  architecture-diagram-author: not_needed
  user-surface-smoker: not_needed
---

# 07c: Doc Agent Contract-Aware Mode

## Business Intent

Documentation agents also get acceptance criteria in v2 tickets (e.g.,
"AC-5: ADR includes Consequences section covering both benefits and costs").
They need the same contract-aware mode as coders: read their AC block, produce
docs that satisfy the ACs, and invoke the sign-off recipe.

## Agent Contracts

### python-coder

- [x] AC-1: documentation-expert.md includes contract-aware mode: when ticket contains `## Agent Contracts → ### documentation-expert`, use that block as the doc spec <!-- signed: python-coder -->
- [x] AC-2: adr-author.md includes contract-aware mode: reads its AC block for specific section requirements (e.g., "AC must cover alternatives X, Y, Z") <!-- signed: python-coder -->
- [x] AC-3: how-to-author.md, reference-author.md, explanation-author.md include contract-aware mode (same pattern — read AC block, produce doc matching spec) <!-- signed: python-coder -->
- [x] AC-4: architecture-diagram-author.md includes contract-aware mode: reads its AC block for diagram type, scope, and component coverage requirements <!-- signed: python-coder -->
- [x] AC-5: All doc agents invoke the AC sign-off recipe from signoff SKILL.md after completing their work — no change for v1 tickets <!-- signed: python-coder -->

## Sign-offs

- [x] python-coder — 2026-06-04 10:00
- [x] pr-reviewer — 2026-06-04 10:05
- [x] commit — 2026-06-04 10:10
- [x] pull-request — 2026-06-04 10:15

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | Added Contract-Aware Mode section to documentation-expert.md | ok — 2026-06-04 |
| AC-2 | | Added Contract-Aware Mode section to adr-author.md | ok — 2026-06-04 |
| AC-3 | | Added Contract-Aware Mode sections to how-to-author.md, reference-author.md, explanation-author.md | ok — 2026-06-04 |
| AC-4 | | Added Contract-Aware Mode section to architecture-diagram-author.md | ok — 2026-06-04 |
| AC-5 | | All doc agents reference signoff SKILL.md §2c in their Contract-Aware Mode section | ok — 2026-06-04 |

## Risk & Safety

- Touches money? No.
- Touches data? No — modifies agent templates only.
- Reversibility? Fully reversible — additive prompt sections, v1 behavior preserved.

## Comments

### 2026-06-04 10:00 — python-coder (status: ok)
feedback-id: fb_2026-06-04_02555c00
completion_manifest:
  code_implemented: true
  tests_passing: true
  doc_enforcer_clean: true
  complexity_check_clean: true
Added Contract-Aware Mode sections to all 6 doc agent templates: documentation-expert.md, adr-author.md, how-to-author.md, reference-author.md, explanation-author.md, and architecture-diagram-author.md. Each section follows the same pattern: v2 detection rule, AC block reading, spec application, and §2c sign-off recipe invocation. All ACs satisfied; v1 behaviour preserved via detection check.

### 2026-06-04 10:05 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-04_19192ee2
completion_manifest:
  ac1_satisfied: true
  ac2_satisfied: true
  ac3_satisfied: true
  ac4_satisfied: true
  ac5_satisfied: true
Reviewed all 6 doc agent template changes. All 5 ACs satisfied: each template has a Contract-Aware Mode section with the correct detection rule, v2 behaviour steps (read AC block, apply requirements, verify satisfaction, invoke §2c), and v1 behaviour fallback. Sections are additive and placed at appropriate locations in each agent's flow. No high-confidence findings. Suppressed: 0 low-confidence nits, 0 medium findings dropped. Escalation: none (medium count was 0, threshold > 3).

### 2026-06-04 10:10 — commit (status: ok)
feedback-id: fb_2026-06-04_ff0cebe4
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Staged 6 doc agent templates and ticket file; committed as feat(07c) on branch EPIC-ContractDrivenACs. SHA: 88219c1. 7 files changed, 237 insertions, 14 deletions. Pre-commit hooks: PRE_COMMIT_ALLOW_NO_CONFIG=1 applied (no .pre-commit-config.yaml in worktree).

### 2026-06-04 10:15 — pull-request (status: ok)
feedback-id: fb_2026-06-04_b47aabf1
completion_manifest:
  branch_pushed: true
  pr_exists: true
Pushed commit 88219c1 to existing epic PR #43 (EPIC-ContractDrivenACs). Branch: EPIC-ContractDrivenACs. PR: https://github.com/urlmonitor/leafcutter-ai/pull/43
