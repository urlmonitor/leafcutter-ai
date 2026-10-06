---
title: "Step 0 for building DK-400 and DK-500: ADR-067, test baseline, staged split rollout"
date: "2026-10-05"
time: "20:30"
type: manual
components:
  - decision_kernel
  - testing_quality
summary: "Prepared the build of the split-compound-requests and reusable-criteria AC trees: published the build-plan decision, wrote ADR-067, recorded main's failing tests and staged split.enabled off until the split gate and part runs land."
description: "Published decision dec-9925ebf1895222f4 (Step 0, then DK-400 in 3 and DK-500 in 4 dependency-checked epics, one PR each). ADR-067 pins host.decompose_goal, the goal_decomposition and decomposition schemas and the split-answer schema. The test baseline lists the 13 tests failing on main at 28b6168c with cause and owner. The DK-400 ACs now ship split.enabled false until epic E3. Tickets: the host-operation test table, goal_to_epic out-of-epic dependencies, and test-runner routing. No runtime code."
---

The build itself runs as seven epics after this PR merges. DK-400 E1 starts only after the host-operation test-table ticket is built, because DK-400c-1 extends that red test file.
