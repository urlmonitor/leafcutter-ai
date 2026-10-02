---
title: "Kernel: a human answer is applied exactly once, and a re-ask is never byte-identical"
status: todo
components:
  - decision_kernel
created: 2026-10-02
depends_on: []
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
last_updated: 2026-10-02
files_touched:
  - kernel/capabilities/decision/loading.py
  - kernel/capabilities/decision/state.py
  - kernel/capabilities/decision/requests.py
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Kernel: a human answer is applied exactly once, and a re-ask is never byte-identical

## Actor / Goal
In order that a human answer always moves a decision forward instead of looping into the no-progress guard, we need each answer applied once, and every follow-up question distinguishable from one already answered.

## Context
- **Live reproduction:** run `run-1dec9568f85745e4` (2026-10-02). After a free-text answer to an escalation:
  - the decision re-emitted a byte-identical human request (the payload carries no revision, requests.py:140-152);
  - `request_dedup_key` (scheduler/guards.py:157-175) matched the already-answered child, so `plan_proposals` linked it (scheduler/merge.py:183-184);
  - the parent resumed with the same answer as a `current_wait` child (merge.py:146,159), and loading.py:158-162 applied it again, so `human_inputs` held the sentence twice (`result-inv-6270c1c4…`);
  - two passes with no new work item tripped `no_progress_limit` (nodes_integrate.py:135-137), and the run ended `partial`.
- Root-cause analysis 2026-10-02 (free-text design blueprint, increment 1a).

## Scope (no acceptance criteria by user decision)
- `DecisionContinuation` records the work-item ids of human answers already applied (`answers_applied`). `loading` skips an answer whose child id is in it.
- A re-asked question differs from the answered one: it quotes the prior answer or carries a revision, so its dedup key differs.
- Tests:
  - replaying an answered human child is a no-op;
  - `human_inputs` holds a free-text answer once;
  - a re-ask after an answer creates a new child rather than linking the answered one;
  - integration: the 2026-10-02 escalation plus a free-text answer no longer ends on the no_progress guard.

## Comments
