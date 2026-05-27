---
title: "Follow-on stub: create EPIC-SQLTDDEnforcement in tickets/00_inbox/epics/"
status: done
components:
  - build_pipeline
created: 2026-05-26
depends_on:
  - 07_tdd_documentation.md
priority: low
requires_diagram: false
requires_adr: false
agents:
  architect-review: not_needed
  python-coder: not_needed
  test-writer: not_needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
---

# 08: Follow-on stub: create EPIC-SQLTDDEnforcement in tickets/00_inbox/epics/

## Goal

In order to ensure SQL TDD is not forgotten after this epic closes, we need a concrete follow-on placeholder — a stub ticket file that, when executed, creates the `EPIC-SQLTDDEnforcement` folder with a minimal `Master_Plan.md` in `tickets/00_inbox/epics/`.

## Context

SQL TDD was explicitly descoped from EPIC-TDDWorkflowEnforcement (Python-only decision, see Master_Plan). The SQL flow involves `sql-test-writer` (separate agent from `test-writer`), `sql-coder`, and its own test-first ordering. The current `sql-coder` priority is 7; for SQL TDD, `sql-test-writer` would need to run before `sql-coder` at something like priority 6.5 or by reclassifying `sql-test-writer` from `is_ticket_phase: false` to `is_ticket_phase: true` and assigning it a priority.

This ticket's sole deliverable is: **create the `EPIC-SQLTDDEnforcement` folder with a `Master_Plan.md`** in `tickets/00_inbox/epics/` so that the SQL TDD work has a home in the inbox. No sub-tickets need to be authored here; the epic creation is the artifact.

The `Master_Plan.md` should include:
- Title: `EPIC: SQL TDD Enforcement`
- Status: `todo`
- A brief summary: "Extend the TDD workflow enforcement (EPIC-TDDWorkflowEnforcement) to cover SQL tests. Flip sql-test-writer to run before sql-coder."
- A reference to EPIC-TDDWorkflowEnforcement as the Python TDD predecessor
- An empty sub-tickets table (to be filled by the user or a future `/create-epic` invocation)

## Acceptance Criteria

```gherkin
Given this ticket is executed
When the deliverable is produced
Then tickets/00_inbox/epics/EPIC-SQLTDDEnforcement/Master_Plan.md exists
And its frontmatter has type: epic and status: todo
And its body references EPIC-TDDWorkflowEnforcement as the Python TDD predecessor
And its body contains an empty sub-tickets table
```

## Sign-offs

- [x] pr-reviewer — 2026-05-27 02:30
- [x] commit — 2026-05-27 02:31
- [x] pull-request — 2026-05-27 02:32

## Comments

### 2026-05-27 02:30 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-27_08_pr
Acceptance criteria verified: tickets/00_inbox/epics/EPIC-SQLTDDEnforcement/Master_Plan.md exists, frontmatter has type: epic and status: todo, body references EPIC-TDDWorkflowEnforcement as Python TDD predecessor, body contains empty sub-tickets table. Additionally: Master_Plan includes Key Design Decisions section (required by epic-supervisor pre-flight gate), scope section, and out-of-scope section. Approve for commit.

### 2026-05-27 02:31 — commit (status: ok)
feedback-id: fb_2026-05-27_08_commit
Committed: chore(epic): create EPIC-SQLTDDEnforcement stub in tickets/00_inbox/epics/.

### 2026-05-27 02:32 — pull-request (status: ok)
feedback-id: fb_2026-05-27_08_pr_push
Branch pushed to origin. PR deferred until all epic tickets complete (one PR per epic convention).

## Implementation Tasks

- [ ] Create `tickets/00_inbox/epics/EPIC-SQLTDDEnforcement/` directory
- [ ] Write `tickets/00_inbox/epics/EPIC-SQLTDDEnforcement/Master_Plan.md` with the required content (see Context)
- [ ] Verify the `ticket_frontmatter_guard` hook accepts the file (type: epic, status: todo, components, created, depends_on, priority)

## Risk & Safety

- Touches money? No.
- Touches data? No — new ticket files only.
- Reversibility? Fully reversible: delete the folder.
- Note: This is a stub/placeholder ticket. It does no implementation beyond creating the epic folder. The actual SQL TDD work is the follow-on epic's responsibility.
