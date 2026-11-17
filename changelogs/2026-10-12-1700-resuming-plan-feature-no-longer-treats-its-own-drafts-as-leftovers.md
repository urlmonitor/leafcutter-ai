---
title: "Resuming /plan-feature no longer treats its own drafts as leftovers from a crash"
date: "2026-10-12"
time: "17:00"
type: manual
components: 
  - ac_driven_dev
summary: "When a paused /plan-feature run is resumed with your answer, the drafts that run produced are no longer offered as orphans from a crashed session, so the run no longer pauses at the wrong gate and overwrites the decision it was waiting for."
description: "On resume, the partial-run recovery scan found the paused run's own uncommitted drafts and asked whether to commit, keep or discard them as leftovers. That new pause replaced the record of the gate the run was really waiting at, so the person's answer could never be applied. Now, only when the scan finds candidates and the answer is for a different gate, the workflow reads the run's own pause record and leaves out the AC ids that record lists. Drafts the record does not list are still offered as orphans. If the record cannot be read, the run stops with pause_record_unreadable instead of overwriting it. Runs that are not resuming, and resumes with no candidates, behave exactly as before. Covers ACD-2100c-3-iii."
breaking: false
---

## Entry
