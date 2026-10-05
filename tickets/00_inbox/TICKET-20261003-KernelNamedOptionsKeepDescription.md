---
title: "Kernel: options named in the goal reach Jev with a description, not as bare titles"
status: todo
components:
  - decision_kernel
created: 2026-10-03
depends_on: []
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - options
  - assessment
last_updated: 2026-10-03
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Kernel: options named in the goal reach Jev with a description, not as bare titles

## Actor / Goal
In order that Jev judges the designs a caller names rather than their labels, we need an option
named in the goal to carry a reviewable description into assessment, so that the ranking is a
judgement of the options and not of their titles.

## Context
- **Live reproduction (2026-10-03, run `run-b5af8c7fae2248ba`, clustering method for DK-300b):**
  - The goal named five options. The host returned them with `named_in_goal: true`, each with a
    description and assumptions.
  - `kernel/capabilities/host/generate_options.py:79-90` keeps a verified named option as "just
    the caller's title (no host description or assumptions)".
  - `assess.py:99` sends `title. description` to Jev, so Jev scored five bare titles. The
    continuation shows `description: ""` for all five
    (`artifacts/result-inv-4602b7e562a14edb.json`).
- **Knock-on effect:** the targeted design research round needs file paths cited in option
  descriptions (`ranking.py:157-168`), so it had no target either.
- **Found by:** the manual "inconclusive ranking → LLM review" pass the user asked for
  (`TICKET-20261002-KernelInconclusiveRankingReview.md`).
- **Why the rule exists:** the host must not put words in the caller's mouth (ADR-053), which is
  why only the title is verified against the goal.

## Scope (no acceptance criteria by user decision)
- Keep the verified title as the caller's. Carry the host's description and assumptions as
  separately labelled host-reported text, e.g. `description_origin: host`, which the human sees
  at the approval gate and may edit.
- `assess` sends that text to Jev, marked as host-reported.
- When the goal itself contains text for the option, prefer the goal's span.
- Tests:
  - a named option reaches the Jev batch with its host description and origin label;
  - the design research round finds targets cited in such a description;
  - an unverified claim is still refused.

## Out of Scope
- Splitting multi-part goals (`TICKET-20261002-KernelDecomposeMultiPartGoal.md`).

## Comments

## Implementation Tasks
### test-writer
- [ ] The three tests above.
### python-coder
- [ ] Description origin field, conversion, assess payload, approval rendering.

## Risk & Safety
- Touches money? No.
- Touches data? No; run artifacts only.
- Reversibility? Fully reversible.
