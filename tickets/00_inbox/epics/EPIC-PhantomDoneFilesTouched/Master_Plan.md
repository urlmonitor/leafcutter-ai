---
epic_name: EPIC-PhantomDoneFilesTouched
created: 2026-07-06
status: in_progress
components:
  - build-pipeline
source_ac: BP-1100e
---
# EPIC-PhantomDoneFilesTouched

## Goal

This epic implements AC BP-1100e: A ticket cannot be called done when its real changes don't match what it said it would touch. It consists of 7 ticket(s) generated from the leaf ACs beneath BP-1100e, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20260706-BP-1100e-1.md](./01_TICKET-20260706-BP-1100e-1.md) | Before a ticket is marked done, source files changed but not declared are flagged | BP-1100e-1 | BP-1100e |
| 02 | [02_TICKET-20260706-BP-1100e-1-i.md](./02_TICKET-20260706-BP-1100e-1-i.md) | out_of_scope entries and generated/lockfiles are exempt from the mismatch flag | BP-1100e-1-i | BP-1100e-1 |
| 03 | [03_TICKET-20260706-BP-1100e-1-ii.md](./03_TICKET-20260706-BP-1100e-1-ii.md) | Path comparison is normalized for separators and case so NTFS/APFS paths are not false-flagged | BP-1100e-1-ii | BP-1100e-1 |
| 04 | [04_TICKET-20260706-BP-1100e-1-iii.md](./04_TICKET-20260706-BP-1100e-1-iii.md) | A docs-only or config-only ticket with legitimately narrow scope is not false-flagged | BP-1100e-1-iii | BP-1100e-1 |
| 05 | [05_TICKET-20260706-BP-1100e-1-iv.md](./05_TICKET-20260706-BP-1100e-1-iv.md) | The reconciliation no-ops cleanly when the ticket has no files_touched frontmatter | BP-1100e-1-iv | BP-1100e-1 |
| 06 | [06_TICKET-20260706-BP-1100e-2.md](./06_TICKET-20260706-BP-1100e-2.md) | The reconciliation is advisory and fails open by default; strict blocking is opt-in | BP-1100e-2 | BP-1100e, BP-1100e-1 |
| 07 | [07_TICKET-20260706-BP-1100e-3.md](./07_TICKET-20260706-BP-1100e-3.md) | A sequence diagram shows where the declared-vs-actual reconciliation sits before done | BP-1100e-3 | BP-1100e, BP-1100e-1, BP-1100e-2 |

## Dependencies

```
BP-1100e-1 (no dependencies)
BP-1100e-1-i -> BP-1100e-1
BP-1100e-1-ii -> BP-1100e-1
BP-1100e-1-iii -> BP-1100e-1
BP-1100e-1-iv -> BP-1100e-1
BP-1100e-2 -> BP-1100e-1
BP-1100e-3 -> BP-1100e-1, BP-1100e-2
```

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| architecture-diagram-author | 07 |
| commit | 01, 02, 03, 04, 05, 06, 07 |
| pr-reviewer | 01, 02, 03, 04, 05, 06, 07 |
| pull-request | 01, 02, 03, 04, 05, 06, 07 |
| python-coder | 01, 02, 03, 04, 05, 06 |
| test-runner | 01, 02, 03, 04, 05, 06, 07 |
| test-writer | 01, 02, 03, 04, 05, 06, 07 |

