---
description: >
  Run an automated epic retrospective. Reads all completed tickets in the
  named epic folder, parses Comments sections for retry patterns and blockers,
  and generates a structured retrospective artifact with proposed Knowledge
  Item entries and rule-update diffs for user approval.
---

Invoke the `retrospective-agent` agent with the user's arguments: $ARGUMENTS

<!-- Usage:
  /retro EPIC-Name
    Run a retrospective for the named epic. The epic folder must exist under
    tickets/00_inbox/epics/ or tickets/99_done/ (done folder checked first).

  /retro EPIC-Name --dry-run
    Show what the retrospective would contain without writing any files.

  /retro EPIC-Name --since 2026-01-01
    Limit telemetry and commit log analysis to entries after the given date.

The epic name argument is required. The agent reads all sub-tickets, parses
## Comments blocks for retry counts and blocker categories, and proposes
Knowledge Item entries and rule updates as diffs — it never auto-applies them.
-->
