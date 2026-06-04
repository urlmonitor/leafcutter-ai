---
title: "Update test-writer and python-coder agent prompts to enforce fixture convention"
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on:
  - 01_conftest_fixture_helper.md
priority: medium
phase: "Phase 2"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/agents/test-writer.md
  - templates/agents/python-coder.md
  - docs/testing/README.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
requires_documentation:
  - how_to
---

# 03: Update test-writer and python-coder agent prompts to enforce fixture convention

## Actor / Goal

In order to make the fixture convention self-enforcing for all AI-authored
tests, we need to update the `test-writer` and `python-coder` agent prompt
templates with an explicit data-extraction rule, so that agents automatically
externalise large dicts and parametrize tables to JSON fixture files without
requiring human review on every PR.

## Context

Agent prompts are the primary enforcement mechanism for conventions in this
project — agents only apply rules they have been explicitly told about. Without
a prompt update, `test-writer` and `python-coder` will continue inlining data
regardless of the hook (ticket 02) or the directory structure (ticket 01).

This ticket is docs-and-prompt only: no Python code changes. It depends on
ticket 01 (the directory and helper exist) but not on ticket 02 (the hook does
not need to be active for agents to follow the convention).

### Required prompt additions

**test-writer** — add to the "Test Authoring Rules" (or equivalent) section:

> If any test needs a dict with more than 5 keys or a parametrize table with
> more than 3 rows, extract the data to `tests/fixtures/<module>/<descriptive_name>.json`
> where `<module>` is this test file's stem minus the `test_` prefix.
> Load it via `load_fixture('<module>/<descriptive_name>')` (imported from
> `tests/conftest.py`). Do not inline large data structures directly in test
> functions or parametrize decorators.

**python-coder** — add to the "Test Delegation" section (the section that
describes when to hand off to test-writer):

> When delegating test authoring: remind test-writer that any dict with >5 keys
> or parametrize table with >3 rows must be externalised to a JSON fixture file
> under `tests/fixtures/` and loaded via `load_fixture()`. See
> `docs/testing/README.md` §Fixture Convention.

**docs/testing/README.md** — add a callout box (or bold note) in the Fixture
Convention section established by ticket 01:

> **Agents are required to read this section.** test-writer and python-coder
> are instructed in their system prompts to consult this file before authoring
> tests. If you observe an agent inlining large data blobs, the agent prompt
> may have drifted — file a ticket to update it.

## Acceptance Criteria

```gherkin
Given templates/agents/test-writer.md is reviewed
When the test authoring rules section is read
Then it contains an explicit instruction to extract dicts with >5 keys to fixture JSON files
 And it contains an explicit instruction to extract parametrize tables with >3 rows to fixture JSON files
 And it references load_fixture() by name
 And it specifies the tests/fixtures/<module>/ path pattern

Given templates/agents/python-coder.md is reviewed
When the test delegation section is read
Then it contains an instruction to remind test-writer of the fixture extraction rule
 And it references docs/testing/README.md §Fixture Convention

Given docs/testing/README.md is reviewed after this ticket
When the fixture convention section is read
Then it contains a note that agents are required to read this section
 And the note references test-writer and python-coder by name
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### documentation-expert
- [ ] Update `templates/agents/test-writer.md`:
  - Locate the test authoring rules section (search for "rule" or "when to"
    near test-writing guidelines)
  - Insert the fixture extraction rule immediately after the section header:
    dict threshold (>5 keys), parametrize threshold (>3 rows), target path
    `tests/fixtures/<module>/<name>.json`, load via `load_fixture()`.
  - Do not alter any other section or the agent's frontmatter.
- [ ] Update `templates/agents/python-coder.md`:
  - Locate the "Test Delegation" section
  - Append the reminder to pass the fixture-extraction constraint to test-writer
  - Reference `docs/testing/README.md §Fixture Convention`
- [ ] Update `docs/testing/README.md`:
  - In the Fixture Convention section (written by ticket 01), add a bold callout:
    "Agents are required to read this section" with the names test-writer and
    python-coder, and instructions on how to file a ticket if agent drift is
    observed.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? High — prompt template changes are text edits; reverted via
  `git revert`. The note in the README is purely additive.
- Agent prompt drift risk: if `build.py` regenerates agent files from templates
  on next build, confirm these edits survive the build step. The build pipeline
  injects paths.json substitutions but does not rewrite prose sections — these
  edits should be safe. Verify with `python scripts/build.py --validate` after
  editing.
