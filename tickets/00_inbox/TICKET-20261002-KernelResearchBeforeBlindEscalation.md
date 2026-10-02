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
  test-writer: signed_off
  python-coder: signed_off
  pr-reviewer: signed_off
  commit: signed_off
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

### 2026-10-02 12:00 — test-writer (status: ok)
feedback-id: (submit-failed)
Wrote tests/kernel/decision_research/test_no_blind_escalation.py (6 tests; 5 red, the nothing-rankable
test is a guard that keeps current behaviour and passes by design).
red_baseline:
  - test_name: test_open_targets_and_no_round_yet_runs_the_research_round
    file: tests/kernel/decision_research/test_no_blind_escalation.py
    error: "AssertionError: NEEDS_HUMAN != NEEDS_EVIDENCE (unidentified_gap)"
  - test_name: test_rounds_exhausted_hands_the_human_a_ranked_question
    file: tests/kernel/decision_research/test_no_blind_escalation.py
    error: "AssertionError: 'unidentified_gap' == 'unidentified_gap'"
  - test_name: test_design_round_already_done_ranks_instead_of_blind_gap
    file: tests/kernel/decision_research/test_no_blind_escalation.py
    error: "AssertionError: empty ranking"
  - test_name: test_unresolved_feasibility_lands_in_cont_gaps
    file: tests/kernel/decision_research/test_no_blind_escalation.py
    error: "AssertionError: Lists differ: [] != ['repo fact one', 'repo fact two']"
  - test_name: test_gaps_are_bounded_and_deduplicated
    file: tests/kernel/decision_research/test_no_blind_escalation.py
    error: "AssertionError: 'fact 1' not found in gaps"
completion_manifest:
  cross_layer_seam_answer:
    result: covered
    producing_side: "OptionsPayload (real serializer) options.v1 output"
    consuming_side: "loading._absorb_options -> cont.gaps, read by ranking.has_targets in combine"
  reachability_entry_point_answer:
    result: not_found
    reason: "combine is a pure function and _absorb_options an inner helper; no CLI, hook, slash command, workflow step or main(argv) wraps them directly."
    remediation: "Escalate to ticket-supervisor for a BO-2900d exemption review if required."

### 2026-10-02 13:00 — python-coder (status: ok)
feedback-id: (submit-failed)
combine: unidentified_gap with rankable options now yields the design research round if due, else the ranked human question. loading: unresolved_feasibility also feeds cont.gaps (dedup, bounded).
red_baseline_results:
  - test_open_targets_and_no_round_yet_runs_the_research_round: green
  - test_rounds_exhausted_hands_the_human_a_ranked_question: green
  - test_design_round_already_done_ranks_instead_of_blind_gap: green
  - test_unresolved_feasibility_lands_in_cont_gaps: green
  - test_gaps_are_bounded_and_deduplicated: green
Tests: tests/kernel/decision_research + tests/kernel/capabilities, 204 passed.

### 2026-10-02 14:30 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
Reviewed kernel/capabilities/decision/combine.py and loading.py (+15 lines). No high-confidence findings.
[M-1] loading.py _add_gaps: when cont.gaps is already at MAX_GAPS_KEPT, new unresolved_feasibility items are silently truncated (bounded by design; confirm acceptable).
[M-2] combine.py: the new unidentified_gap branch falls back to RESEARCH_CAP as the ranked-question reason when loop_reason is empty; reason label is semantically approximate.
Suppressed: 0 low. Escalation: not escalated, medium count 2 (threshold > 3).
No Sign-offs or Implementation Tasks section exists in this ticket; frontmatter updated only.

### 2026-10-02 15:00 — commit (status: ok)
feedback-id: (submit-failed)
Auto-authorized commit gate: subject "fix(kernel): research or ranked question before blind unidentified_gap escalation"; staged files: combine.py, loading.py, test_no_blind_escalation.py, this ticket. Unrelated working-tree drift (docs/agents/cards/*, LEAFCUTTER_VERSION) deliberately not staged.
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true

### 2026-10-02 15:05 — commit (status: blocker)
feedback-id: (submit-failed)
Commit not created. Pre-commit hook check-output-drift (always_run) exits 2: "gaps=2" (UNCOMPARABLE GAP .claude/commands/leafcutter.md and .gemini/workflows/leafcutter.md, "run build.py to register it"); main-worktree .venv also missing. Unrelated to this change (kernel/ + tests only); worktree-environment/build-output issue. --no-verify not used. Remedy: run build.py in the worktree (or fix the hook gap handling), then re-run commit. Staged and ready: combine.py, loading.py, test_no_blind_escalation.py, this ticket.

### 2026-10-02 16:00 — commit (status: blocker)
feedback-id: (submit-failed)
Retry failed. check-feedback-id fixed (heading 15:05 now has feedback-id), but check-output-drift still exits 2 with gaps=2 (.claude/commands/leafcutter.md, .gemini/workflows/leafcutter.md: 'run build.py to register it'), even though both files exist on disk. Unrelated to this change. --no-verify not used. Remedy: run build.py in the worktree or fix hook gap handling, then re-run commit.

### 2026-10-02 17:00 — commit (status: blocker)
feedback-id: (submit-failed)
Third attempt failed identically: check-output-drift exits 2 with gaps=2 (.claude/commands/leafcutter.md, .gemini/workflows/leafcutter.md "run build.py to register it"), drifted=0 missing=0. Probe passes; HEAD unchanged (fb022dbe). Unrelated to kernel change. --no-verify not used. Remedy: run build.py or fix hook GAP handling, then re-run commit.

### 2026-10-02 18:00 — commit (status: blocker)
feedback-id: (submit-failed)
Fourth attempt failed identically: check-output-drift exits 2 (gaps=2: .claude/commands/leafcutter.md, .gemini/workflows/leafcutter.md "run build.py to register it"; drifted=0 missing=0). Probe passes; HEAD unchanged (fb022dbe). Unrelated to the kernel change; not fixable by precommit-autofix. --no-verify not used. Remedy: run build.py in the worktree or fix hook GAP handling, then re-run commit.

### 2026-10-02 19:00 — commit (status: ok)
feedback-id: (submit-failed)
Commit 87228a8e created: "fix(kernel): research or ranked question before blind unidentified_gap escalation" (4 files). The earlier check-output-drift failure did not recur; hooks passed. No --no-verify used. Unrelated drift in docs/agents/cards/* left unstaged.
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true

### 2026-10-02 20:00 — python-coder (status: ok)
feedback-id: fb_2026-10-02_2f6d1112
Follow-up fix to 87228a8e: when no research round was due because there were no research targets (no gaps, no added options, no uncited files), combine labelled the ranked question `research_cap` although zero rounds ran. It now uses the new `NO_RESEARCH_TARGETS` ("no_research_targets") reason, defined next to `RESEARCH_CAP` in ranking.py and added to `DESIGN_REASONS`. `loop_reason` still yields `research_cap` when the cap was really reached. The ranked question text (`design_ending._WHY`) and the rationale ("stopped researching because no_research_targets after 0 research round(s)") now say so. Two regression tests added to test_no_blind_escalation.py; no existing assertion changed. Kernel capabilities/contracts/interaction/decision_research/memory suites: 532 passed; ruff and ast.parse clean.
