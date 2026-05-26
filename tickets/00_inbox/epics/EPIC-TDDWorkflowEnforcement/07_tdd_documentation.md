---
title: "Author TDD documentation: explanation doc, how-to guide, and ADR-004"
status: todo
components:
  - build_pipeline
created: 2026-05-26
depends_on:
  - 02_test_writer_rewrite.md
  - 03_coder_success_gate.md
  - 04_contract_shrinking_hook.md
  - 05_building_epics_skill_update.md
priority: medium
requires_diagram: false
requires_adr: true
requires_documentation:
  - explanation
  - how_to
  - adr
agents:
  adr-author: needed
  architect-review: needed
  explanation-author: needed
  how-to-author: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 07: Author TDD documentation: explanation doc, how-to guide, and ADR-004

## Goal

In order to make the TDD workflow discoverable, understandable, and permanently recorded as an architectural decision, we need three documentation artifacts: an explanation doc (why TDD works this way in leafcutter), a how-to guide (how to write a TDD ticket), and ADR-004 capturing the decision to flip test-writer before coders.

## Context

This ticket depends on tickets 02–05 being complete (the enforcement machinery must exist before we document it as authoritative). The three artifacts:

### 1. Explanation doc: `docs/explanation/tdd-workflow.md`

Audience: developers new to the project or new to this TDD variant.

Content outline:
- What "test-first in an agentic pipeline" means (different from classical TDD with a human at the keyboard)
- The three phases: test-planner (BA flow) → test-writer (build flow, red) → coder (build flow, green)
- The red_baseline concept and why it matters
- The three-layer contract-shrinking guard (hook + supervisor warn + honor-system)
- The docs-only / config-only skip rule and why it exists
- Scope: Python only in Phase 1; SQL TDD is a follow-on

### 2. How-to guide: `docs/how-to/writing-a-tdd-ticket.md`

Audience: anyone writing a new ticket that will involve Python code.

Content outline:
- Step 1: ensure your `## Test Requirements` block is populated (test-planner does this during BA flow)
- Step 2: understand what test-writer will do (writes failing tests before the coder runs)
- Step 3: what happens when the coder runs (success gate: all red_baseline tests must be green)
- Step 4: what the contract-shrinking hook catches (and what to do if it fires)
- FAQ: "what if test-planner left my tests array empty?" → test-writer is skipped; start by writing an ADR or doc ticket instead
- FAQ: "what if a red_baseline test is wrong?" → fix the test in a separate commit with no production code changes

### 3. ADR-004: `docs/architecture/adrs/ADR-004-tdd-workflow-enforcement.md`

Decision: flip `test-writer` to run before `python-coder`/`sql-coder` (priority 5 instead of 8), making tests the contract that drives implementation rather than a post-hoc verification.

Context: the current test-AFTER flow allows coders to write whatever code they want, with test-writer retroactively documenting it. This defeats the purpose of tests as a design tool. The TDD flip makes failing tests the explicit success target for coders.

Alternatives considered:
- Keep test-AFTER, add stronger PR review: rejected — review is subjective and still allows test-after patterns
- Add a separate "design" phase agent: rejected — over-engineering; test-writer in TDD mode already serves this purpose
- Honor-system only (no hook): rejected — without enforcement, the pattern erodes under time pressure

Consequences:
- Positive: coders have a clear, machine-verifiable done criterion
- Positive: test quality improves (tests are written without knowledge of the implementation)
- Negative: test-writer must run even if coder is faster (sequential constraint)
- Mitigation: docs-only skip rule prevents stalls on non-code tickets

## Acceptance Criteria

```gherkin
Given docs/explanation/tdd-workflow.md exists
When the file is read
Then it explains the three-phase TDD flow (test-planner → test-writer → coder)
And it describes the red_baseline concept
And it describes all three layers of the contract-shrinking guard
And it notes Python-only scope for Phase 1

Given docs/how-to/writing-a-tdd-ticket.md exists
When the file is read
Then it provides step-by-step guidance for writing a ticket that will go through TDD flow
And it references the contract-shrinking hook (ticket 04)
And it answers the FAQ about empty test_requirements

Given docs/architecture/adrs/ADR-004-tdd-workflow-enforcement.md exists
When the file is read
Then it records the decision, context, alternatives, and consequences in standard ADR format
And it references the specific priority change (test-writer 8 → 5)
And it references this epic (EPIC-TDDWorkflowEnforcement)
```

## Architecture Plan

### ADRs

- `ADR-004: Test-First Workflow Enforcement in the Agentic Build Pipeline` — new ADR to be authored capturing the decision to flip test-writer priority and the three-layer contract-shrinking guard.

## Sign-offs

- [ ] adr-author
- [ ] architect-review
- [ ] explanation-author
- [ ] how-to-author
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### adr-author
- [ ] Author `docs/architecture/adrs/ADR-004-tdd-workflow-enforcement.md` following ADR standard format (Status, Context, Decision, Alternatives Considered, Consequences)
- [ ] Reference the priority change: test-writer `"priority": 8 → 5`
- [ ] Reference all three enforcement layers (hook, supervisor, docs)
- [ ] Reference this epic

### architect-review
- [ ] Review ADR-004 draft for architectural completeness — confirm alternatives are fairly represented and consequences are accurate
- [ ] Confirm the explanation doc correctly describes the `red_baseline` schema
- [ ] Confirm the how-to FAQ section covers the most common confusion points

### explanation-author
- [ ] Author `docs/explanation/tdd-workflow.md` following the outline in Context
- [ ] Include a reference to ADR-004 for the decision rationale
- [ ] Include a cross-reference to `docs/how-to/writing-a-tdd-ticket.md`

### how-to-author
- [ ] Author `docs/how-to/writing-a-tdd-ticket.md` following the outline in Context
- [ ] Cross-reference `check_contract_shrinking.py` hook and what its error output looks like
- [ ] Cross-reference `docs/explanation/tdd-workflow.md` for background

## Risk & Safety

- Touches money? No.
- Touches data? No — new documentation files only.
- Reversibility? Fully reversible: delete the three files.
- Risk: ADR-004 must be written after the enforcement machinery is in place (tickets 02–05) to accurately describe the actual implementation, not the aspirational one.
