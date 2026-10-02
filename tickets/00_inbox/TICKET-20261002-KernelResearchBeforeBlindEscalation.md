---
title: "Kernel: research or a ranked question before any blind unidentified_gap escalation"
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
  - kernel/capabilities/decision/combine.py
  - kernel/capabilities/decision/loading.py
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Kernel: research or a ranked question before any blind unidentified_gap escalation

## Actor / Goal
In order not to hand a human a blind "what is missing?" question while research targets are still open, we need the decision to run its targeted research round, or show a ranked question, before it ever escalates with `unidentified_gap`.

## Context
- **Live reproduction:** run `run-1dec9568f85745e4` (2026-10-02). Right after the human approved 5 options and 7 criteria, the decision escalated "The decision cannot be made and the missing knowledge is not identified" with no ranking. Zero research rounds had run, while `cont.gaps` held three synthesis gaps and the host had listed four repo facts as `unresolved_feasibility`.
- **Cause (root-cause analysis, 2026-10-02):** a hole in `combine.combine` (combine.py:203-229). `design_reason` (combine.py:218, ranking.py:142) needs every evidence-answerable required criterion sufficient (>= 0.8). One scored 0.72, so the branch fell to `classify_missing` (combine.py:91-110). That relies only on Jev naming a missing-knowledge category; Jev named none, so it returned `NEEDS_HUMAN/unidentified_gap` without consulting `design_round_due`, `has_targets`, the criterion kinds or the round count.
- `unresolved_feasibility` only goes to `work.limitations` (loading.py:87) and never becomes a research target.
- ADR-053 §8: a `needs_*` outcome must not collapse into a guess.

## Scope (no acceptance criteria by user decision)
- Where `classify_missing` would return `unidentified_gap`:
  - if `design_round_due(work, cfg)`, return the targeted design research round (`NEEDS_EVIDENCE`);
  - otherwise, if options and required criteria are rankable, hand the human the ranked question (`_hand_to_human`);
  - keep `unidentified_gap` only when nothing is rankable.
- `loading._absorb_options` also feeds `unresolved_feasibility` into `cont.gaps` (bounded by `MAX_GAPS_KEPT`).
- Tests (with the existing decision graph / design-round tests under `tests/kernel/capabilities/` and `tests/kernel/decision_research/`):
  - one answerable criterion at 0.72, Jev names no kind, gaps present, 0 rounds -> research round;
  - the same with rounds exhausted -> ranked human question, not the unidentified_gap text;
  - nothing rankable -> unidentified_gap unchanged;
  - `unresolved_feasibility` lands in `cont.gaps`.

## Comments
