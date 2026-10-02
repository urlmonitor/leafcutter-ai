---
title: "Kernel: free-text human answers are interpreted by an LLM host operation, never only recorded"
status: todo
components:
  - decision_kernel
created: 2026-10-02
depends_on:
  - TICKET-20261002-KernelAnswerAppliedOnce.md
  - TICKET-20261002-KernelChoiceWithCondition.md
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: true
change_target: code
risk_surface: contract_boundary
tags:
  - decision-kernel
  - host-operation
last_updated: 2026-10-02
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Kernel: free-text human answers are interpreted by an LLM host operation, never only recorded

## Actor / Goal
In order that what a human writes in their own words changes the decision (a choice, a condition, a missing fact, a new option), we need free text interpreted by an LLM into typed, verified effects instead of being "only recorded".

## Context
- **Live reproduction (2026-10-02, run `run-1dec9568f85745e4`):** free text at an escalation was appended to `cont.human_inputs` (approvals.py:145-146) and did nothing else. At approval, free text is a dead end ("the proposals stay unapproved", approvals.py:111-115), and the question wording itself says "free text is only recorded" (requests.py:183-185).
- ADR-053 §1 gives interpretation to the LLM; Jev may not invent options, criteria or questions. ADR-060: the human stays the approver.
- Design blueprint 2026-10-02 (architect analysis): a new host operation `host.interpret_answer` on the pattern of `host.formulate_question` / `host.generate_options` (kernel/capabilities/host/). It is dispatched by the decision as a SUPPORTING child.

## Scope (no acceptance criteria by user decision): increment 1b
- New schemas `leafcutter.answer_interpretation_request.v1` and `leafcutter.answer_interpretation.v1`. The output carries: `chosen_option_id`, statements (condition / constraint / fact / preference, each with a verbatim `quote`), evidence needs (each with a `quote`), and `unclear` + `clarifying_question`. It has no confidence and no approval fields.
- `InterpretAnswer.convert_payload`:
  - forces an explicit `choice_id`;
  - drops any item whose quote is not a substring of the answer;
  - drops unknown option ids;
  - caps counts;
  - total conversion, never raises.
- Effects:
  - conditions and constraints reach Jev's constraints;
  - evidence needs go to `cont.gaps` and a research round;
  - an *inferred* choice is shown back for the human's confirmation before it applies;
  - unclear leads to a re-ask that quotes the prior answer.
- Bounded attempts (`decision.max_interpretations`, `decision.confirm_inferred_choice`, `host.interpret_answers` in config). Interpreter failure falls back to the verbatim record plus an explicit limitation.
- Covers design-choice and escalation questions first. Approval subsets, added options and edited criteria are increment 2 (follow-up ticket).
- New registry descriptor in `config/capability_registry.json`. ADR: dispatch `adr-author` directly with a pinned number.
- Tests:
  - host op unit tests (quote check, forced choice, dropped ids);
  - decision flow tests (interpret child emitted, conditions applied, inferred choice gives a confirm question, unclear gives a re-ask with a different payload);
  - integration replay of the 2026-10-02 scenario ending `completed` with a human approver.

## Comments
