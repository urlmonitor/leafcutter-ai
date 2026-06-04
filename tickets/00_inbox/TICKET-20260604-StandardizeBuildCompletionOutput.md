---
title: "Standardize completion output for build-ticket and build-epic workflows"
status: todo
components:
  - infrastructure
created: 2026-06-04
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
user_facing_surface: null
actuation_contract: "When build-epic.js or build-single-ticket completes successfully, the user sees a consistent 4-section output: summary, worktree path, manual test suggestions, and a copy-pastable /finalize-feature command."
files_touched:
  - templates/workflows-js/build-epic.js
  - templates/skills/build-single-ticket/SKILL.md
  - templates/workflows/build-feature.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
out_of_scope:
  - build-backlog.md output (separate workflow, not user-facing in the same way)
  - Error/blocked output formatting (only success path is in scope)
  - Changing what data build-epic.js returns in its JSON — only the message/rendering
---

# Goal

When `build-epic.js` or `build-single-ticket` finish successfully, the output
is inconsistent. The epic path emits batch/ticket counts but no worktree path
or manual test hints. The single-ticket path emits a PR number and finalize
instructions but no summary of what was built, no worktree path, and no test
suggestions.

Standardize both success outputs to always include these four sections in order:

1. **Summary** — 2-3 sentences describing what was built (derived from ticket
   title/goal and files_touched for single-ticket; from epic title and ticket
   count for epics).
2. **Worktree path** — the absolute path so the user can `cd` into it or
   inspect files.
3. **Things to manually test** — 3-5 concrete smoke-test suggestions derived
   from the acceptance criteria and files_touched.
4. **Finalize command** — a copy-pastable `/finalize-feature <name>` with the
   epic name or ticket branch pre-filled. No editing required.

## Current state

### build-epic.js (Step 6 return)

```
Epic "EPIC-Foo" complete. 3 batch(es) run, 7 ticket(s) completed.
Next step: run /finalize-feature tickets/00_inbox/epics/EPIC-Foo to open the PR...
```

Missing: worktree path, manual test suggestions, summary beyond counts.

### build-feature.md (prose layer for epics)

```
Epic EPIC-Foo complete.
All sub-tickets signed off. Branch: EPIC-Foo.
Next step: run /finalize-feature EPIC-Foo to open the PR and close the worktree.
```

Missing: worktree path, manual test suggestions.

### build-single-ticket (Step 4c)

```
Ticket complete. PR #42 is open.
Review it in GitHub...then run /finalize-feature
```

Missing: summary of what was built, worktree path, manual test suggestions,
the finalize command is not pre-filled with the branch/ticket name.

## Acceptance Criteria

- [ ] AC1: build-epic.js Step 6 return object includes `worktree_path` and
  `manual_tests` fields alongside the existing `message`, `epic_path`, `title`,
  `batches_run`, `tickets_completed`, and `completed_batches`.
- [ ] AC2: build-epic.js Step 6 `message` string contains all four sections
  (summary, worktree, tests, finalize command) in that order.
- [ ] AC3: build-feature.md "On ok, print the completion message" block renders
  all four sections from the build-epic.js return value (preferred JS path).
- [ ] AC4: build-feature.md inline fallback completion message template includes
  all four sections with `WORKTREE_PATH` and `EPIC_NAME` placeholders.
- [ ] AC5: build-single-ticket Step 4c template includes all four sections:
  summary (from ticket Goal + files_touched), worktree path (from Step 2),
  manual test suggestions (from ACs + files_touched), and a copy-pastable
  `/finalize-feature <BRANCH>` with the branch name pre-filled.
- [ ] AC6: The finalize command in all three locations uses the epic name or
  branch name directly (not a raw path like `tickets/00_inbox/epics/EPIC-Foo`).

## Test Requirements

No automated tests — this is prose template and message formatting work.
Verification is manual: run /build-feature on a test epic or ticket and
confirm the output matches the four-section format.

## Sign-offs

- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
