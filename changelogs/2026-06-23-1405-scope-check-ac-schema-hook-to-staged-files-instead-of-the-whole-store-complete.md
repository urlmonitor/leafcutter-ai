---
title: "Scope check-ac-schema hook to staged files instead of the whole store complete"
date: "2026-06-23"
time: "14:05"
type: ticket_completion
components: 
  - guardrail-engine
summary: "check-ac-schema Phase 1 now validates only staged AC YAML files, not the whole store."
description: "Phase 1 schema validation in the check-ac-schema pre-commit hook now validates only staged AC YAML files (via git diff --cached) instead of the whole store, while cross-file pattern lookups still resolve against the full on-disk store. The hook remains fail-open, and the unit-test harness was reworked (HOOK_TEST_STAGED_FILES seam) so the exit-1 schema tests exercise the staged-files path."
pr: 152
commits: 
  - 302fa33
  - e9f33c9
  - c43840a
  - 42d7967
ticket: "TICKET-20260622-AcSchemaHookStagedScope"
---

## Entry
