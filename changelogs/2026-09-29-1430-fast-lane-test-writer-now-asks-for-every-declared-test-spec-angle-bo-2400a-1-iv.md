---
title: "Fast-lane test-writer now asks for every declared test_spec angle (BO-2400a-1-iv)"
date: "2026-09-29"
time: "14:30"
type: manual
components: 
  - build_orchestration
summary: "Fixed the fast lane so it asks for a test covering every declared test scenario instead of just one happy-path check, closing a gap that let unreachable code ship with green tests."
description: "1 commit (e1b3b9a7) to templates/workflows-js/fast-lane-ship.js: the test-writer request now asks for one test per declared test_spec descriptor (honouring its angle) instead of a single generic failing test, and falls back to a criterion+reachability floor when no test_spec is declared (80% of coder-assigned ACs). New AC BO-2400a-1-iv under BO-2400a-1, work_status done. Added 4 behavioural tests in unit_tests/workflows/test_bo2400a_1_iv_test_writer_ask.py asserting on the actual workflow-engine dispatch (not source text); 3 of 4 mutation-proven red when fast-lane-ship.js is reverted. Full unit_tests/workflows/: 838 passed, 94 subtests passed; ruff and mypy clean. Does not change the red-baseline gate's one-red rule (BO-2400a-3-v), which stays deliberately loosened. This is a prompt-compliance fix, not an enforcement gate; a deterministic gate refusing missing per-descriptor tests is the natural successor but was deferred due to its blast radius on the existing partially-covered AC population."
commits: 
  - e1b3b9a7158227913f2ddc90cbf1e6b51f4858f4
breaking: false
---

## Entry
