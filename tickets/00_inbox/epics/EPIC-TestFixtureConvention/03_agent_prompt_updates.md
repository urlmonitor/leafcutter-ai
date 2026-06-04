---
title: "Update test-writer and python-coder agent prompts to enforce fixture convention"
status: done
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
  documentation-expert: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
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

- [x] documentation-expert — 2026-06-04 10:15
- [x] pr-reviewer — 2026-06-04 10:18
- [x] commit — 2026-06-04 10:22
- [x] pull-request — 2026-06-04 10:25

## Comments

### 2026-06-04 10:15 — documentation-expert (status: ok)
feedback-id: fb_2026-06-04_46159175
completion_manifest:
  doc_written: true
  cross_links_added: true
  diataxis_genre_correct: true
Updated all three target files: added §2h Fixture Extraction Rule to `templates/agents/test-writer.md` after the failing-stubs section; appended fixture-extraction reminder to the Test Delegation section of `templates/agents/python-coder.md` with a reference to `docs/testing/README.md §Fixture Convention`; added agent-required callout at the top of the Fixture Convention section in `docs/testing/README.md`. All Acceptance Criteria satisfied.

### 2026-06-04 10:18 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-04_6e5f6595
completion_manifest:
  diff_reviewed: true
  no_high_findings: true
  scope_verified: true
Reviewed 24-line diff across 3 files. All Acceptance Criteria satisfied. No high-confidence or medium-confidence findings. Scope matches `files_touched` exactly — only `templates/agents/test-writer.md`, `templates/agents/python-coder.md`, and `docs/testing/README.md` were modified. Escalation: none (medium count was 0, threshold >3).

### 2026-06-04 10:22 — commit (status: ok)
feedback-id: fb_2026-06-04_c8376710
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Staged 4 files: templates/agents/test-writer.md, templates/agents/python-coder.md, docs/testing/README.md, and the ticket file. Committed as feat(agents): add fixture extraction rule to test-writer and python-coder prompts.

### 2026-06-04 10:25 — pull-request (status: ok)
feedback-id: fb_2026-06-04_670f09fa
completion_manifest:
  branch_pushed: true
  pr_created: true
  pr_body_complete: true
PR #44 (https://github.com/urlmonitor/leafcutter-ai/pull/44) already exists for branch EPIC-TestFixtureConvention. All commits including this ticket's fixture-convention prompt updates are in the remote HEAD. No push required. Ticket status flipped to done — all agents are signed_off or not_needed.

## Implementation Tasks

### documentation-expert
- [x] Update `templates/agents/test-writer.md`:
  - Locate the test authoring rules section (search for "rule" or "when to"
    near test-writing guidelines)
  - Insert the fixture extraction rule immediately after the section header:
    dict threshold (>5 keys), parametrize threshold (>3 rows), target path
    `tests/fixtures/<module>/<name>.json`, load via `load_fixture()`.
  - Do not alter any other section or the agent's frontmatter.
- [x] Update `templates/agents/python-coder.md`:
  - Locate the "Test Delegation" section
  - Append the reminder to pass the fixture-extraction constraint to test-writer
  - Reference `docs/testing/README.md §Fixture Convention`
- [x] Update `docs/testing/README.md`:
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
