---
title: "Changelog origin/main..fix/ac-schema-conformance-33 — build-orchestration proof-of-done remediation (PR #493)"
date: "2026-08-25"
time: "10:26"
type: manual
components: 
  - ac_store
  - build_orchestration
  - commit_guardian
  - ux_prototyping
summary: "Corrected the status of 29 build-orchestration acceptance criteria that had been marked done without real test proof, and documented a gap in how two of the guardrail tools decide what counts as a leaf requirement."
description: "Remaining contribution of fix/ac-schema-conformance-33 over origin/main: 46 acceptance-criteria YAML records (+967/-27) from a whole-store proof-of-done sweep over 235 build-orchestration ACs using verify_done_eligible() — 43 flagged ineligible, 25 given a real test_spec, 4 marked test_required: false with a written rationale, and an initial 39 status flips off done cut to 29 after adversarial review reverted 10 (the work existed and tests already passed). Adds known-issue KI-CG-012 (docs/known-issues/commit-guardian.md): the schema hooks _is_leaf_ac() (level-based) and the oracles verify_done_eligible() (covered_by-based) disagree about what counts as a leaf, observed on BO-1500a-1, BO-1500b-1, BO-1500c-1. Also bumps a two-line product-truth asof date. No code changes remain over main."
pr: 493
commits: 
  - 2d33c9f3
  - 5a1a5bee
---

## Entry
