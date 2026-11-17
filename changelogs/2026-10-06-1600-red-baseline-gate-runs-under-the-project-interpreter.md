---
title: Red-baseline gate runs under the project interpreter
date: '2026-10-06'
time: '16:00'
type: manual
components:
- build_orchestration
- testing_quality
summary: The build workflows now launch fast_lane.py with python instead of python3,
  and the red-baseline reader refuses with test_interpreter_unusable when pytest is
  not importable.
description: 'build-feature.js, build-ticket.js and fast-lane-ship.js start every
  fast_lane.py command with python (TQ-500f-3-ii). Every verify_red_baseline verdict
  now carries the interpreter that judged the tests, and the gate halt message names
  it. Linux users: python must resolve to the project interpreter (the one with pytest
  installed); the hooks already require this, so no new requirement, but a system
  with only python3 on PATH needs a python alias or an active venv.'
breaking: false
created: '2026-10-06'
last_updated: '2026-10-06'
status: active
---
## Entry
