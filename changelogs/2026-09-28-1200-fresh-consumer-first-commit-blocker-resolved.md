---
title: "The 'fresh consumer cannot make its first commit' blocker is closed, with a CI guard so it stays closed"
date: "2026-09-28"
time: "12:00"
type: manual
components:
  - commit_guardian
  - build_pipeline
  - build_orchestration
summary: "KI-CG-20260831-0713 is resolved. A real consumer install built from main now passes the hook-trigger reachability check with zero unreachable conditions (exit 0, total=69 unreachable=0 exempt=6 nothing_to_match=1). The fix was BP-100k-4-iii, which landed 2026-09-24 and counts untracked stageable paths. The KI's 2026-09-07 measurement predated it. BP-900h-6-iii now also requires CI's consumer-install simulation to run the reachability guard on the adopter's first commit instead of withholding it, so a regression would turn CI red. Two new plan-feature KIs are filed, and the status-checker KIs are consolidated."
description: "RESOLUTION. KI-CG-20260831-0713 (blocker) said a freshly installed project could not make its first commit, because check-hook-trigger-reachability reported about 28 location-shaped conditions unreachable. It was re-measured on 2026-09-28. The package was vendored at leafcutter-ai/ as its own git repository, the consumer was a separate repository tracking nothing, and scripts/ci/check_consumer_install.py built the install ('CONSUMER INSTALL SIMULATION OK'). The deployed check_hook_trigger_reachability.py then returned exit 0: RESULT total=69 unreachable=0 exempt=6 nothing_to_match=1. An independent probe with the test_bp_100k_4_ii harness agreed (unreachable=0). BP-100k-4-iii had made untracked stageable paths count, and build.py deploys docs/product-truth/ and docs/roadmap.json into the consumer root, so the two gates the KI named (check-eval-staleness, check-surface-components-e3) are reachable. A layout-frame design (four L3 criteria under BP-100k-4) was drafted and then withdrawn, because the symptom it targeted no longer reproduces. BP-100k-4 stays done. GUARD. CI's consumer simulation (scripts/ci/_use_install_step.py, _isolate_precommit_registry_for_scratch_fixture) narrows the registry before the adopter's first commit and currently leaves the reachability guard out. BP-900h-6-iii (todo) gains the clause 'reachability guard is run, not withheld'. The guard must execute inside the first commit against the real registry, pass with unreachable=0, and a negative case with an impossible-location gate must fail the job and name the guard. Two test_spec entries and six constraints are added. The target file is at 399 of the 400-line ratchet, and Windows text decoding is a known gap. KNOWN ISSUES. New: KI-BO-20260928-pause-verify-rejects-an-enveloped-read-back. plan-feature's pause verify checks a top-level `exists` at plan-feature.js:1891, but worktree-agent nests the record under pause_record, so a successfully saved pause is reported as pause_persist_failed. New: KI-BO-20260928-stage-commit-leaves-the-edited-parent-unstaged. commitStageOutput stages only the files named in acs_written, so the BA's covered_by edit to the parent is left out and check-ac-parent-covered-by refuses the commit. The same KI records the done-parent case. Consolidated: the plan-feature/finalize status-checker occurrence moves from KI-BO-20260901-1620 into KI-BO-20260927-status-checker-runs-workflow-shell-commands. The commit-guardian and build-orchestration indexes are recounted from disk; 12 resolved entries had been listed as open."
commits:
breaking: false
---

## Entry

**Closed: "a fresh consumer project cannot make its first commit"** (KI-CG-20260831-0713).
A real consumer install built from `main` passes the hook-trigger reachability
check with zero unreachable conditions. BP-100k-4-iii fixed it on 2026-09-24. The
known issue's figure of 28 unreachable was measured before that fix.

**Guard.** CI's consumer simulation currently leaves the reachability check out
of the adopter's first commit, so a regression would go unnoticed. BP-900h-6-iii
now requires the check to run in that commit, pass, and be shown able to fail the
job.

**Known issues.** Two new plan-feature defects are filed:
- A successfully saved pause is reported as failed.
- The stage commit leaves the parent it edited unstaged.

The two overlapping status-checker entries are consolidated, and the index
totals are recounted from disk.
