---
title: "Known issue filed: the ACS-200g reachability test outgrows its 30 s timeout"
date: "2026-10-21"
time: "18:00"
type: manual
components:
  - testing_quality
summary: "KI-TQ-20261021 (high) records that test_acs200g_pr_scoped_ac_check runs the deployed check_ac_schema.py under a hard 30 s timeout while one staged record makes the hook index the whole AC store, so cold CI runners time out at random and fail the required pytest check."
description: "Docs only. New docs/known-issues/testing-quality/open-high-ki-tq-20261021-acs200g-hook-run-outgrows-its-30s-timeout.md and its register row. Evidence: 4 of the last 6 main CI runs failed in shard 3/8 on this test; cold index ~22 s vs 1.2 s warm; CI recorded 25 s (84% of budget). Remediation directions recorded, not applied: point HOOK_ROOT at a fixture store, or a store-scaled budget with an env override."
commits:
breaking: false
---

## Entry

A test that checks the AC schema hook keeps timing out on fresh CI runners, because the hook
indexes the whole requirement store before it checks the one record the test stages. That
randomly fails the required test run. It is now recorded as a known issue with the evidence
and two ways to fix it.
