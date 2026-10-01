---
title: "Kernel V0: intake answer-kind classification and routing/clarification defects"
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
  - routing
  - intake
last_updated: 2026-10-01
agents:
  commit: needed
---

# Kernel V0: intake answer-kind classification and routing/clarification defects

## Actor / Goal
In order to get a useful answer (or a plain, honest decline) for any goal typed into
`/leafcutter`, we need the kernel to decide what kind of answer the goal needs before it
routes, so that out-of-domain and write requests are declined plainly, evidence and idea
requests reach the capabilities that can serve them, and clarification questions are
understandable.

## Context
Live exploratory runs of the Decision Kernel V0 (PR #973, default config, `TaskInput`
exactly as the `/leafcutter` skill sends it, so `requested_output_schema` defaulted to
`leafcutter.decision_report.v1`) exposed these defects:

1. "How is the weather today?" - Jev `__NONE__` 0.76; run blocked with an `unsupported` gap
   marked `build_opportunity: true`. An out-of-domain request lands in the build backlog.
2. "Where are tests saved in leafcutter?" - blocked `unsupported`: the default decision
   output schema leaves only `decision` eligible; `research` is excluded with
   `output_schema_mismatch`. The gap says "no registered capability can serve this request"
   while listing research and retrieval among the candidates, unranked, with no exclusion
   reasons.
3. "Come up with ideas to improve tracing in the Leafcutter kernel." - blocked `unsupported`
   for the same reason (`host.generate_options` only runs as a child of `decision`). The gap
   title reads "Capability for: come ideas improve kernel leafcutter tracing up" because
   `normalized_need` is a sorted bag of words. The report is a bare "blocked".
4. "Implement a critical acceptance criterion." - Jev `__NEEDS_CONTEXT__` 0.80 opened the
   fixed-template question "Which approach or capability should handle: ...?" (no choices,
   jargon in `why_research_cannot_settle`, a ".?" typo), after an `ambiguous` gap was already
   recorded. Implementing is write work and the MVP is read-only: it should be declined.
5. After the user answered that clarification ("Decide which acceptance criterion is most
   critical to implement next.") the run still ended `blocked` with
   "no_progress: clarification already requested without new information": the re-route kept
   the original goal, Jev answered `__NEEDS_CONTEXT__` again, and the guard treated an
   answered question like a repeated one. The envelope also showed the deduplicated
   `ambiguous` gap with the resume time as `first_seen` while the gap store kept the original.
6. The envelope reports `input_tokens` / `output_tokens` as null although every Jev
   generation carries usage.

Evidence (envelopes, gap records, trace urls) is kept by the orchestrator under the session
scratchpad `explore/` folder (`g1_run.json` ... `g4_run.json`, `g4_resume1.json`,
`gaps.json`, `gaps_after.json`).

Governing text: Rev 3 spec sections 6, 7.11 ("the root request must pick a supported output
contract"), 9, 11.6, 13.3/13.4 (a denied native action must not be reclassified as a missing
capability), 14; ADR-053 (deterministic first; Jev for bounded classification against known
candidates; LLM for generation; human for preference and authority).

## Scope (no acceptance criteria by user decision)
- Intake answer-kind classification through one bounded Jev choice question
  (`decision`, `evidence`, `ideas`, `change`, `out_of_domain`, plus `__NEEDS_CONTEXT__`) when
  the caller did not set `requested_output_schema`; thresholds from config.
- Roots that can use the resulting contracts (`research` for evidence, `host.generate_options`
  for ideas), with root completion and report rendering for evidence and options roots.
- Plain declines: `out_of_scope_write` (permission-type observation) and `out_of_domain`
  (not a build opportunity).
- Clarification questions in plain language with choices; re-classification on the goal as
  clarified; at most one follow-up; no `ambiguous` gap before the human answered.
- Gap record quality (exclusion reasons, ranking, readable title), consistent gap timestamps
  in the envelope, blocked/partial report text, envelope token totals, skill text.
- The `decision` capability's routing description also covers "decide what to do / which X
  to pick, including when options must first be generated".

## Out of Scope
- Write capabilities (the V0 kernel stays read-only).
- Pushing; the orchestrator merges this branch into the PR branch.

## Comments

## Sign-offs
- [ ] python-coder
- [ ] commit

## Implementation Tasks
### python-coder
- [ ] Tests first, then the changes listed under Scope.
- [ ] Update `docs/how-to/run-the-decision-kernel.md` and add an "As built (intake intent)"
  note to design parts 3 and 5.

## Risk & Safety
- Touches money? No.
- Touches data? No; run artifacts only.
- Reversibility? Fully reversible; explicit `requested_output_schema` keeps the old behaviour.
