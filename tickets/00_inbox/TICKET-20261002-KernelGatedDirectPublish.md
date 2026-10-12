---
title: "Kernel: publish approved decisions directly when the gates pass and the decision is not risky, through a PR flow copied from finalize-feature"
status: todo
components:
  - decision_kernel
created: 2026-10-02
depends_on: []
priority: medium
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: true
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - decision-store
  - publishing
last_updated: 2026-10-02
agents:
  python-coder: needed
  commit: needed
---

# Kernel: publish approved decisions directly when the gates pass and the decision is not risky, through a PR flow copied from finalize-feature

## Actor / Goal
In order to stop asking the user to publish every approved decision, we need approved decision records to be published directly when the important gates pass and the decision is not risky. Publishing goes through a new PR flow copied from the existing finalize-feature workflow. Anything risky still asks the user.

## Context
- **Decision:** `dec-acdfd972fcaca478` (run `run-8a31d2cf1ea84f42`, approved by the user 2026-10-02).
  - The user added and chose the option "publish directly when the important gates are met (tests run, worktree removed, etc.) and the decision is not risky, through a new PR flow copied from finalize-feature".
  - The kernel ranked it 4th of 4, because ADR-060 currently requires a person to publish and forbids a record from granting a permission.
- **The finalize-feature template:** `templates/workflows/finalize-feature.js`, the sole finalization path since the agent was removed (ADR-006 addendum). It already does:
  - a pre-merge test baseline;
  - opens the PR;
  - merges `origin/main`;
  - post-merge tests with triage;
  - merges only when green;
  - auto-tickets pre-existing failures;
  - closes tickets;
  - removes the worktree.
- **Known failure modes the new flow must handle:**
  - finalize sends git and `rm` steps to an agent that refuses shell (`docs/analysis/2026-09-25-worktree-failure-modes.md`, F1);
  - worktrees go stale within minutes (KI-BO-20260909);
  - unattended destructive git operations (KI-BO-20260921, an open blocker).

## Scope (no ACs, by user decision)
1. **ADR-060 amendment**, approved by the user. It must state:
   - the standing rule under which an approved record may be published without a per-decision answer;
   - the gates: tests ran green, `decisions validate` ok, the worktree is cleaned up, the branch is fresh against main, and the others to be decided;
   - what counts as risky and therefore always asks: superseding or correcting a record, changing an ADR or a policy, and the others to be decided.
2. **A publish-decision PR flow** derived from `finalize-feature.js`: branch off fresh main, `decisions publish`, validate, changelog, PR, wait for green, merge, and remove the worktree. Gate failures stop and ask; risky decisions ask.
3. **Skills:** the kernel's completed-run message tells the host whether the record qualifies for direct publishing. The skills follow the flow instead of always asking.

## Out of Scope
- Kernel writes during a run: the kernel stays read-only, and publishing happens after the run.

## Comments
