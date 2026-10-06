---
title: "Build orchestration: follow-ups from today's single-ticket /build-feature runs"
date: "2026-10-02"
time: "15:16"
type: manual
components: 
  - build_orchestration
  - changelog
summary: "Six pipeline defects seen while driving single-ticket /build-feature runs were checked against the existing tickets and ACs. One ticket was filed: a ticket drive should write the changelog entry that CI requires. The other five are already covered, and dated notes were added to the tickets that cover them."
description: "One new ticket: TICKET-20261002-BuildFeatureWritesChangelogEntry. A single-ticket drive gets a changelog step before commit, required only when the actual diff touches a non-exempt path, using the CI checker's own exempt list. A drive that needed an entry but has none is not completed (KI-CL-002). Already covered: worktree identity for ticket files and the agent-made worktree without a build bootstrap (EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace, tickets for BO-4300a-1-ia and BO-4300a-2, both annotated); stale renamed outputs in new worktrees (TICKET-20260930-RetireRenamedCommandOutputs, annotated, and BP-1500b); stale installed copies not being reported (BP-1500c, BO-4300b-2-ii); a pull-request phase that claims success without publishing, and duplicate sign-offs (BO-3100e-1, BO-3100b-2, BO-2900f-2-ii)."
---

## Entry

### Added

- `tickets/00_inbox/TICKET-20261002-BuildFeatureWritesChangelogEntry.md`: the single-ticket
  `/build-feature` drive writes the `changelogs/` entry that the required CI check demands.

### Changed

- `tickets/00_inbox/epics/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/02_TICKET-20260927-BO-4300a-1-ia.md`:
  a dated note on the agent-chosen worktree location and the missing build bootstrap.
- `tickets/00_inbox/epics/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05_TICKET-20260927-BO-4300a-2.md`:
  a dated note saying ticket-file targets need one identity, without `.md`.
- `tickets/00_inbox/TICKET-20260930-RetireRenamedCommandOutputs.md`: a dated note on stale
  `leafcutter.md` outputs reaching new worktrees.
