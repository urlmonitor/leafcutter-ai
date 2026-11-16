---
title: "The informational mypy job is green on the Windows lock module"
date: "2026-11-01"
time: "14:00"
type: manual
components:
  - build_orchestration
summary: "The informational mypy job failed on Linux at the Windows lock call, because msvcrt is declared for win32 only. That call now carries the same type-ignore as the module's platform imports. No behaviour change."
description: >-
  scripts/suite_performance/_shared_layout_coordination.py: type-ignore on the
  win32-only msvcrt call in _acquire_windows. Ticket
  TICKET-20261030-HousekeepingTestTriggersOnGit256.
breaking: false
---

## Entry
