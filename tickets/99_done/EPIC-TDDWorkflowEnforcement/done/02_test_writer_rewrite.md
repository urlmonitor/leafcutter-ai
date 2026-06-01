---
title: "Rewrite test-writer agent: test-FIRST role, red-baseline capture, docs-only skip rule"
status: done
components:
  - build_pipeline
created: 2026-05-26
depends_on:
  - 01_agent_registry_priority_update.md
priority: high
requires_diagram: false
requires_adr: false
agents:
  architect-review: signed_off
  python-coder: signed_off
  test-writer: not_needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
---

# 02: Rewrite test-writer agent: test-FIRST role, red-baseline capture, docs-only skip rule

## Goal

In order to enforce the TDD red-green cycle, we need to rewrite the `test-writer` agent definition so it (a) runs **before** coders and writes failing tests, (b) captures a mandatory structured `red_baseline` block in its sign-off comment, and (c) skips entirely when `## Test Requirements` has an empty `tests` array (docs-only / config-only tickets).

## Context

The current `test-writer` agent (`leafcutter-ai/templates/agents/test-writer.md` and its deployed copy `.claude/agents/test-writer.md`) is written as a post-coder agent: it receives a handoff from `python-coder`, reads the finished implementation, and writes tests that match the code. This is test-AFTER.

The desired state:
1. `test-writer` runs at priority 5 (after `architect-review`, before `python-coder`).
2. Its input is the ticket's `## Test Requirements` block (authored by `test-planner` during BA flow).
3. It writes tests that are deliberately failing — the suite must be red after test-writer completes.
4. Its sign-off comment MUST include a structured `red_baseline` block:
   ```
   red_baseline:
     - test_name: test_foo_raises_on_empty_input
       file: unit_tests/my_module/test_foo.py
       error: "AssertionError: expected ValueError, got None"
     - ...
   ```
5. When `## Test Requirements` → `tests: []` (empty array), test-writer skips its own phase by appending `(status: ok)` with a note "test_requirements empty — skipping test-writer phase (docs/config-only ticket)" and immediately signing off as `signed_off` without writing any test files.
6. The coder agents (see ticket 03) will receive this `red_baseline` as their explicit success target.

Files to update:
- `leafcutter-ai/templates/agents/test-writer.md` (source of truth for the template)
- `.claude/agents/test-writer.md` (deployed copy — must stay in sync)

## Acceptance Criteria

```gherkin
Given a ticket with a non-empty ## Test Requirements tests array
When test-writer runs (priority 5, before python-coder)
Then it writes failing test stubs to the paths declared in test_requirements.tests[*].target_dir
And it runs the test suite to confirm the new tests are RED
And its sign-off comment includes a structured red_baseline block with at least one entry per test written
And the sign-off status is "ok"

Given a ticket whose ## Test Requirements tests array is empty (docs/config-only)
When test-writer runs
Then it appends "(status: ok) — test_requirements empty: skipping test-writer phase (docs/config-only ticket)"
And it immediately signs off as signed_off
And it writes zero test files

Given the red_baseline block in the test-writer sign-off comment
When python-coder reads it
Then it uses that block as the explicit success target: "all these tests must be green; no previously-passing test may go red"
```

## Sign-offs

- [x] architect-review — 2026-05-27 01:20
- [x] python-coder — 2026-05-27 01:25
- [x] pr-reviewer — 2026-05-27 01:26
- [x] commit — 2026-05-27 01:27
- [x] pull-request — 2026-05-27 01:28

## Comments

### 2026-05-27 01:20 — architect-review (status: ok)
feedback-id: fb_2026-05-27_02_arch
red_baseline schema confirmed sufficient for python-coder: test_name + file + error fields give coders the exact failure to target. Schema placement confirmed: red_baseline YAML block goes in the comment body after the (status: ok) line — this is outside the parser-strict heading regex (which only matches the `### YYYY-MM-DD HH:MM — <agent> (status: ...)` line), so the structured block is safe to embed and won't break the ticket-supervisor routing. Docs-only skip rule confirmed: appending (status: ok) with skip note and signing off immediately routes correctly through the ticket-supervisor ok → GOTO 1 loop without any special casing. No ADR required.

