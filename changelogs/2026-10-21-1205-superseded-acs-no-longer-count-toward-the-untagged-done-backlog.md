---
title: "Superseded ACs no longer count toward the untagged-done backlog"
date: "2026-10-21"
time: "12:05"
type: manual
components: 
  - testing_quality
  - ac_store
summary: "The untagged-done backlog ratchet no longer counts acceptance criteria that have been superseded, since they have no current behaviour left to test, and its high-water mark drops from 244 to 240."
description: "Ported from 545285f42 (epic branch), without that commit's BO-2400f-3-i change. unit_tests/docs/test_artifact_graph_covers_scope.py: _collect_done_ac_ids now skips a record whose status is superseded or superseded_by (new _STATUS_SUPERSEDED_RE). Re-measured on origin/main 77354d6e9: 243 untagged done ACs under the old rule, 240 under the new one. HIGH_WATER_MARK lowered from 244 to 240 and its comment records the measurement."
breaking: false
---

## Entry
