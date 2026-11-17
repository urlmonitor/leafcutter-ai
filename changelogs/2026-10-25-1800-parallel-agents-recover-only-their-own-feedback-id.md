---
title: Parallel agents recover only their own feedback id
date: "2026-10-25"
time: "18:00"
type: manual
components:
  - infrastructure
  - feedback_collector
summary: "The feedback id-recovery fallback is now safe when agents submit at the same time: each submission gets its own recovery file, and each agent writes its error stream to its own file."
description: "KI-FC-002, ACs INF-500d-3-i, -ii and -iii. submit_feedback.py names the recovery file feedback_id_<digits>.txt from time, process id and random digits, and creates it exclusively, so it never overwrites another submission's file. The name stays all digits, so the documented search pattern is unchanged. The signoff skill and the documentation-verifier, user-surface-smoker, live-surface-tester and ticket-supervisor instructions now send stderr to /tmp/feedback_err_<ticket_basename>_<agent>.txt (ticket-supervisor adds the event kind) instead of one shared file. Reading the id from standard output is unchanged. INF-500d-3-iv (record the failure marker, never a foreign id) is still open."
breaking: false
---

## Entry
