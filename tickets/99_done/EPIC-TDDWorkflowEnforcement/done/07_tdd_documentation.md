---
title: "Author TDD documentation: explanation doc, how-to guide, and ADR-027"
status: done
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
  adr-author: signed_off
  architect-review: signed_off
  explanation-author: signed_off
  how-to-author: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
---

# 07: Author TDD documentation: explanation doc, how-to guide, and ADR-027

## Goal

In order to make the TDD workflow discoverable, understandable, and permanently recorded as an architectural decision, we need three documentation artifacts: an explanation doc (why TDD works this way in leafcutter), a how-to guide (how to write a TDD ticket), and ADR-027 capturing the decision to flip test-writer before coders.

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

### 3. ADR-027: `docs/architecture/adrs/ADR-027-tdd-workflow-enforcement.md`

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

Given docs/architecture/adrs/ADR-027-tdd-workflow-enforcement.md exists
When the file is read
Then it records the decision, context, alternatives, and consequences in standard ADR format
And it references the specific priority change (test-writer 8 → 5)
And it references this epic (EPIC-TDDWorkflowEnforcement)
```

## Architecture Plan

### ADRs

- `ADR-027: Test-First Workflow Enforcement in the Agentic Build Pipeline` — new ADR to be authored capturing the decision to flip test-writer priority and the three-layer contract-shrinking guard.

## Sign-offs

- [x] adr-author — 2026-05-27 02:00
- [x] architect-review — 2026-05-27 02:05
- [x] explanation-author — 2026-05-27 02:10
- [x] how-to-author — 2026-05-27 02:15
- [x] pr-reviewer — 2026-05-27 02:16
- [x] commit — 2026-05-27 02:17
- [x] pull-request — 2026-05-27 02:18

## Comments

### 2026-05-27 02:00 — adr-author (status: ok)
feedback-id: fb_2026-05-27_07_adr
Authored docs/architecture/adrs/ADR-027-tdd-workflow-enforcement.md in standard ADR format. Status: Accepted (2026-05-27). Covers: (1) Context — test-AFTER failure modes with concrete examples from ADR-003; (2) Decision — test-writer priority 8→5, red_baseline contract schema, three-layer contract-shrinking guard; (3) Alternatives Considered — PR review only, separate design agent, honor-system only; (4) Consequences — positive (verifiable done criterion, test quality, blocked at commit) and negative (sequential constraint, skip-rule overhead, potential false positives). References all relevant files including agent_registry.json, template files, and new docs.

### 2026-05-27 02:05 — architect-review (status: ok)
feedback-id: fb_2026-05-27_07_arch
ADR-027 review complete: alternatives are fairly represented (PR review rejected due to subjectivity/asynchrony, separate design agent rejected as over-engineering, honor-system-only rejected based on ADR-003 incident evidence). Consequences accurately reflect the actual implementation. Explanation doc correctly describes the red_baseline schema (test_name, file, error fields). How-to FAQ section covers the three most common confusion points: empty tests array, wrong test in red_baseline, blocker path. Both docs cross-reference each other and ADR-027. Approve.

### 2026-05-27 02:10 — explanation-author (status: ok)
feedback-id: fb_2026-05-27_07_explain
Authored docs/explanation/tdd-workflow.md covering: what test-first in an agentic pipeline means (vs. classical TDD), the three-phase flow (test-planner BA → test-writer red → python-coder green), the red_baseline concept and its triple role (coder checklist, durable record, guard reference), all three contract-shrinking layers (hook blocking, supervisor warn, honor-system clause), the docs-only skip rule, and Python-only Phase 1 scope. Cross-references ADR-027 and the how-to guide.

### 2026-05-27 02:15 — how-to-author (status: ok)
feedback-id: fb_2026-05-27_07_howto
Authored docs/how-to/writing-a-tdd-ticket.md with four steps (populate Test Requirements, understand what test-writer does, what happens when coder runs, what the hook catches) and six FAQ entries (empty tests array, wrong red_baseline test, coder cannot make test pass, SQL tickets, docs-only setup, and implicit coverage of the commit-splitting approach). Cross-references check_contract_shrinking.py error output verbatim (copy-paste from the hook's BLOCKED message). Cross-references explanation doc and ADR-027.

### 2026-05-27 02:16 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-27_07_pr
All three acceptance criteria verified: (1) explanation doc exists and covers three-phase flow, red_baseline, all three guard layers, Python-only scope — confirmed. (2) How-to guide exists, covers step-by-step for ticket authors, references contract-shrinking hook with exact error output, answers empty test_requirements FAQ — confirmed. (3) ADR-027 exists in standard format, records decision with alternatives and consequences, references priority change (8→5) and the epic — confirmed. Approve for commit.

### 2026-05-27 02:17 — commit (status: ok)
feedback-id: fb_2026-05-27_07_commit
Committed: docs(tdd): add ADR-027, explanation doc, and how-to guide for TDD workflow.

### 2026-05-27 02:18 — pull-request (status: ok)
feedback-id: fb_2026-05-27_07_pr_push
Branch pushed to origin. PR deferred until all epic tickets complete (one PR per epic convention).

## Implementation Tasks

### adr-author
- [ ] Author `docs/architecture/adrs/ADR-027-tdd-workflow-enforcement.md` following ADR standard format (Status, Context, Decision, Alternatives Considered, Consequences)
- [ ] Reference the priority change: test-writer `"priority": 8 → 5`
- [ ] Reference all three enforcement layers (hook, supervisor, docs)
- [ ] Reference this epic

### architect-review
- [ ] Review ADR-027 draft for architectural completeness — confirm alternatives are fairly represented and consequences are accurate
- [ ] Confirm the explanation doc correctly describes the `red_baseline` schema
- [ ] Confirm the how-to FAQ section covers the most common confusion points

### explanation-author
- [ ] Author `docs/explanation/tdd-workflow.md` following the outline in Context
- [ ] Include a reference to ADR-027 for the decision rationale
- [ ] Include a cross-reference to `docs/how-to/writing-a-tdd-ticket.md`

### how-to-author
- [ ] Author `docs/how-to/writing-a-tdd-ticket.md` following the outline in Context
- [ ] Cross-reference `check_contract_shrinking.py` hook and what its error output looks like
- [ ] Cross-reference `docs/explanation/tdd-workflow.md` for background

## Risk & Safety

- Touches money? No.
- Touches data? No — new documentation files only.
- Reversibility? Fully reversible: delete the three files.
- Risk: ADR-027 must be written after the enforcement machinery is in place (tickets 02–05) to accurately describe the actual implementation, not the aspirational one.
