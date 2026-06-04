---
title: "Create ac-validator agent — final AC coverage gate before commit"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on:
  - 02_ac_format_and_frontmatter.md
priority: high
phase: "Phase 2"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
user_facing_surface: null
files_touched:
  - templates/agents/ac-validator.md
  - leafcutter/config/agent_registry.json
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

# 05: Create ac-validator Agent

## Business Intent

A final gate agent that validates all acceptance criteria are actually covered
by the implementation before allowing commit. Prevents "all agents signed off
but AC-3 was never tested" scenarios.

## Context

The ac-validator runs at priority 11 (after pr-reviewer, before commit) and is
the single point of truth for "are all ACs met?" It does not implement anything —
it reads the ticket ACs, the working diff, and test output, then produces a
coverage verdict.

### Verdict Rules

- **All covered** → sign off `ok`, unblock commit
- **Any missing** → sign off `blocker`, report which ACs lack evidence
- **Partial** → sign off `question`, surface to ticket-supervisor for judgment

### Evidence Requirement

For each AC, the validator must cite concrete evidence:
- Test name that exercises it (from test output or test file)
- File + function/line that implements it (from the diff)

This evidence requirement suppresses false positives — the model cannot
hallucinate coverage if it must cite a real artifact.

## Agent Contracts

### python-coder

- [ ] AC-1: Agent template file exists at `templates/agents/ac-validator.md` with valid frontmatter (name: ac-validator, model: sonnet, tools: Bash/Read)
- [ ] AC-2: Agent prompt reads `## Acceptance Criteria` or `## Agent Contracts` section from the ticket, parses each `- [ ] AC-N:` line
- [ ] AC-3: For each AC, agent searches the diff (`git diff --cached` or `files_touched`) for implementation evidence (file path + function name or line range)
- [ ] AC-4: For each AC, agent searches test output or test files for test coverage evidence (test name that exercises this AC)
- [ ] AC-5: Agent updates the ticket file: fills AC Coverage table (Validated column), flips covered AC checkboxes to `[x]` with attribution, updates `ac_coverage: N/M` in frontmatter
- [ ] AC-6: Agent signs off as `ok` when all ACs covered, `blocker` when any AC has no evidence, `question` when any AC is partial

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
| AC-6 | | | |

## Risk & Safety

- Touches money? No.
- Touches data? No — modifies ticket files (AC checkboxes, frontmatter) only.
- Reversibility? Fully reversible — new agent template + registry entry.
- Risk: False negatives (validator can't find evidence for a legitimately covered AC).
  Mitigation: `partial` status escalates to ticket-supervisor for human judgment
  rather than hard-blocking.
