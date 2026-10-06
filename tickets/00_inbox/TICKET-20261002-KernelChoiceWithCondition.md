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
  - kernel/capabilities/decision/design_ending.py
  - kernel/capabilities/decision/executor.py
  - kernel/capabilities/decision/state.py
agents:
  test-writer: signed_off
  python-coder: signed_off
  pr-reviewer: signed_off
  commit: signed_off
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
- (Added 2026-10-02 by the orchestrator, reachability) The Claude Code and Codex skill texts tell the host it may send {choice_id, free_text} when the user picks a choice and adds a condition, and free text is allowed.

## Implementation Tasks

### test-writer
- [x] tests/kernel/capabilities/test_choice_with_condition.py: an approval at awaiting_approval with {choice_id: "approve", free_text: CONDITION} lands the text in cont.conditions, the rationale and the staged record's task_context.constraints (approvals._apply_approval now keeps it).
- [x] Same file: an unusable choice keeps no condition at awaiting_human (tie) and at awaiting_design_choice (RankedGapCase): the text is in neither conditions nor human_inputs, the limitation "answer 'nope' is not a usable option" is recorded (the design-choice case used to keep the text as a condition).
- [x] Same file: a tie ruling's limitations contain "human ruling: human:ada chose [A] at a tie escalation" and not "ranked by the kernel"; the staged record's assessment.basis stays kernel_ranking (the basis enum is a pinned vocabulary, see comment) with an empty ranking.
- [x] tests/kernel/interaction/test_submissions.py: no change needed (decision approval and precedent questions have free_text_allowed false, so the pair is already rejected there); add one assertion only if no test covers that rejection.
- Fixtures: any dict with more than 5 keys or parametrize table with more than 3 rows goes to tests/fixtures/ via load_fixture() (docs/testing/README.md).

## Sign-offs
- [x] test-writer — 2026-10-02 14:32
- [x] python-coder — 2026-10-02 16:00
- [x] pr-reviewer — 2026-10-02 16:30
- [x] commit — 2026-10-02 17:00
- [ ] pull-request

## Comments

### 2026-10-02 14:32 — test-writer (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  tests_written: true
  red_baseline_verified: true
  cross_layer_seam_answer:
    result: covered
    producing_side: "HumanAnswerPayload / apply_human_answer (kernel.capabilities.decision.approvals) via DecisionExecutor"
    consuming_side: "Jev assess state constraints, decision rationale and kernel.memory.staging staged record task_context.constraints"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "DecisionExecutor.ainvoke resumed with a leafcutter.human_answer.v1 child (and submit_interaction in test_submissions.py)"
red_baseline:
  - test_name: test_choice_with_free_text_is_accepted_and_keeps_both
    file: tests/kernel/contracts/test_human_answer_condition.py
    error: "ValidationError: set exactly one of choice_id, free_text and a structured approval answer"
  - test_name: test_renders_the_choice_label_and_the_condition
    file: tests/kernel/contracts/test_human_answer_condition.py
    error: "AssertionError: 'Records and Jev' not found in 'Jev decides'"
  - test_name: test_a_choice_at_an_unidentified_gap_completes_with_the_human_as_approver
    file: tests/kernel/capabilities/test_choice_with_condition.py
    error: "AssertionError: ResultStatus.WAITING != ResultStatus.COMPLETED"
  - test_name: test_the_rationale_names_a_human_ruling_not_a_kernel_finding
    file: tests/kernel/capabilities/test_choice_with_condition.py
    error: "AssertionError: expected a value, got None"
  - test_name: test_jev_sees_the_condition_as_a_labelled_human_stated_constraint
    file: tests/kernel/capabilities/test_choice_with_condition.py
    error: "AssertionError: False is not true (condition present but not labelled human-stated)"
  - test_name: test_the_choice_stays_authoritative_and_the_condition_reaches_the_rationale
    file: tests/kernel/capabilities/test_choice_with_condition.py
    error: "PayloadValidationError: set exactly one of choice_id, free_text and a structured approval answer"
  - test_name: test_the_staged_record_carries_the_condition_in_its_constraints
    file: tests/kernel/capabilities/test_choice_with_condition.py
    error: "PayloadValidationError: set exactly one of choice_id, free_text and a structured approval answer"
  - test_name: test_a_design_choice_with_a_condition_resolves_and_records_it
    file: tests/kernel/capabilities/test_choice_with_condition.py
    error: "PayloadValidationError: set exactly one of choice_id, free_text and a structured approval answer"
  - test_name: test_accepts_a_choice_with_a_condition_where_free_text_is_allowed
    file: tests/kernel/interaction/test_submissions.py
    error: "SubmissionRejected schema_invalid"
  - test_name: test_rejects_semantic_invalid_for_a_condition_where_free_text_is_not_allowed
    file: tests/kernel/interaction/test_submissions.py
    error: "AssertionError: schema_invalid != semantic_invalid"
