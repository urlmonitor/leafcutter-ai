---
title: "EPIC: Fix Template Doc Violations Caught by Own Pre-commit Hooks"
type: epic
status: todo
components:
  - build_pipeline
  - sync_platforms
created: 2026-05-26
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
---

# EPIC: Fix Template Doc Violations Caught by Own Pre-commit Hooks

## Goal

In order to ship a self-consistent package, we need to fix all DECISION HISTORY
format violations and missing documentation artifacts in the leafcutter template
source files so that downstream projects built with `build.py` pass the very
pre-commit hooks leafcutter installs.

## Context

After a fresh `build.py` run in a downstream project the user received
`Check Documentation Requirements → Failed` from the pre-commit hook with:

- **Tail-tag violations** (`#EPIC-Name/NN` or `#TICKETLESS reason=...` missing)
  in four security-scanner skill scripts and two entries in the ticket-prioritizer
  skill script.
- **Missing HH:MM time** in three DECISION HISTORY entries across
  `sync_platforms.py` (template + deployed copy) and the deployed
  `scripts/feedback/submit_feedback.py`.
- **Missing directory README**: `scripts/sync_platforms/README.md` is absent
  despite the hook requiring a README for every directory with code.
- **UnicodeDecodeError** crashing the hook on Windows: `check_documentation.py`
  uses `subprocess.run(..., text=True)` without `encoding="utf-8"`, causing
  `cp1252` decoding failures when any staged file contains non-cp1252 bytes
  (e.g. em-dash in sign-off templates).

All fixes must land in the **leafcutter-ai/ source files** so that the next
`build.py` run in any downstream project produces clean output.

## Sub-Ticket Table

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_fix_security_scanner_tail_tags.md](./01_fix_security_scanner_tail_tags.md) | Add tail-tags to security-scanner skill script DECISION HISTORY entries | `[ ]` |
| 02 | [02_fix_ticket_prioritizer_tail_tags.md](./02_fix_ticket_prioritizer_tail_tags.md) | Add tail-tags to ticket-prioritizer skill script DECISION HISTORY entries | `[ ]` |
| 03 | [03_fix_sync_platforms_decision_history.md](./03_fix_sync_platforms_decision_history.md) | Fix missing HH:MM time in sync_platforms.py DECISION HISTORY (template + deployed) | `[ ]` |
| 04 | [04_add_sync_platforms_readme.md](./04_add_sync_platforms_readme.md) | Add README.md to templates/scripts/sync_platforms/ and deployed scripts/sync_platforms/ | `[ ]` |
| 05 | [05_fix_check_documentation_unicode.md](./05_fix_check_documentation_unicode.md) | Fix UnicodeDecodeError in check_documentation.py on Windows (subprocess encoding) | `[ ]` |

## Locked Design Decisions

- Fixes go to **source templates** in `leafcutter-ai/`; deployed copies in
  `scripts/` are updated in the same ticket where they exist.
- Tail-tags use `(#TICKETLESS reason=template-initial-impl)` because these are
  initial-implementation entries where no ticket number exists in leafcutter's history.
- Max nesting depth: 3.
