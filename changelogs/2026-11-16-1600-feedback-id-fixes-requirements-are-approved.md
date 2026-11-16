---
title: "Feedback-id fixes: requirements are approved"
date: "2026-11-16"
time: "16:00"
type: manual
components:
  - commit_guardian
  - ac_store
  - feedback_collector
summary: "Three requirement sets that make feedback ids trustworthy again are approved at high priority: reasoned failure markers (INF-500d-3), copyable comment examples that pass the commit check (BO-2000g), and a feedback-id check that no commit message can switch off (GE-123e)."
description: "INF-500d-3 is enriched: five failure-reason identifiers, a vocabulary file, a stderr contract and a test design. Two new children, INF-500d-3-v and INF-500d-3-vi, carry the reasoned marker into the remaining agent instructions. New L1 BO-2000g (8 children) requires every Comments example in agent templates and skills to open with a valid feedback-id line, adds one documented value for entries that sign nothing off, and adds a template lint plus a proof against the real commit check. New L1 GE-123e (7 children) removes the [NO-FEEDBACK-CHECK] bypass, which read the previous commit's message. Its refusal names the submission script, and concluding a merge, revert or cherry-pick is not blocked by sign-offs carried in unchanged. GE-123 is reworded to cover any check, not only security checks. All 20 records are approved at high priority. Three known issues are filed in the commit-guardian register."
breaking: false
---

## Entry
