---
title: "Decision kernel: tests for the 12 partly-tested ACs and DK-600b-2-ii, so each can be marked done"
status: done
components:
  - decision_kernel
created: 2026-10-02
depends_on: []
priority: medium
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - acceptance-criteria
  - tests
last_updated: 2026-10-06
agents:
  python-coder: signed_off
  test-writer: not_needed
  commit: not_needed
---

# Decision kernel: tests for the 12 partly-tested ACs and DK-600b-2-ii, so each can be marked done

## Actor / Goal
In order for the decision-kernel ACs that are built but not fully proven to reach `done` with real evidence, we need the tests the it-po verification pass found missing.

## Context
- **Source:** the it-po `gaps` in each AC's `amended_by` entry, ticket `TICKET-20261002-DecisionLifecycleACs`. These ACs are `in_progress`; the code exists, the proof is incomplete.
- **Rule:** each new test carries `# covers: <AC id>`. Once an AC's tests pass, mark it through `scripts/ac_store/mark_ac_done.py --test-root tests`, with `covered_by` set to the test pointers.
- **No kernel code changes** in this ticket. A test that finds a real defect gets its own ticket.

## Scope (no ACs, by user decision)
One test (or small group) per AC:
- **DK-600b-1-i** (only what you approved, edited or added goes on): one answer that applies an option subset, a reworded criterion and an added option together, and asserts the declined option is absent from the research request. As built, `edited_criteria` replaces the whole set and `approved_criterion_ids` is ignored when it is present; the test pins that.
- **DK-600b-2-ii** (own words at the ranked choice lead to a new ranking; built, not tested): answer the ranked question with words; assert status waiting, a second `decision.assess` Jev call whose constraints hold the words, a new ranked question, nothing selected.
- **DK-600b-2-iii** (no answer or cancel leaves the decision unresolved): cancel at the ranked question, then assert the staged folder and `docs/decisions/` hold no record.
- **DK-600c-2-i** (builder refuses a non-human approver or missing approval time): assert which condition the message names, and that the bare `human` actor is refused through `build_decision_record`, not only `human_actor()`.
- **DK-600c-2** (the record holds the question, choice, evidence and provenance): assert `provenance.model_version`, `kernel_version` and `repository_revision`.
- **DK-600c-3** (staged in the run folder, repository untouched): assert `git status` is the same before and after the run.
- **DK-600c-4** (you are told where the record is staged and how to publish): assert the Claude Code `/leafcutter` skill text tells the host to show the command, not run it (only the Codex skill text is tested today).
- **DK-600d-1-i** (a staged record you keep is never found as precedent): stage a record, skip publish, and show a later run does not find it.
- **DK-600d-1** (publishing starts only when you ask): assert the Claude Code skill text (only the Codex text is tested). See also `TICKET-20261002-RunKernelHowToFreeTextReRank` for the wording contradiction.
- **DK-600d-2-ii** (an unknown component or roadmap phase stops with exit code 3): an unknown roadmap phase on publish; exit 3 through the CLI for an unknown filter on publish; the message names the value; the retry succeeds once fixed.
- **DK-600d-4** (a published record reaches main only through review): assert structurally that `kernel/memory/` imports no subprocess or git (no commit, push or merge), and test the lookup against a store produced by publish.
- **DK-600e-2** (earlier decisions are judged for fit): the exact 0.5 threshold, and an overridden threshold (tests pin only 0.49, 0.6, 0.8 and the defaults).
- **DK-600e-3-ii** (an applicable precedent below the reuse threshold is cited without a reuse question): the 0.79 boundary partner.

## Out of Scope
- `DK-600a-3` and `DK-600e-3-i`: they are partly built, not only untested (`TICKET-20261002-KernelSynthesisCitationCheck`, `TICKET-20261002-KernelSupersedePublishCorrect`).
- The documentation ACs.

## Sign-offs

- [x] python-coder — 2026-10-06 06:39

## Comments

### 2026-10-06 06:39 — python-coder (status: ok)
feedback-id: fb_2026-10-06_00b44d28
Wrote the missing tests for the DK-600 decision-lifecycle ACs against the real kernel rigs (nothing committed, no kernel code changed). Deviation: the dispatch asked python-coder to author the tests directly, so `test-writer` is `not_needed`; `commit` is `not_needed` because the user commits.
- **Tests written** (each carries `# covers: <id>`; the existing it-po cited tests were tagged too, comment-only):
  - b-1-i: test_decision_criteria_proposals::test_one_answer_applies_a_subset_a_reworded_criterion_and_an_added_option
  - b-2-ii: test_design_ending::test_a_words_answer_at_the_ranked_question_is_reassessed_and_ranked_again, ::test_a_words_answer_never_resolves_the_decision
  - b-2-iii: test_learning_loop_e2e::test_cancelling_at_the_ranked_question_stages_no_record
  - c-2-i: test_builder::test_the_refusal_names_the_failed_condition, ::test_a_named_human_and_the_bare_human_actor_are_both_built
  - c-2: test_decision_precedent::test_the_staged_record_names_model_kernel_and_repository_versions
  - c-3: test_learning_loop_e2e::test_a_staging_run_leaves_git_status_unchanged
  - c-4 and d-1: test_render_hosts (five tests: staged rule in both skills, publish named as the user's command, Claude Code allowed-tools, Codex rules file, Codex how-to)
  - d-1-i: test_publish_cli::test_a_staged_record_that_is_not_published_is_never_found, test_learning_loop_e2e::test_a_record_kept_staged_is_never_found_as_precedent
  - d-2-ii: test_publish_cli::test_an_unknown_filter_value_exits_3_names_it_and_the_fixed_record_publishes
  - d-4: test_publish_cli (git checkout unchanged but for record and index, kernel/memory imports no subprocess or git, lookup after publish)
  - e-2 and e-3-ii: test_precedent_units (0.5, overridden threshold, 0.79) and the new test_precedent_thresholds (executor level, max_precedents)
- **Marked done through `mark_ac_done.py --test-root tests` (16):** DK-600b-1-i, b-2-ii, b-2-iii, c-2-i, c-2, c-3, c-4, d-1-i, d-1, d-2-ii, d-4, e-3-ii and the composites b-1, b-2, d-2.
- **Held back, `in_progress`:** DK-600e-2. Thresholds, the exact 0.5 edge, an overridden threshold and the max_precedents bound are tested, but the criteria quote the literal Jev question "does this earlier decision apply here?" and the kernel asks "Does the previous decision in `precedents.<id>` apply to the current `question` in its context?". Needs the business-analyst to reword the criterion (as for DK-600d-1 and DK-600d-4), or a kernel change; no kernel code was touched here.
- **Behaviour checked, matched the criteria:** DK-600b-2-ii (the words are a Jev constraint, a second assessment runs, a new ranked question follows, nothing is selected). Docs still say otherwise: `docs/how-to/run-the-decision-kernel.md` calls a words answer "recorded only" (see TICKET-20261002-RunKernelHowToFreeTextReRank).
- **Baseline:** the 18 previously done ACs' cited tests were re-run after the merge with main (all green) and their `implemented_by` symbols re-resolved. The two failures in `tests/kernel` (`test_host_operations::test_every_host_capability_of_the_design_has_an_operation`, `test_retrieval_live_misses::test_the_design_folder_is_fully_considered_and_the_record_part_is_found`) are not cited by any DK-600 AC and come from main.
