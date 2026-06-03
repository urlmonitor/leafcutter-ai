---
title: "Remove stale 00_inbox copies of the 2 known duplicate tickets"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - tickets/00_inbox/TICKET-20260527-WireVersionIntoBuild.md
  - tickets/00_inbox/TICKET-20260602-ComponentsRegistryScaffold.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# 06: Remove stale 00_inbox copies of the 2 known duplicate tickets

## Actor / Goal

In order to resolve the 2 confirmed live duplicates in the repo, we need to
remove the stale `00_inbox/` copies of `TICKET-20260527-WireVersionIntoBuild.md`
and `TICKET-20260602-ComponentsRegistryScaffold.md`, so that each ticket
exists in exactly one lifecycle folder.

## Context

Two ticket files currently have copies in both `tickets/00_inbox/` and
`tickets/99_done/`:

```
tickets/00_inbox/TICKET-20260527-WireVersionIntoBuild.md    ← STALE (remove)
tickets/99_done/TICKET-20260527-WireVersionIntoBuild.md     ← CANONICAL (keep)

tickets/00_inbox/TICKET-20260602-ComponentsRegistryScaffold.md    ← STALE (remove)
tickets/99_done/TICKET-20260602-ComponentsRegistryScaffold.md     ← CANONICAL (keep)
```

The `99_done/` copies are canonical: they reflect the completed state of the
tickets (status: done, signed-off). The `00_inbox/` copies are stale
remnants left behind when `git mv` from inbox → 99_done was processed in a
merge that git couldn't track as a rename — leaving the old copy undeleted.

### Verification before deletion

Before removing the `00_inbox/` copies, verify:
1. The `99_done/` copy exists and its frontmatter has `status: done`.
2. The `00_inbox/` copy has the same basename and lower or equal `status:`
   (should be `todo` or older, never `done` — if it shows `done` something
   unusual happened).
3. The `00_inbox/` copy is identical to or an older version of the
   `99_done/` copy.

If both copies have `status: done` and identical content, the `00_inbox/`
copy is a pure duplicate — safe to delete.

If the `00_inbox/` copy has content not present in `99_done/` (e.g. sign-off
edits that didn't make it), merge the missing content into `99_done/` before
deleting. This is unlikely but must be checked.

### This ticket can run in parallel with tickets 01–05

This cleanup is independent of the pattern changes in tickets 01–05. It can
be driven and merged first (to immediately resolve the known duplicates)
or last (as a post-epic cleanup). It does NOT depend on any other ticket in
this epic.

### `depends_on: []`

Explicitly set to empty — this ticket has no dependency on the other
EPIC-MoveOnMainOnly tickets. The duplicate problem exists today on main and
should be resolved as soon as possible, independently of when the pattern
changes land.

## Acceptance Criteria

```gherkin
Given the repo contains the 2 known duplicate tickets
When this ticket is driven
Then tickets/00_inbox/TICKET-20260527-WireVersionIntoBuild.md is deleted from the repo
 And tickets/99_done/TICKET-20260527-WireVersionIntoBuild.md remains intact with status: done
 And tickets/00_inbox/TICKET-20260602-ComponentsRegistryScaffold.md is deleted from the repo
 And tickets/99_done/TICKET-20260602-ComponentsRegistryScaffold.md remains intact with status: done

Given git diff --stat of the commit produced by this ticket
When the diff is reviewed
Then it shows exactly 2 deletions (D entries) with no modifications to 99_done/ copies

Given check_ticket_state_integrity.py is run after this ticket merges
When the duplicate check runs
Then it reports no duplicates for either ticket basename
```

## Sign-offs

- [x] pr-reviewer — 2026-06-03 12:00
- [x] commit — 2026-06-03 12:05
- [ ] pull-request

## Comments

### 2026-06-03 12:00 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-03_fc0fefa7
completion_manifest:
  canonical_copies_verified: true
  inbox_copies_are_stale: true
  no_unique_content_in_inbox: true
  deletion_is_safe: true
Reviewed the two duplicate ticket pairs. The 99_done/ copies of both TICKET-20260527-WireVersionIntoBuild.md (226 lines, all agents signed_off/failed) and TICKET-20260602-ComponentsRegistryScaffold.md (313 lines, status: done) are canonical and more complete. The 00_inbox/ copies are strictly older versions (184 and 272 lines respectively) with no unique content not present in 99_done/. Git rm of the 00_inbox/ copies is safe — no content loss. Plan approved.

### 2026-06-03 12:05 — commit (status: ok)
feedback-id: fb_2026-06-03_9ea05ef5
completion_manifest:
  staged_explicit_paths_only: true
  commit_created: true
  no_unintended_files: true
  two_deletions_only: true
Executed git rm on both stale inbox copies (TICKET-20260527-WireVersionIntoBuild.md and TICKET-20260602-ComponentsRegistryScaffold.md). Staged explicitly by path. Committed with chore message — 2 file deletions only, no modifications to 99_done/ canonical copies.

## Implementation Tasks

- [ ] Verify the `99_done/` copy of `TICKET-20260527-WireVersionIntoBuild.md`
  has `status: done` in its frontmatter:
  ```bash
  head -10 tickets/99_done/TICKET-20260527-WireVersionIntoBuild.md
  ```
- [ ] Verify the `99_done/` copy of `TICKET-20260602-ComponentsRegistryScaffold.md`
  has `status: done` in its frontmatter:
  ```bash
  head -10 tickets/99_done/TICKET-20260602-ComponentsRegistryScaffold.md
  ```
- [ ] Compare each `00_inbox/` copy against its `99_done/` counterpart to
  confirm no unique content is present in the inbox copy:
  ```bash
  diff tickets/00_inbox/TICKET-20260527-WireVersionIntoBuild.md \
       tickets/99_done/TICKET-20260527-WireVersionIntoBuild.md
  diff tickets/00_inbox/TICKET-20260602-ComponentsRegistryScaffold.md \
       tickets/99_done/TICKET-20260602-ComponentsRegistryScaffold.md
  ```
- [ ] If both diffs show only `status:` differences (inbox shows `todo`,
  done shows `done`) or are identical: proceed to deletion.
- [ ] If any diff shows substantive content in the inbox copy not in 99_done/:
  manually merge the unique content into the `99_done/` copy before deletion.
- [ ] Delete the two stale copies:
  ```bash
  git rm tickets/00_inbox/TICKET-20260527-WireVersionIntoBuild.md
  git rm tickets/00_inbox/TICKET-20260602-ComponentsRegistryScaffold.md
  ```
- [ ] Commit:
  ```bash
  git commit -m "chore(tickets): remove stale 00_inbox duplicates (EPIC-MoveOnMainOnly/06)"
  ```
- [ ] Verify `git log --oneline -1` shows the commit and
  `git diff HEAD~1 HEAD -- tickets/00_inbox/` shows 2 deletions only.

## Risk & Safety

- Touches money? No.
- Touches data? Ticket files are deleted from `00_inbox/`. The canonical
  copies in `99_done/` are untouched. Deletion is reversible via
  `git revert` or `git checkout <sha> -- <path>`.
- Reversibility? Fully reversible — git history retains the deleted content.
- Risk: if the `00_inbox/` copies contain unique sign-off or comment content
  not merged to `99_done/`, that content would be lost. Mitigated by the
  `diff` step in Implementation Tasks above.
- No production risk: these are documentation files. Their removal does not
  affect any running system.
