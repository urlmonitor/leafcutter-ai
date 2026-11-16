---
title: "A masked AC failure is reported as pytest's own xfail"
date: "2026-11-16"
time: "17:08"
type: manual
components: 
  - testing_quality
summary: "When masking is on, the AC enforcement pytest plugin now reports a not-done AC's failing test as a pytest xfail: outcome skipped plus wasxfail. Before, it set the outcome to \"xfailed\", which pytest does not define. pytest printed F for the test, JUnit XML recorded it as a passing testcase, and the post-merge lane report recorded it as passed. CI and the gates run with AC_ENFORCE_STRICT=1, so their verdicts do not change."
description: "fix(ac-store), TQ-100b-1-iv. scripts/ac_store/pytest_ac_enforcement.py set report.outcome = \"xfailed\". TestReport.outcome only takes passed, failed and skipped, and mypy flagged the assignment. Measured on pytest 9.0.3 with masking on, before the change: the progress letter was F and the verbose word XFAILED. JUnit XML recorded a plain passing testcase and reported tests=\"3\" skipped=\"0\" for four testcases, the same under pytest-xdist -n 2. scripts/ci/_lane_report_plugin.py recorded the test as passed. The summary count (1 xfailed), the exit status and --maxfail were already right. The plugin now sets outcome \"skipped\" and keeps wasxfail, as _pytest/skipping.py does for a native xfail. After the change: letter x, word XFAIL, a JUnit skipped element of type pytest.xfail with tests=\"4\" skipped=\"1\" (also under xdist), --maxfail unchanged, and the lane report records skipped, the same as for a native xfail. The masked-failure line and summary are unchanged. Readers keep their verdicts: the shared pytest -v reader reads XFAIL, the fast lane red-baseline gate counts it red, the post-merge fix proof labels it xfailed (only a comment changed in scripts/ci/post_merge_fix_proof.py), and a strict run still reports FAILED. New L3 TQ-100b-1-iv is added under TQ-100b-1. It is covered by unit_tests/ac_store/test_tq_100b_1_iv_xfail_convention.py, which runs real pytest sessions in a temp project."
adrs: []
commits: []
breaking: false
---

## Entry
