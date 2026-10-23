---
title: "Known issues filed: a scan-timeout flake, a full-repo export in the consumer sweep, a not-applicable verdict that says verified, and PR #1324 mypy leftovers"
date: "2026-10-23"
time: "17:00"
type: manual
components:
  - build_orchestration
  - testing_quality
summary: "Four known issues from the TQ-500g-3 / TQ-500g-5 work. KI-BO-20261023-uxp-700d-3-i-scan-timeout-flake (medium): a UXP-700d-3-i test runs scan_ac_store.py --json over the whole AC store under a 30 s timeout and timed out on CI shard 7 on three unrelated PRs. KI-TQ-20261023-consumer-sweep-full-repo-export (low): the consumer-sweep base run exports the whole base commit on every check. KI-TQ-20261023-wvr-verified-true-on-not-applicable (low): the wrong-version verdict can read applicable false with verified true. KI-TQ-20261023-g3-mypy-followups (low): four annotation-only mypy errors in the consumer-sweep code."
description: "Docs only. One new file under docs/known-issues/build-orchestration/ (low index bucket, graded medium) and three under docs/known-issues/testing-quality/, with one register row in build-orchestration.md (open 74 to 75) and three in testing-quality.md (open 29 to 32). Sites at origin/main ae3a1591c: test_uxp_700d_3_i.py:180-189/:197-211, scan_ac_store.py:933-946; _cs_runs.py:121-140/:219-242/:259-265, consumer_sweep.py:208-220; _wvr_verdict.py:114-143, wrong_version_runner.py:280-296, check_build_epic_gate_verdicts.py:131-135; _cs_asserts.py:216, _cs_edits.py:173, _cs_runs.py:128/:135. CI runs 39753286415, 39929154081, 39942548263. Remediation directions recorded, not applied."
commits:
breaking: false
---

## Entry

Four more problems seen while building the wrong-version and consumer-sweep checks are now
recorded as known issues.

One test that counts example criteria runs a scan of every criterion in the store and gives it
30 seconds. On a busy CI machine that is not enough, and it failed three unrelated pull requests
in two days. The check that compares old and new test runs copies the whole repository to a
temporary folder every time, even when one test file changed. The wrong-version report can say a
result was verified when the runs did not apply, although nothing reads that field yet. And the
last change left four type-checker errors that need annotations only. Each entry names the
affected lines and the suggested fix; none of the fixes is applied yet.
