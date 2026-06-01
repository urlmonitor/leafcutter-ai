---
title: "Add default_artifact_checklist to sql-query"
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
  documentation-expert: signed_off
  pr-reviewer: signed_off
  commit: failed
  pull-request: needed
---

# 02_13: Add default_artifact_checklist to sql-query

## Goal
Add `default_artifact_checklist` YAML frontmatter to `templates/agents/sql-query.md` so the agent always confirms these items in its `completion_manifest:` block on sign-off.

## Context
The sql-query agent (priority 7, role: coding) authors ad-hoc SQL queries for analysis/debugging. Its checklist should confirm the query was authored, reviewed for correctness, and past queries were consulted.

Source of truth: `config/agent_registry.json` entry with `"id": "sql-query"`.

## Checklist Items
```yaml
default_artifact_checklist:
  - query_authored
  - query_reviewed
  - past_queries_checked
```

## Acceptance Criteria
```gherkin
Given templates/agents/sql-query.md is read
When the frontmatter is parsed
Then a default_artifact_checklist key is present as a YAML list
And it contains exactly: query_authored, query_reviewed, past_queries_checked
```

## Sign-offs

- [x] documentation-expert — 2026-05-29 12:00
- [x] pr-reviewer — 2026-05-29 12:05
- [ ] commit — failed 2026-05-29 12:10
- [ ] pull-request

## Implementation Tasks

### documentation-expert
- [x] Edit `templates/agents/sql-query.md` frontmatter: add `default_artifact_checklist: [query_authored, query_reviewed, past_queries_checked]`
- [x] Add instruction paragraph in body referencing signoff §2b completion_manifest requirement

## Comments

### 2026-05-29 12:00 — documentation-expert (status: ok)
feedback-id: fb_2026-05-29_621d0073
completion_manifest:
  frontmatter_checklist_added: true
  instruction_paragraph_added: true
Added `default_artifact_checklist` (query_authored, query_reviewed, past_queries_checked) to `templates/agents/sql-query.md` frontmatter and added `## Completion Manifest (sign-off §2b)` instruction section referencing the signoff skill §2b contract.

### 2026-05-29 12:05 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-29_1af010a6
completion_manifest:
  checklist_items_correct: true
  pattern_matches_siblings: true
  acceptance_criteria_met: true
Changes are clean and minimal: `default_artifact_checklist` added to frontmatter with exactly the three items specified in the ticket (query_authored, query_reviewed, past_queries_checked); `## Completion Manifest (sign-off §2b)` instruction paragraph added following the same pattern as sql-coder.md. No regressions. Approved for commit.

### 2026-05-29 12:10 — commit (status: blocker)
feedback-id: fb_2026-05-29_25e0b811
completion_manifest:
  files_staged: true
  commit_created:
    result: false
    reason: "git commit failed: unable to write new index file — disk C:\\ is 100% full (237G/237G used)."
    remediation: "Free disk space on C:\\ then re-run the commit phase for this ticket."
Commit failed due to disk-full condition: `git commit` exits with "unable to write new index file". All implementation changes are staged and ready; only disk space is needed to complete this ticket.
