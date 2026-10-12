---
title: "Plan: shrink-only ratchet for the Python complexity check (GE-131) — planned work only, no code changes"
date: "2026-10-09"
time: "13:52"
type: manual
components: 
  - commit_guardian
  - ac_store
summary: "Planned, not built: this adds only the approved acceptance-criteria plan for switching on the Python code-complexity check without blocking existing files, and changes no code or behaviour."
description: "PLANNED WORK ONLY. No code changes and no behaviour changes in this PR; it adds and approves the GE-131 acceptance-criteria records (5 YAML files under docs/acceptance-criteria/guardrail-engine/GE-131-functions-stay-followable/) and nothing else. Why: check_complexity.py exists but has never run on a commit, because 109 functions in 90 of 2,221 tracked .py files (measured at 7c9cc469a) are already over its limit of 15, so switching it on as-is would refuse any commit touching one of them. The plan (GE-131a-1, -2, -3) is a shrink-only ratchet: a staged function may stay at or below the greater of 15 and its own highest previous score across the parent commits; a new function is held to 15; a file that cannot be parsed or read is never passed as clean. The check is then registered in the hook list and shown refusing through a real commit (a function grown from 30 to 31, and a new function scoring 16), and the commit-guardian README and complexity-reduction skill text are corrected to state the rule. Scope: the tree was deliberately cut from an earlier 13-record draft (commit 1ef5f8db0) to 5 records and 12 specified tests after an independent review. It was approved by BrainCandy on 2026-10-09 (readiness: approved on all five records); the second commit also folds an assertion of the stated refusal reason (new / crossed) into the existing test test_new_or_crossing_function_is_held_to_limit, so the test count stays at 12. Deferred follow-ups named in GE-131a notes: a renamed or moved function keeping its previous score, a nothing-to-examine message when no Python file is staged, richer refusal text, distinguishing an unreadable previous version from an absent one, and property getter/setter pairing. All records remain work_status: todo."
commits: 
  - 51ebe053
  - 92257a5e
breaking: false
---

## Entry
