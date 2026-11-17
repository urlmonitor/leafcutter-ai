---
title: "Approving a /plan-feature gate is no longer silently lost when the saved pause record cannot be read"
date: "2026-10-09"
time: "14:37"
type: manual
components:
  - build_orchestration
  - ac_driven_dev
summary: "When /plan-feature pauses at a gate and the agent relaying the saved pause record answers in prose or garbles its JSON, the run now retries the read and, if it still cannot read it, says so instead of claiming nothing was waiting or that the record was never written."
description: "Each pause-record read in plan-feature.js was a single agent dispatch, and an unparseable reply was treated as 'record absent' (nothing_to_resume) or 'not verified' (pause_persist_failed). On 2026-10-09 this dropped a real approval and reported a correctly saved record as unwritten. A new readPauseRecordWithRetry helper makes up to 3 attempts, labels each attempt separately, uses a stricter prompt on retries, and only accepts a reply with a boolean exists field. It is used for the paused-gate lookup, the resume read, the persist verification and the clear verification. A new terminal status, pause_record_unreadable, is reported when all attempts fail, and the five duplicated caller status lists are collapsed into one TERMINAL_GATE_STATUSES list. The shared parseAgentJson helper (identical copies in plan-feature.js, finalize-feature.js, build-epic.js and build-ticket.js) no longer returns a nested child object when the outer object is malformed or unbalanced: it resumes past a balanced segment that fails to parse and stops on a segment that never balances. Covered by the new test_acd_2100c_3_ii.py (including the real recorded malformed reply) and an update to test_acd_2100c_1.py; AC ACD-2100c-3-ii was added and ACD-2100c-3 updated."
commits:
  - e24e3601f
breaking: false
---

## Entry
