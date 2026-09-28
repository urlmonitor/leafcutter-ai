---
title: "A guard's refusal is recorded from what actually happened, not from what it declares"
date: "2026-09-25"
time: "14:20"
type: ticket_completion
components: 
  - commit_guardian
  - precommit_hooks
summary: "A new runner puts each commit check's declared known-bad input, and an input it must accept, through the entry point the protected surface really uses, and records a refusal only when the check rejected the bad input and accepted the good one. A check that can never refuse, refuses everything, or is only ever exercised from inside is no longer counted as working."
description: "GE-120f-1 adds check_negative_control_liveness.py, which writes each check's negative_control.currently record (passing, failing, blocked or unverified) from observation alone. GE-120f-1-i makes the run state which entry point it actually invoked for every check and names a refusal obtained by reaching inside a check (demonstration=reach_inside) instead of counting it; a hook with no registered entry point is blocked. GE-120f-1-ii puts an acceptable input through the same entry point in the same run and records the result in a discrimination field: a check that refuses both inputs, or whose declared pair cannot discriminate, does not count as working and fails the run. No existing hook declares a known-bad input yet; enrolling them is GE-120f-4 and GE-120f-4-i. Documented at docs/reference/commit-guardian-negative-control-liveness.md and its companion -record.md."
breaking: false
ticket: "01_TICKET-20260914-GE-120f-1.md"
---

## Entry

Until now a commit check was counted as protection because it was registered, not because anyone had seen it refuse anything. check_negative_control_liveness.py changes that. For each check that declares a known-bad input, it puts that input through the entry point the protected surface really uses and writes the check's record from what happened: passing, failing, blocked, or unverified. Nothing in the record is copied from the declaration.

Two ways of passing that without protecting anything are closed as well. A refusal obtained by calling a check's deciding code directly, rather than through its registered entry point, is reported as reach_inside and does not count; the report states, for every check, which entry point was actually used. And a check must also accept an input it is meant to accept, put through the same entry point in the same run. A check that refuses both inputs is reported as refusing without discriminating (narrow it), one that refuses neither as rejection not observed (widen it), and one whose declared pair cannot tell them apart as a broken pair (fix the declaration). Each of these fails the run, and the sweep still examines every other check.

No existing hook declares a known-bad input yet, so today this mechanism examines only the hooks enrolled in it. Enrolling the existing hooks is the follow-on work in GE-120f-4 and GE-120f-4-i.
