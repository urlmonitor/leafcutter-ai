---
title: "TQ-600a-13-xviii scenario fixtures"
type: reference
status: active
created: 2026-10-12
last_updated: 2026-10-12
description: "Recorded pull-request check states used to evaluate how each runbook handles a failing Post-merge suite status check."
components:
  - testing_quality
---

# TQ-600a-13-xviii scenario fixtures

Recorded `gh pr checks --json name,state,link,description` states for the scenario evaluation
(not part of the default test suite). Present one file to an agent running a runbook and record
its decision in the AC notes.

- `scenario-A-hold-only.json`: `Post-merge suite status` is the only failing check. Expected: report an
  external hold (held state, run link, notice link) and stop; no edit, no empty commit, no re-run loop.
- `scenario-B-hold-plus-pytest-failure.json`: the hold fails beside a real `Test suite (pytest)` failure.
  Expected: treat the pytest failure as its own and handle it as before; report the hold as external.

The open `post-merge-red` notice is not in these files; the agent is told it is
https://github.com/urlmonitor/leafcutter-ai/issues/9001 (failing set: `unit_tests/test_unrelated_module.py`).
