---
title: "Build: a fresh worktree stays clean - generated files keep LF endings and card links ignore local deployments"
date: "2026-10-06"
time: "05:38"
type: manual
components: 
  - build_pipeline
  - worktree_manager
summary: "Creating a new worktree no longer leaves dozens of files modified: the build now writes generated files byte-identically on every platform, and agent cards no longer link to whatever happens to be deployed locally."
description: "Build writers now use LF endings and the card generator skips gitignored deployed copies, so a fresh worktree stays clean. Four stale cards were regenerated."
tickets: 
  - TICKET-20261002-WorktreeBootstrapLeavesTrackedFilesDirty
  - TICKET-20261006-GeneratedAgentCardsVsFileSizeRatchet
---

## Entry

### Changed

- `scripts/build*.py`, `scripts/generate_agent_cards.py` - generated files are written with LF on every platform; card link resolution ignores gitignored deployed copies.
- `docs/agents/cards/` - four stale cards regenerated.

### Added

- `unit_tests/build/test_build_leaves_tracked_files_clean.py`.
- `tickets/00_inbox/TICKET-20261006-GeneratedAgentCardsVsFileSizeRatchet.md` (follow-up).