Wrote two new test files and rewrote the two-modes test in test_submissions.py (now choice+structured). Guard tests (single modes valid, non-pair mixes rejected, schema-matches-models, unusable choice does not resolve) pass today by design and must stay green; the schema-matches-models test goes red if the model changes without regenerating the committed schema.

### 2026-10-02 15:10 — python-coder (status: handoff)
feedback-id: (not-submitted)
Implementation done; all 10 red_baseline tests are green. Two pre-existing tests are now stale
(classification: test_drift), production is correct; test-writer must update them (assertion-only):
- tests/kernel/capabilities/test_decision_graph.py::TestConflict::test_human_ruling_on_conflict_lets_the_decision_resolve
  (line ~239) asserts the raw text in Jev constraints; the ticket requires the label, now
  "human-stated: ADR 2 supersedes ADR 1.". Assert the labelled form.
- tests/kernel/fixtures/invalid/leafcutter.human_answer.v1/invalid_basic.json is {choice_id, free_text},
  now valid by design. Replace with an invalid mix (e.g. choice_id + approved_option_ids).
Full run: tests/kernel 1516 passed, 2 failed (the two above). Sign-off boxes left open pending this.

### 2026-10-02 16:00 — python-coder (status: ok)
feedback-id: (not-submitted)
Stale tests (test_decision_graph conflict label, invalid_basic.json fixture) are already updated in the working tree. Re-run: test_decision_graph, test_choice_with_condition, tests/kernel/contracts, tests/kernel/interaction = 205 passed. All 10 red_baseline tests green.

### 2026-10-02 16:30 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
No high-confidence findings. Contract/schema regenerated and consistent with the model; pair accepted, other mixes rejected.
- [M-1] design_ending.py, executor.py, state.py are modified but not listed in the ticket's files_touched (needed for rationale, staging pass-through, `conditions` field); update files_touched.
- [M-2] design_ending.choice_rationale human_ruling branch does `next(...)` with no default; relies on design_choice_id always being a known option (guaranteed by the usable check in approvals.py, but fragile).
Suppressed: 0 low, 0 dropped. Escalation: not escalated, medium count 2 (threshold > 3).
Full tests/kernel run not completed within tool timeout; relied on python-coder's 205-pass targeted run.

### 2026-10-02 17:00 — commit (status: ok)
feedback-id: (not-submitted)
Committed 03c4b7bb (15 files, hooks passed, no bypass). Added design_ending.py, executor.py, state.py to files_touched per pr-reviewer M-1.
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true

### 2026-10-02 18:00 — python-coder (status: ok)
feedback-id: fb_2026-10-02_0f324846
Skill reachability: Claude Code and Codex SKILL.md now tell the host it may send {choice_id, free_text} (condition relayed verbatim) where free_text_allowed. Test added in tests/kernel/adapters/test_install_skill.py; tests/kernel/adapters 128 passed, ruff clean.

