---
title: "Correct GE-127a-1's claim that its tests perform an ordinary commit"
date: "2026-09-08"
time: "15:25"
type: manual
components:
  - ac_store
  - commit_guardian
summary: "Corrected an acceptance-criteria record that had claimed its tests exercise an ordinary commit when every one of them actually invokes pre-commit by hand, so the one behavior that distinguishes the criterion from a mere registration check was going untested; no code, test, or behavior changed."
description: "Single-file change to docs/acceptance-criteria/guardrail-engine/GE-127-files-stay-workable/GE-127a-1.yaml. All five descriptors in unit_tests/commit_guardian/test_ge_127a_1.py invoke `pre-commit run check-file-size` — an extra command invoked by hand — never an ordinary `git commit`, so the criterion's own discriminating clause is unexercised; test_rationale had asserted the opposite since before the descriptors existed. notes now records the gap, why work_status stays done (the gate has refused ordinary commits in production since PR #728, most recently a 467-line file on 2026-09-07), and the route to closing it via the single-hook fixture GE-120g also needs."
commits:
  - eaf6e220b6cd9c014471cf4f17216e3a768e2a89
breaking: false
---

## Entry

### A record correcting what it claims about itself

Nothing shipped and nothing broke here. This commit touches one AC file and changes
what it says about its own test coverage, so a claim a reviewer would previously have
taken at face value now matches reality instead.

### The claim and the gap

GE-127a-1's criteria require the file-size refusal to fire when the author "performs
an ordinary commit — no extra command, no extra flag, and nothing invoked by hand."
Every one of the five descriptors in `unit_tests/commit_guardian/test_ge_127a_1.py`
instead invokes `pre-commit run check-file-size` directly — which is exactly an extra
command invoked by hand. So the single clause that separates this criterion from a
plain "the hook is registered" fact was never exercised: a build where the manifest
entry exists but the hook is never wired into the ordinary commit path would still
pass all five descriptors.

The record's own `test_rationale` said the opposite — it asserted "every descriptor
performs an ordinary `git commit` in a real temporary repository," a sentence written
before the descriptors existed and never reconciled against what they actually do. It
now states the requirement plainly and states, in the same place, that nothing shipped
meets it yet.

### Why `work_status: done` is still correct

The gate's behavior is genuinely live, not merely claimed: `check-file-size` refused an
ordinary commit of a 467-line file on 2026-09-07, and has run on every ordinary commit
in this repository since PR #728. Flipping `work_status` to `todo` would assert the
behavior is absent, which is false. What's missing is not the behavior — it's a test
that would notice if the behavior regressed.

### The route

Closing the gap needs a temporary repository whose `.pre-commit-config.yaml` carries
only the file-size hook, so an ordinary commit can be driven through it without other
hooks interfering. GE-120g needs the identical fixture for its own descriptors, which is
why this record is sequenced to follow it rather than duplicate the harness.
