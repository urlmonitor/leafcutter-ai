---
title: "Rewrite test-writer agent: test-FIRST role, red-baseline capture, docs-only skip rule"
status: todo
components:
  - build_pipeline
created: 2026-05-26
depends_on:
  - 01_agent_registry_priority_update.md
priority: high
requires_diagram: false
requires_adr: false
agents:
  architect-review: needed
  python-coder: needed
  test-writer: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
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

- [ ] architect-review
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

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
