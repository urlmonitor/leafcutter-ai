---
title: "Kernel: a basis Jev rates insufficient gets research before ranking, even with caller evidence"
status: todo
components:
  - decision_kernel
created: 2026-10-03
depends_on:
  - TICKET-20261003-KernelNamedOptionsKeepDescription.md
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - research
  - assessment
last_updated: 2026-10-03
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Kernel: a basis Jev rates insufficient gets research before ranking, even with caller evidence

## Actor / Goal
In order that a ranking rests on evidence and not on Jev's priors, we need the decision to run a
research round when Jev rates the evidence insufficient for its criteria. Supplied evidence must
not suppress that round.

## Context
- **Live reproduction (2026-10-03, run `run-b5af8c7fae2248ba`):** Jev's sufficiency was 0.30-0.46
  for all 7 criteria, against a threshold of 0.8 (`config/kernel_config.default.json:60`), yet no
  research ran. Three gates let it through:
  1. The caller supplied 3 evidence items, so grounding was skipped (`basis.py:48-52`, "evidence
     the caller already supplied skips the research").
  2. Jev classified every criterion `design_judgement`, including one the host had proposed as
     `evidence_answerable`. With no answerable required criteria, `design_reason`
     (`ranking.py:139-148`) passes `all()` over an empty list and stops research.
  3. The design round had no targets, because named options lose their descriptions
     (`TICKET-20261003-KernelNamedOptionsKeepDescription.md`).
- **Related, same family:** `TICKET-20261001-KernelPrecedentSkipsGrounding.md` (precedent evidence
  skips grounding).

## Scope (no acceptance criteria by user decision)
- Supplied evidence skips grounding only when Jev's sufficiency for the required criteria meets
  the threshold. Otherwise one targeted research round runs, bounded by the existing round caps.
- `design_reason` does not end research in a decision that has run zero research rounds while
  every criterion's sufficiency is below threshold. At least one round runs first.
- The report states when the ranking rests on unresearched design judgement.
- Tests:
  - caller evidence plus low sufficiency gives one research round;
  - caller evidence plus high sufficiency skips it as today;
  - all criteria `design_judgement` with zero rounds and low sufficiency gives one round before
    the ranked question.

## Out of Scope
- The pass threshold itself (0.8).

## Comments

## Implementation Tasks
### test-writer
- [ ] The three tests above.
### python-coder
- [ ] Grounding gate, `design_reason` guard, report line.

## Risk & Safety
- Touches money? One extra research round in the affected cases, within existing caps.
- Touches data? No; run artifacts only.
- Reversibility? Fully reversible.
