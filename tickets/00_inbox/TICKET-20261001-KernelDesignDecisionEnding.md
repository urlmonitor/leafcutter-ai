---
title: "Kernel V0.1 A: end design decisions with a ranked human choice instead of looping on research"
status: in_progress
components:
  - decision_kernel
created: 2026-10-01
depends_on: []
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - decision
  - jev
last_updated: 2026-10-01
agents:
  commit: needed
---

# Kernel V0.1 A: end design decisions with a ranked human choice instead of looping on research

## Actor / Goal
In order to get a usable answer to a design question, we need a decision whose criteria are
properties of the proposed options to end with a ranked, human-answerable question instead of
researching forever.

## Context
Live run `run-5d246775f5e54f11` (goal: "Decide how Leafcutter should file decision records as
JSON or YAML files under docs/ ...") never converged. The user approved 4 options and 6
criteria. Jev assessed twice: no criterion was ever sufficient (0.55 to 0.67) and no option
passed every required criterion at 0.8. The scores barely moved between assessments although
6 evidence items were added. The decision looped assess, research, synthesis, research ... and
needed 18 Jev calls and 4 host operations after approval without reaching a human or a ranked
result. Evidence: session scratchpad `explore/runs5/`, `r5_state2.txt`, `r5_resume3.json` to
`r5_resume5.json`, Langfuse trace 954274b26bf886b3d7658e0345453cbb.

Root cause: criteria such as "readable by the existing knowledge-map parser", "ids enforced at
commit" and "small reviewable diffs" are properties of the proposed designs. Retrieval cannot
make them sufficient. ADR-053 gives preference and authority to a human; a design decision
needs a "rank and hand to a human" ending.

Governing text: Rev 3 spec section 9.4 (resolved gate) and 10.1; ADR-053; the decision-kernel
design part 4 ("As built" notes).

## Scope (no acceptance criteria by user decision)
- Criterion kind: `evidence_answerable` versus `design_judgement`, classified by one bounded
  Jev question per criterion inside the existing assessment batch (no extra Jev call), recorded
  on the criterion (additive field with a default).
- Design-decision ending: when the required criteria are design judgements, when two
  assessments after new evidence score within a configured epsilon, or when a configured cap on
  research rounds is reached, stop researching, rank the options deterministically and ask the
  human to choose among the ranked options; on the choice resolve with `approved` and the
  human as approver. The ranking is evidence, not authority. Evidence-answerable decisions are
  unchanged.
- `option_context` on `ResearchRequestPayload` (`OptionContext`), populated by the decision when
  it requests research after options exist; not consumed yet (Wave 2).
- Config keys with defaults, regenerated schemas, tests (offline reproduction of the live loop
  and one run through the real graph and service).

Out of scope: retrieval, research, providers, observability and scheduler.
