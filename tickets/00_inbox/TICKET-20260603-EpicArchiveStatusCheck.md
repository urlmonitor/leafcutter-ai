---
title: "Epic archive pre-flight: verify all sub-ticket statuses before archiving"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/skills/finalize-feature-archive-check/SKILL.md
  - templates/workflows-js/finalize-feature.js
agents:
  architect-review: needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# Epic Archive Status Check

## Actor / Goal

As the finalize-feature workflow, before archiving an epic folder to 99_done/,
I need to verify that every completed sub-ticket has `status: done` in its YAML
frontmatter, so that downstream tooling (extract_epic_facts.py, retrospective
agent) correctly counts completed tickets.

## Context

During EPIC-MoveOnMainOnly, ticket 03 was archived without its frontmatter
`status:` being set to `done`. This caused `completed_ticket_count` to read 5
instead of 6 in the retrospective. The fix is a pre-archive validation skill
that can be invoked by finalize-feature.js Step 5.

## Acceptance Criteria

```gherkin
Given an epic folder with 6 sub-tickets in done/, 5 with status: done and 1 with status: todo
When the archive status check skill runs
Then it reports the 1 ticket missing status: done
 And it offers to fix the frontmatter automatically (confirmation-gated)

Given an epic folder with all sub-tickets having status: done
When the archive status check skill runs
Then it reports all clear and proceeds

Given finalize-feature.js Step 5
When the archive step runs
Then it invokes the status check skill before moving the folder
```

## Implementation Notes

- Create a skill (or script) that scans an epic's `done/` folder
- For each `.md` file, parse YAML frontmatter and check `status: done`
- Report any tickets that are NOT `status: done`
- Offer auto-fix (set `status: done` + commit) — confirmation-gated
- Integrate into finalize-feature.js Step 5 before the folder move