### 2026-10-02 19:00 — python-coder (status: ok)
feedback-id: fb_2026-10-02_48ad6bb8
Tests retargeted after merging #1001 (research-before-blind-escalation). An unidentified_gap with usable options now ends in the ranked design-choice question (phase awaiting_design_choice, pending_reason research_cap), not awaiting_human. Condition and ranked-choice tests (RankedGapCase) renamed and re-described honestly; the human-ruling coverage of approvals._apply_escalation moved to a tie (TieCase: awaiting_human, reason tie): choice completes with the human as approver, rationale says "Human ruling" not "Kernel ranking", choice plus condition is staged. Non-usable choice does not resolve in both. Only the test file changed; capabilities/contracts/interaction/decision_research/memory 552 passed, ruff clean.
Observed, not fixed: the ranked rationale reads "stopped researching because research_cap after 0 research round(s)". The count is true, but the reason is the fallback label: loop_reason was None (0 rounds < max_research_rounds 2) and design_round_due was false because has_targets() found nothing to aim at, so research was skipped, not capped.

### 2026-10-06 12:00 — python-coder (status: handoff)
feedback-id: fb_2026-10-06_c37f167b
handoff_target: test-writer
Condition and ruling honesty. (1) approvals._apply_approval keeps the text of {approve, free_text} in cont.conditions; decision approval and precedent questions allow no free text, so the pair is already rejected at submission there. (2) A condition is kept only when its choice is applied: _apply_design_choice no longer keeps text with an unusable choice (escalation already kept nothing); an unrecognised choice at approval keeps nothing. (3) design_resolved_result: for design_reason human_ruling the limitation is "human ruling: <approver> chose [<id>] at a <pending_reason> escalation". basis stays kernel_ranking: config/decision_record.schema.json is generated from kernel/memory/models.py but is duplicated as the hash-pinned trusted asset knowledge/native_types/decision_schema.json (tests/knowledge/test_native_decision.py pins its sha256), so a new value needs a reviewed re-pin; needs its own ticket. (4) Decision.design_reason comment lists human_ruling. Existing tests unchanged and green: capabilities/contracts/interaction/memory/decision_research 553 passed, 1 failed (test_host_operations has_an_operation, host.retrieval_needs, also fails on main). ruff clean, ast.parse ok. New tests not written (python-coder does not author tests): see Implementation Tasks / test-writer.

