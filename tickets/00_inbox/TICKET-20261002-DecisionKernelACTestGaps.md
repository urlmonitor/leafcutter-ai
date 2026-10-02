---
title: "Decision kernel: tests for the 12 partly-tested ACs and DK-300b-2-ii, so each can be marked done"
status: todo
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
last_updated: 2026-10-02
agents:
  test-writer: needed
  commit: needed
---

# Decision kernel: tests for the 12 partly-tested ACs and DK-300b-2-ii, so each can be marked done

## Actor / Goal
In order for the decision-kernel ACs that are built but not fully proven to reach `done` with real evidence, we need the tests the it-po verification pass found missing.

## Context
- **Source:** the it-po `gaps` in each AC's `amended_by` entry, ticket `TICKET-20261002-DecisionLifecycleACs`. These ACs are `in_progress`; the code exists, the proof is incomplete.
- **Rule:** each new test carries `# covers: <AC id>`. Once an AC's tests pass, mark it through `scripts/ac_store/mark_ac_done.py --test-root tests`, with `covered_by` set to the test pointers.
- **No kernel code changes** in this ticket. A test that finds a real defect gets its own ticket.

## Scope (no ACs, by user decision)
One test (or small group) per AC:
- **DK-300b-1-i** (only what you approved, edited or added goes on): one answer that applies an option subset, a reworded criterion and an added option together, and asserts the declined option is absent from the research request. As built, `edited_criteria` replaces the whole set and `approved_criterion_ids` is ignored when it is present; the test pins that.
- **DK-300b-2-ii** (own words at the ranked choice lead to a new ranking; built, not tested): answer the ranked question with words; assert status waiting, a second `decision.assess` Jev call whose constraints hold the words, a new ranked question, nothing selected.
- **DK-300b-2-iii** (no answer or cancel leaves the decision unresolved): cancel at the ranked question, then assert the staged folder and `docs/decisions/` hold no record.
- **DK-300c-2-i** (builder refuses a non-human approver or missing approval time): assert which condition the message names, and that the bare `human` actor is refused through `build_decision_record`, not only `human_actor()`.
- **DK-300c-2** (the record holds the question, choice, evidence and provenance): assert `provenance.model_version`, `kernel_version` and `repository_revision`.
- **DK-300c-3** (staged in the run folder, repository untouched): assert `git status` is the same before and after the run.
- **DK-300c-4** (you are told where the record is staged and how to publish): assert the Claude Code `/leafcutter` skill text tells the host to show the command, not run it (only the Codex skill text is tested today).
- **DK-300d-1-i** (a staged record you keep is never found as precedent): stage a record, skip publish, and show a later run does not find it.
- **DK-300d-1** (publishing starts only when you ask): assert the Claude Code skill text (only the Codex text is tested). See also `TICKET-20261002-RunKernelHowToFreeTextReRank` for the wording contradiction.
- **DK-300d-2-ii** (an unknown component or roadmap phase stops with exit code 3): an unknown roadmap phase on publish; exit 3 through the CLI for an unknown filter on publish; the message names the value; the retry succeeds once fixed.
- **DK-300d-4** (a published record reaches main only through review): assert structurally that `kernel/memory/` imports no subprocess or git (no commit, push or merge), and test the lookup against a store produced by publish.
- **DK-300e-2** (earlier decisions are judged for fit): the exact 0.5 threshold, and an overridden threshold (tests pin only 0.49, 0.6, 0.8 and the defaults).
- **DK-300e-3-ii** (an applicable precedent below the reuse threshold is cited without a reuse question): the 0.79 boundary partner.

## Out of Scope
- `DK-300a-3` and `DK-300e-3-i`: they are partly built, not only untested (`TICKET-20261002-KernelSynthesisCitationCheck`, `TICKET-20261002-KernelSupersedePublishCorrect`).
- The documentation ACs.

## Comments