### 2026-05-27 01:25 — python-coder (status: ok)
feedback-id: fb_2026-05-27_02_coder
Rewrote templates/agents/test-writer.md: (a) description frontmatter updated to reflect test-FIRST role, BEFORE python-coder, with red_baseline capture; (b) adopter_notes updated — invoked BEFORE python-coder; (c) intro paragraph rewritten — TDD test-first agent, tests MUST be red when signing off; (d) Dispatch Contract section rewritten — runs before all coders, new sequence diagram, docs-only skip rule added explicitly; (e) Step 1 pre-flight updated — skip rule reference replaces old "sign off as not_needed equivalent" prose; (f) Step 2g rewritten — failing stubs for not-yet-implemented behavior, no xfail/skip, expect ImportError/AssertionError; (g) Step 4 rewritten — required outcome is non-zero exit (red), outcome handling table, green-before-impl is a problem; (h) Output section rewritten — Completion Report + Red Baseline block, mandatory red_baseline YAML schema with required fields. Applied identical changes to deployed copy .claude/worktrees/.claude/agents/test-writer.md.

### 2026-05-27 01:26 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-27_02_pr
All three acceptance criteria verified: (1) non-empty tests array path: test-writer writes stubs, runs to confirm red, captures red_baseline in sign-off with test_name+file+error — confirmed in Step 4 and Output section. (2) Empty tests array path: skip rule fires, appends ok comment with "test_requirements empty" note, zero file writes, immediate sign-off — confirmed in Dispatch Contract §Docs-only skip rule. (3) red_baseline handoff to coders: coders use red_baseline as explicit success target — confirmed in the schema and in the python-coder update (ticket 03). Approve for commit.

### 2026-05-27 01:27 — commit (status: ok)
feedback-id: fb_2026-05-27_02_commit
Committed: feat(tdd): rewrite test-writer agent — TDD test-first role, red-baseline capture.

### 2026-05-27 01:28 — pull-request (status: ok)
feedback-id: fb_2026-05-27_02_pr_push
Branch pushed to origin. PR deferred until all epic tickets complete (one PR per epic convention).

## Implementation Tasks

### architect-review
- [ ] Review the `red_baseline` block schema — confirm it is sufficient for `python-coder` to use as a success target (needs: test name, file path, and the actual error/assertion seen)
- [ ] Confirm the sign-off comment format is compatible with `signoff` SKILL.md §5.4 parser-strict regex (the structured block is embedded inside the comment body)
- [ ] Confirm the docs-only skip rule integrates cleanly with the existing `(status: ok)` routing in `ticket-supervisor`

### python-coder
- [ ] Rewrite `leafcutter-ai/templates/agents/test-writer.md`:
  - [ ] Update the `description:` frontmatter to reflect test-FIRST role
  - [ ] Replace the existing "receive handoff from coder" preamble with "run before coders from ## Test Requirements block"
  - [ ] Add the `red_baseline` structured sign-off contract with the exact YAML schema shown in Context
  - [ ] Add the docs-only skip rule (empty `tests` array → immediate ok sign-off, zero file writes)
  - [ ] Add: "run `pytest <target_dir>` after writing tests; confirm exit code is non-zero (tests are red); if any new test passes immediately, that test is under-specified — add a TODO comment and flag in red_baseline"
  - [ ] Update the `## Sign-offs` wording to require the `red_baseline` block
- [ ] Apply the identical changes to `.claude/agents/test-writer.md` (deployed copy)

## Risk & Safety

- Touches money? No.
- Touches data? No — agent definition markdown files only.
- Reversibility? Fully reversible: revert the template and deployed copy to the prior content.
- Risk: If the `red_baseline` schema is not parseable by `ticket-supervisor`'s comment regex, the supervisor may misroute. Architect-review must confirm the schema placement is outside the `(status: ok)` line itself (it goes in the comment body after the status line).
