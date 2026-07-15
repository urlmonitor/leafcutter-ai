---
title: "Finalize — Post-Merge Feature Finalization"
description: "The finalize-feature workflow: pre-merge test baseline capture, PR merge gating, push-before-merge sync, main sync, and ticket/epic closure."
flight_level: L3-Component
status: active
type: reference
created: 2026-07-10
last_updated: 2026-07-10
components:
  - finalize
---

# Finalize

## Overview

The Finalize component is the post-merge feature-finalization workflow. It captures a pre-merge test baseline on `main`, opens the PR if missing, merges `origin/main` into the worktree, runs post-merge tests with a triage baseline, verifies the local branch head is on origin before merging (push-before-merge sync check), merges the PR to `main` only when tests pass, syncs local `main`, closes tickets / archives the epic, and removes the worktree. All destructive steps are confirmation-gated and it HALTs on test regression before the PR merge.

## Responsibilities

- Capture the pre-merge test baseline and detect post-merge regressions via triage
- Guarantee the PR head contains every local commit before `gh pr merge` (push-before-merge sync check)
- Gate the merge to `main` on green required checks and confirmation
- Reconcile ticket lifecycle state (close tickets / archive epic) and clean up the worktree

## Entry Points

- `templates/workflows-js/finalize-feature.js` — the finalize-feature workflow script

## Integration

Invoked as the `/finalize-feature` workflow after a feature or epic PR is ready. It consumes the ticket lifecycle state produced by the build pipeline and hands off to the merged `main`. See the push-before-merge sync check (AC-1 of TICKET-20260708) for the merge-safety invariant.
