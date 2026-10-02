---
title: "Kernel: a human choice can carry a condition, and a choice at an escalation resolves"
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
risk_surface: contract_boundary
tags:
  - decision-kernel
last_updated: 2026-10-02
files_touched:
  - kernel/contracts/payloads.py
  - kernel/schemas/leafcutter.human_answer.v1.schema.json
  - kernel/interaction/results.py
  - kernel/capabilities/decision/approvals.py
  - kernel/capabilities/decision/assess.py
  - kernel/memory/staging.py
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Kernel: a human choice can carry a condition, and a choice at an escalation resolves

## Actor / Goal
In order that "pick option X, but with condition Y" can be answered as said, we need a human answer to carry a choice plus free text. A choice made at an escalation must actually settle the decision.

## Context
- **Live reproduction (2026-10-02):** the owner answered "records + jev audience - however jev should be able to decide based on some criteria". `leafcutter.human_answer.v1` `_exactly_one` (kernel/contracts/payloads.py:269-281) rejects `choice_id` + `free_text`, so the answer had to go in as free text and the choice was lost.
- A `choice_id` at an `unidentified_gap` escalation only sets `preferred_option_id` (approvals.py:137-141); only tie/preference/conflict set a completion flag (148-151), and only `design_choice_id` resolves (executor.py:90-92).
- Root-cause analysis 2026-10-02 (free-text design blueprint, increment 1a).

## Scope (no acceptance criteria by user decision)
- `HumanAnswerPayload` accepts exactly one mode, or the pair {`choice_id`, `free_text`}; `choice_id` + structured and `free_text` + structured stay rejected. Existing payloads stay valid. The committed schema file is regenerated, and `tests/kernel/interaction/test_submissions.py:125-129` is rewritten.
- With a pair, the choice is authoritative and the text is recorded verbatim as a condition. It reaches Jev's constraints (assess.py:88-89, labelled human-stated), the rationale, and the staged record's `task_context.constraints`. `answer_text` renders both.
- A choice of a usable option at an escalation resolves with the human as approver. `design_reason` names it a human ruling, so the rationale is not misleading.
- Tests: the pair is accepted where free text is allowed and rejected where not; the condition lands in the constraints, rationale and staged record; a choice at unidentified_gap completes the decision.

## Comments
