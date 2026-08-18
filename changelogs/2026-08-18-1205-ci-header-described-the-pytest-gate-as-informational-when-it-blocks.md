---
title: "docs(ci): the CI header describes the gates the file actually defines"
date: "2026-08-18"
time: "12:05"
type: manual
components:
  - build_pipeline
summary: "ci.yml's header comment said the pytest job was informational-only, red on a fresh checkout, and awaiting promotion — while the job body twelve lines below declared it blocking with no continue-on-error. The body was right. The header also announced three jobs for a file that defines seven."
description: "The header comment block of .github/workflows/ci.yml had not been updated when BP-1200b promoted the pytest job to a blocking required check. It stated the job was 'INFORMATIONAL ONLY (continue-on-error) FOR NOW', that the suite was 'NOT yet green on a fresh checkout' with '~4 collection errors ... plus pre-existing failures', and that promotion to blocking remained a future deliverable 'tracked separately'. The job body at the same time carried the opposite statement: 'BLOCKING gate (BP-1200b) ... There is NO continue-on-error -- dropping it is the whole point of this job.' Anyone reading the header to decide how far to trust the test signal got the wrong answer, and the named collection errors invited someone to go hunting for failures that no longer exist. Measured on this branch before the edit: the full suite over tests/ and unit_tests/ under AC_ENFORCE_STRICT=1 with --continue-on-collection-errors reports 4360 passed, 8 skipped, 2 xfailed, 0 failed and 0 collection errors. The header now records the job as blocking, notes that it runs under AC_ENFORCE_STRICT=1 so enforcement xfail-masking is off, and keeps the ADR-016 rationale for why build.py runs before pytest, which is still accurate and still the reason the step exists. The job inventory is corrected from three to seven -- six blocking (lint, component-vocab, test, done-proof, ac-store-valid, changelog-presence) and one informational (typecheck) -- matching the required-status-checks list in the branch-protection ruleset. Comment-only change: no job, step, condition or environment value is touched, and the file still parses as YAML."
pr: null
commits: []
---

## Entry

`ci.yml` contradicted itself about its own most important gate.

The header said the pytest job was informational, that the suite was red on a
fresh checkout, and that making it blocking was still to come. Twelve lines
below, the job itself said it was blocking, with no `continue-on-error`, and
that dropping that flag "is the whole point of this job."

The body was the truth. The header was a snapshot of the world before BP-1200b
landed, left in place afterwards.

This matters more than a stale comment usually would, because of what the stale
version invited. It named four specific collection errors — for
`check_test_fixture_bloat`, `link_feedback`, `transform_decision_history` and
`known_failing_tests` — and attributed the suite's redness to them plus
"pre-existing failures". None of that is true now. Measured before this edit,
under `AC_ENFORCE_STRICT=1` so nothing is masked:

```
4360 passed, 8 skipped, 2 xfailed, 0 failed, 0 collection errors
```

A reader deciding how far to trust the test signal would have concluded the
gate was advisory and the suite unreliable, and might have gone looking for
four failures that are not there.

The header now states the job is blocking, records that it runs with
`AC_ENFORCE_STRICT=1` so AC-enforcement xfail-masking is off, and keeps the
ADR-016 explanation of why `build.py` runs before pytest — that part was always
correct and is still why the step exists.

The job count is also fixed: the file defines seven jobs, not the three the
header listed. Six block (`lint`, `component-vocab`, `test`, `done-proof`,
`ac-store-valid`, `changelog-presence`) and one is informational (`typecheck`),
which matches the required-status-checks list on the ruleset.

Comment-only. No job, step, condition, or environment value changed.
