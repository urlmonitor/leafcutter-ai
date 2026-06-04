---
title: "Add contract-aware mode to test-writer and pr-reviewer"
status: todo
components:
  - build_pipeline
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
  - templates/agents/test-writer.md
  - templates/agents/pr-reviewer.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  architecture-diagram-author: not_needed
  user-surface-smoker: not_needed
---

# 07d: Test-Writer + PR-Reviewer Contract-Aware Mode

## Business Intent

test-writer and pr-reviewer have distinct roles in the AC flow compared to
coders: test-writer fills the Test column (not Implementation), and pr-reviewer
validates contracts without filling the table.

## Agent Contracts

### python-coder

- [ ] AC-1: test-writer.md includes contract-aware mode: when ticket has `## Agent Contracts`, write tests mapped to specific ACs and fill the **Test** column in the AC Coverage table (format: `test_file.py:test_function_name`)
- [ ] AC-2: test-writer maps each AC to at least one test — if an AC is untestable, it notes this in the Test column as `(not testable: <reason>)` rather than leaving it blank
- [ ] AC-3: pr-reviewer.md includes contract-aware mode: validates that `Delivers to` contracts in the ticket match the actual implementation in the diff — checks field names, types, status codes, endpoint paths
- [ ] AC-4: pr-reviewer flags contract mismatches as high-confidence findings (e.g., "contract specifies `avatar_url` but implementation returns `url`")
- [ ] AC-5: Both agents fall back to v1 behavior when ticket has no `## Agent Contracts` section

## Sign-offs

- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |

## Risk & Safety

- Touches money? No.
- Touches data? No — modifies agent templates only.
- Reversibility? Fully reversible — additive prompt sections, v1 behavior preserved.