### 2026-10-06 13:00 — test-writer (status: ok)
feedback-id: fb_2026-10-06_96124dd2
Tests for the 2026-10-06 python-coder handoff added to tests/kernel/capabilities/test_choice_with_condition.py (19 tests, all green against the staged fix). New: TestApprovalWithACondition (approve + free text lands in cont.conditions and the staged record's constraints; blank text keeps none; unrecognised choice "maybe" records "unrecognised approval answer 'maybe'" and keeps no text), TestUnusableChoiceKeepsNothingAtATie and ...AtTheRankedQuestion (no conditions/human_inputs, limitation "answer 'nope' is not a usable option", not resolved), TestATieRulingDoesNotClaimAKernelRanking (limitation "human ruling: human:ada chose [A] at a tie escalation", no "ranked by the kernel"; staged basis stays kernel_ranking with empty ranking, commented as the basis-vocabulary follow-up), and TestConditionIsRecorded gained the exact "Condition stated by the human: <text>" rationale-suffix test. Note: the rationale suffix exists only on the ranked-choice ending (design_ending.choice_rationale); an approval resolution carries the approve condition in cont.conditions, Jev constraints and the staged record, not in the rationale, so the approval test asserts the record. Coupling: with HEAD's approvals.py and emit.py swapped in, 5 tests fail (approve condition x2, unrecognised approval, ranked unusable choice, tie limitation); restored byte-identical (cmp), 19 pass again. The tie-unusable, suffix and basis tests pass on HEAD too (behaviour already correct there; they pin it). Run: tests/kernel/capabilities+interaction+memory 428 passed, 1 failed (test_host_operations ...has_an_operation, host.retrieval_needs, fails on main). ruff clean.
red_baseline:
  - test_name: test_ac1_approve_with_free_text_keeps_the_text_as_a_condition
    file: tests/kernel/capabilities/test_choice_with_condition.py
    error: "AssertionError: [] != ['but Jev should be able to decide based on some criteria'] (against HEAD approvals.py)"
completion_manifest:
  tests_written: true
  red_baseline_verified: true
  cross_layer_seam_answer:
    result: covered
    producing_side: "approvals.apply_human_answer / emit.design_resolved_result via DecisionExecutor"
    consuming_side: "DecisionReportPayload limitations, decision rationale and the staged record's task_context.constraints"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "DecisionExecutor.ainvoke resumed with a leafcutter.human_answer.v1 child (run_decision rig)"

### 2026-10-06 14:00 — python-coder (status: handoff)
A condition stated at the proposals approval now ends every rationale written afterwards. New helper `condition_suffix(conditions)` in kernel/capabilities/decision/design_ending.py (one " Condition stated by the human: <text>" per condition, in order) is used by `choice_rationale` and by emit.py `resolved_result` (gate-resolved, basis resolved_gate) and `precedent_resolved_result` (approval may precede the precedent reuse). Run: tests/kernel/capabilities+interaction+memory 428 passed, 1 failed (test_host_operations ...has_an_operation, host.retrieval_needs, fails on main); ruff clean, ast.parse ok.
feedback-id: fb_2026-10-06_9c534176
handoff_target: test-writer
Test needed: an approve with free text at awaiting_approval that then resolves through the gate (resolved_result) gives a decision rationale text ending with " Condition stated by the human: <text>" (and the report payload's rationale likewise); two conditions give two suffixes in order; with no condition the rationale is unchanged. Optionally the same for the precedent-reuse path.

### 2026-10-06 14:30 — test-writer (status: ok)
feedback-id: fb_2026-10-06_da421b22
Condition-suffix tests for the 14:00 python-coder handoff, in tests/kernel/capabilities/test_choice_with_condition.py (24 tests, all green). TestApprovalWithACondition now asserts the gate rationale (and the report payload's rationale) ends with " Condition stated by the human: <text>", two conditions give two suffixes in order, and no condition leaves the gate rationale exactly "Option [A] Use sqlite satisfies the required criteria ['p1', 'p2'] according to evidence [...]."; new TestPrecedentReuseWithACondition covers the reuse rationale with and without a condition. The earlier condition is seeded on the waiting continuation_state (conditions) since one approval answer yields one condition. Coupling: with HEAD's design_ending.py and emit.py (the pre-fix staged state is not separately recoverable, the index already holds the fix) 5 fail: the three approval suffix tests, the precedent reuse suffix test, and the tie limitation test (that last one only because HEAD also lacks the earlier human-ruling note); restored byte-identical, 24 pass. Run: capabilities+interaction+memory 433 passed, 1 failed (test_host_operations ...has_an_operation, host.retrieval_needs, fails on main). ruff clean.
red_baseline:
  - test_name: test_the_reuse_rationale_ends_with_the_condition
    file: tests/kernel/capabilities/test_choice_with_condition.py
    error: "AssertionError: rationale lacks the suffix (against HEAD emit.py)"
completion_manifest:
  tests_written: true
  red_baseline_verified: true
  cross_layer_seam_answer:
    result: covered
    producing_side: "emit.resolved_result / precedent_resolved_result with design_ending.condition_suffix"
    consuming_side: "decision rationale and DecisionReportPayload rationale read back through DecisionExecutor"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "DecisionExecutor.ainvoke resumed with a leafcutter.human_answer.v1 child (run_decision rig)"
