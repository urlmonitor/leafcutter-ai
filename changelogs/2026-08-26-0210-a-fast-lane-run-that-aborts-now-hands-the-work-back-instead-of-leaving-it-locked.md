---
title: "A fast-lane run that aborts now hands the work back instead of leaving it locked"
date: "2026-08-26"
time: 0210
type: manual
components: 
  - build_orchestration
summary: "Every one of the nine paths where a fast-lane run halts after claiming its work now actually returns that work to todo, and a release that did not release is named in the halt beside the failure that caused it."
description: "Implements BO-2400f-10, BO-2400f-10-i and BO-2400f-10-ii, closing KI-BO-020. All nine release-on-failure dispatches asked status-checker to run the release command; that agent correctly refuses the role, so every aborted run since the release step was added stranded its acceptance criteria at in_progress, invisibly. The nine dispatches now route through one RELEASE_EXECUTOR_AGENT_TYPE constant so they cannot drift apart again, and the executor is an agent whose registry entry permits running the command. Two paths that previously shared the label release-on-review-fail are now distinguishable as release-on-review-no-verdict-fail and release-on-review-high-findings-fail. Per BO-2400f-10-ii the halt payload now reads the release reply and names any claim it failed to return, so a silent second failure can no longer hide behind the first. Proven by mutation: restoring the old agent type fails exactly two tests, one of which enumerates all nine halting scenarios by name, and the charter test reads permits_shell from agent_registry.json at test time rather than hardcoding an agent name, so a future swap to any other shell-less agent fails too."
breaking: false
---

## Entry

The fast lane has always had a release step: if a run halts after claiming its acceptance
criteria, it is supposed to flip them back from `in_progress` to `todo` so the next run can
pick them up. It never worked. All nine halting paths dispatched the release command to
`status-checker`, an agent whose charter is evidence-based ticket-state investigation, and it
declined the job every time — correctly, and in a well-formed reply the lane read as an
ordinary result. So every aborted run since the release step was added left its work locked,
and nothing said so.

This was found by running the lane rather than reading it. Two runs earlier the same day
halted at review; both left their criteria at `in_progress`, and the refusal was sitting in
the transcript in plain language: *"I am `status-checker`, and this request does not fit my
defined role or protocol."*

**The fix.** The nine dispatches now route through a single `RELEASE_EXECUTOR_AGENT_TYPE`
constant, so they can no longer drift apart one edit at a time — which is how they came to
share a defect in the first place. The executor is an agent whose registry entry permits
running the command. Two paths that both carried the label `release-on-review-fail` are now
`release-on-review-no-verdict-fail` and `release-on-review-high-findings-fail`, so a halt is
attributable to the branch that produced it.

`BO-2400f-10-ii` adds the part that keeps this honest: the halt payload now **reads the
release reply** and names any claim it failed to return. A release that quietly fails can no
longer hide behind the failure that triggered it — which is exactly how the original defect
stayed invisible.

**Proven by mutation, not by assertion.** Restoring the old agent type fails exactly two
tests, and one of them enumerates all nine halting scenarios by name. The charter test reads
`permits_shell` from `config/agent_registry.json` at test time instead of hardcoding an agent
name, so swapping in any other shell-less agent fails it too. The tests execute the workflow
under the E2 harness and inspect recorded dispatches; none of them greps the source.

One property worth recording, because it will recur: the run that produced this fix could not
benefit from it. It halted at review, tried to release, and was refused — because the lane
executing the run was the deployed copy, still carrying the bug. The fix only takes effect
once merged and redeployed.
