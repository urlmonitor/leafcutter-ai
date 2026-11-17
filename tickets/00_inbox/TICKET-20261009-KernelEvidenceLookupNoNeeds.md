---
title: "Kernel: an evidence lookup completes with no needs and an empty bundle"
status: in_progress
components:
  - decision_kernel
created: 2026-10-09
depends_on: []
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - research
  - regression
last_updated: 2026-10-09
agents:
  python-coder: signed_off
  commit: needed
---

# Kernel: an evidence lookup completes with no needs and an empty bundle

## Actor / Goal
In order for a lookup question to be answered from the repository, we need an evidence request to plan at least one research need from its goal. An empty plan must never end as a silent `completed`.

## Context
- **Observed on 2026-10-09.** Runs `run-124d6a01a27c442c` and `run-4b8b2b8cc8aa42d5`, on main at #1043, kernel code from both a branch checkout and the runtime checkout, with the goal "Find where this repository records why a piece of data is needed ...".
- **What the runs did:**
  - Both ended `completed` after 2 Jev calls, with an empty `evidence_bundle.v1`.
  - The bundle's only limitation was "no evidence needs were identified for the question".
  - The events were `run.started`, `context.recognized` ("unavailable: 0 meaning(s)"), `intent.assessed` (evidence), `routing.assessed` (selected), then `result.integrated` (completed). No research need was planned and no source was searched.
- **Earlier behaviour:** lookups like this (for example `run-0ee037dcf49c4a66`, 2026-10-02) planned needs and retrieved evidence. Something merged since then, likely around entity context or request splitting, changed this.

## Scope (no ACs, by user decision)
- **Reproduce** with the scripted rig: an evidence goal with unavailable entity context.
- **Fix the cause** so the goal itself always yields research needs (task context and existing patterns at least).
- **Make an empty plan visible:** a zero-need plan ends `partial` or `blocked`, with a limitation saying no research ran, never `completed`.
- **Tests:** a regression test for both behaviours.

## Out of Scope
- Changing entity recognition itself.

## Sign-offs

- [x] python-coder — 2026-10-09
- [ ] commit

## Comments

### 2026-10-09 12:00 — python-coder (status: ok)
feedback-id: fb_2026-10-09_c9aa5803
- **Cause:** a goal request plans needs only from Jev's `need.<category>` probabilities (supporting >= 0.5, required >= 0.8). When Jev rates every category below 0.5 the plan is empty and `bundle_result` reported it `completed`. Since 19e195bfa every research Jev batch also carries `entity_context` (here `unavailable`), `caller_context` and `registered_capabilities`, which is the only change to what Jev sees on that path; no merged code dropped needs.
- **Fix:** `research/baseline.py` plans supporting `task_context` and `existing_patterns` needs when Jev selects none (`planning._select_needs`); `results.bundle_result` ends a zero-need plan `partial` with "no research ran" in the limitations.
- **Tests:** `tests/kernel/intent/test_evidence_floor.py` (service rig with unavailable entity context and no Jev-selected category: red before, green after; zero-need bundle and executor partial).
- **Live smoke:** `python -m kernel run` with a scratch `paths.run_root` planned and ran research for three phrasings of the lookup goal (two reached evidence `completed`/`waiting_host`).
- feedback-id: fb_2026-10-09_0158bddc
