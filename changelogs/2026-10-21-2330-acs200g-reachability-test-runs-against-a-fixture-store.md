---
title: "The AC-schema hook's reachability test runs against a small fixture repository, so it no longer times out on CI"
date: "2026-10-21"
time: "23:30"
type: manual
components:
  - ac_store
  - testing_quality
summary: "test_acs200g_pr_scoped_ac_check now runs the real deployed check_ac_schema.py against a temporary git repository holding three valid records and one malformed one, instead of the whole requirement store. Each hook run takes about half a second instead of ~22 s, so the test stays well inside its 30 s limit on a cold CI runner. Fixes KI-TQ-20261021."
description: "ACS-200g-3 (test-only, user decision 2026-10-21). The reachability check copies the deployed .leafcutter/scripts/commit_guardian and ac_store scripts plus the real schema into a git-initialised tmp fixture and sets HOOK_ROOT and cwd to it. New tests prove the hook read only the fixture (its index cache holds exactly the 4 fixture ids), that a valid record passes (control), that each cold run finishes under 10 s, and that the real working tree and the real index cache are untouched. Helpers in unit_tests/build_guards/_acs200g_fixture.py."
commits:
breaking: false
---

## Entry

One test was failing most CI runs because it made the schema check read the whole requirement
store just to look at one record. It now runs the same real check against a tiny repository
built for the test, so it finishes in under a second and no longer blocks pull requests.
