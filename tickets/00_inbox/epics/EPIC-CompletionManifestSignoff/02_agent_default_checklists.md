---
title: "Add default_artifact_checklist to phase agent templates"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on:
  - 01_signoff_skill_manifest_section.md
priority: high
requires_diagram: false
requires_adr: false
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
---

# 02: Add default_artifact_checklist to phase agent templates

## Goal
In order to give each phase agent a baseline checklist it always confirms in its completion_manifest, we need to add `default_artifact_checklist:` to the YAML frontmatter of every phase agent template.

## Context
Depends on ticket 01 (signoff skill §2b) which defines the manifest format. The `default_artifact_checklist` is a list of item names that the agent MUST confirm in its `completion_manifest:` on every ticket, regardless of ticket-level overrides. Ticket-level `artifact_checklist:` items (ticket 04) merge with and can extend or override these defaults at dispatch time.

Files to edit (all in `templates/agents/`):
- `python-coder.md` — checklist: `code_implemented`, `tests_passing`, `doc_enforcer_clean`, `complexity_check_clean`
- `sql-coder.md` — checklist: `sql_deployed_locally`, `sql_tests_passing`, `naming_conventions_met`
- `test-writer.md` — checklist: `test_stubs_created`, `all_tests_red`, `red_baseline_captured`
- `pr-reviewer.md` — checklist: `diff_reviewed`, `no_high_findings`, `scope_verified`
- `commit.md` — checklist: `pre_commit_hooks_pass`, `commit_message_valid`, `ticket_staged`
- `documentation-expert.md` — checklist: `doc_written`, `cross_links_added`, `diataxis_genre_correct`
- `changelog-agent.md` — checklist: `changelog_entry_created`, `frontmatter_valid`, `category_correct`
- `adr-author.md` — checklist: `adr_file_created`, `all_sections_present`, `status_set`

The frontmatter addition looks like:
```yaml
default_artifact_checklist:
  - code_implemented
  - tests_passing
  - doc_enforcer_clean
  - complexity_check_clean
```

## Acceptance Criteria
```gherkin
Given a phase agent template (e.g. python-coder.md) is read
When the frontmatter is parsed
Then a default_artifact_checklist key is present as a YAML list of strings

Given the default_artifact_checklist for python-coder
When inspected
Then it contains exactly: code_implemented, tests_passing, doc_enforcer_clean, complexity_check_clean

Given the default_artifact_checklist for sql-coder
When inspected
Then it contains exactly: sql_deployed_locally, sql_tests_passing, naming_conventions_met

Given the default_artifact_checklist for test-writer
When inspected
Then it contains exactly: test_stubs_created, all_tests_red, red_baseline_captured

Given the default_artifact_checklist for commit
When inspected
Then it contains exactly: pre_commit_hooks_pass, commit_message_valid, ticket_staged

Given all 8 phase agent templates are read
When each frontmatter is checked
Then every template has a non-empty default_artifact_checklist
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### documentation-expert
- [ ] Edit `templates/agents/python-coder.md` frontmatter: add `default_artifact_checklist: [code_implemented, tests_passing, doc_enforcer_clean, complexity_check_clean]`
- [ ] Edit `templates/agents/sql-coder.md` frontmatter: add `default_artifact_checklist: [sql_deployed_locally, sql_tests_passing, naming_conventions_met]`
- [ ] Edit `templates/agents/test-writer.md` frontmatter: add `default_artifact_checklist: [test_stubs_created, all_tests_red, red_baseline_captured]`
- [ ] Edit `templates/agents/pr-reviewer.md` frontmatter: add `default_artifact_checklist: [diff_reviewed, no_high_findings, scope_verified]`
- [ ] Edit `templates/agents/commit.md` frontmatter: add `default_artifact_checklist: [pre_commit_hooks_pass, commit_message_valid, ticket_staged]`
- [ ] Edit `templates/agents/documentation-expert.md` frontmatter: add `default_artifact_checklist: [doc_written, cross_links_added, diataxis_genre_correct]`
- [ ] Edit `templates/agents/changelog-agent.md` frontmatter: add `default_artifact_checklist: [changelog_entry_created, frontmatter_valid, category_correct]`
- [ ] Edit `templates/agents/adr-author.md` frontmatter: add `default_artifact_checklist: [adr_file_created, all_sections_present, status_set]`

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? Additive-only frontmatter edits to template files; no existing keys removed. Fully reversible.
