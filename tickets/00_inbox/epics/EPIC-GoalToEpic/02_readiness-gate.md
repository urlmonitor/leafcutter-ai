---
title: "Readiness gate — report unapproved ACs and offer approval choices"
status: done
components:
  - ac-driven-dev
created: 2026-06-05
depends_on:
  - tickets/00_inbox/epics/EPIC-GoalToEpic/01_tree-traversal-ticket-generation.md
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
target_epic: EPIC-GoalToEpic
files_touched:
  - scripts/goal_to_epic.py
  - templates/agents/build-ac.md
  - unit_tests/ac_store/test_readiness_gate.py
agents:
  test-writer: signed_off
  python-coder: signed_off
  llm-expert: signed_off
  test-runner: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
ac_coverage: 0/3
source_ac: ACD-1200b
---

# 02: Readiness gate — report unapproved ACs and offer approval choices

## Actor / Goal

In order to prevent tickets from being generated for ACs that are not yet
approved, the system must surface unapproved ACs before any ticket generation
begins — and let the user choose to proceed with only the approved subset,
kick off IT PO v3 for bulk review, or cancel the entire epic generation.

## Context

After the tree traversal from ticket 01 produces the leaf set, `goal_to_epic.py`
reads the `readiness` field from each leaf AC YAML and classifies leaves into
`approved` vs `unapproved` groups. The prompt-and-branch logic is handled by the
`build-ac` agent (llm-expert authored; `goal_to_epic.py` emits structured output,
the agent interprets and routes).

The all-approved fast-path is a performance-of-UX detail: skip the prompt entirely
and print a confirmation before proceeding.

## AC References

- Implements ACD-1200b-1 (readiness report before generation; count + IDs of unapproved)
- Implements ACD-1200b-1-i (all-approved fast-path: no prompt, proceed immediately)
- Implements ACD-1200b-2 (user choice: yes / review-all / cancel; review-all dispatches IT PO v3)

## Agent Contracts

### python-coder

- [x] AC-1: Given the leaf set from ticket 01, the readiness check reads the `readiness` field from each AC YAML (read-only), classifies into `{approved: list[str], unapproved: list[dict{id, readiness}]}`, completes in <500ms for <=100 leaves, and returns the dict before any ticket generation begins. <!-- signed: python-coder -->
- [x] AC-2: Given all leaves have `readiness: approved`, no readiness report is displayed, no prompt is shown, and the system prints "All N leaf ACs are approved. Generating epic..." before proceeding directly to ticket generation. <!-- signed: python-coder -->

**Delivers to llm-expert (approval gate prompt):**
```json
{
  "approved": ["ACD-050a-1", "ACD-050a-2"],
  "unapproved": [
    {"id": "ACD-050a-2-i", "readiness": "draft"},
    {"id": "ACD-050b-1", "readiness": "reviewed"}
  ]
}
```

**Depends on ticket 01:** `list[str]` — leaf AC IDs with `readiness` fields readable from disk.

### llm-expert

- [x] AC-3: Given the readiness dict shows N unapproved ACs, the agent presents "Proceed with M approved ACs only? (yes / review-all / cancel)" and routes correctly: (a) "yes" → pass only approved IDs to ticket generation and print summary; (b) "review-all" → dispatch IT PO v3 for unapproved ACs, re-read readiness from disk after completion, re-evaluate the gate; (c) "cancel" → no epic generated, no tickets created, no AC files modified. <!-- signed: llm-expert -->

**Delivers to python-coder (ticket 01 generation step):**
```
list[str] — final approved AC IDs after gate decision (the included set for
            ticket generation, target_epic stamping, and dependency wiring)
```

**Depends on python-coder:** readiness classification dict as above.

## Acceptance Criteria

- [ ] AC-1: Readiness check classifies all leaf ACs into approved vs unapproved; runs <500ms for <=100 leaves; fires before any ticket generation
- [ ] AC-2: All-approved fast-path skips prompt entirely; prints confirmation; proceeds immediately
- [ ] AC-3: Three-choice prompt routes correctly: yes (approved-only gen), review-all (IT PO v3 dispatch + re-evaluation), cancel (no writes, no modifications)

## AC Coverage

| AC   | Test | Implementation | Validated |
|------|------|----------------|-----------|
| ACD-1200b-1   | test_readiness_gate.py:TestClassifyReadiness | classify_readiness() added to goal_to_epic.py; reads readiness field, classifies approved vs unapproved, read-only | |
| ACD-1200b-1-i | test_readiness_gate.py:TestFastPathOutput | print_fast_path_message() + all-approved branch in run() integrated | |
| ACD-1200b-2   | test_readiness_gate.py:TestThreeChoicePromptRouting | readiness_gate_prompt() + dispatch_it_po_v3() + re-read from disk in _route_answer() | |

## Test Requirements

```yaml
tests:
  - path: unit_tests/ac_store/test_readiness_gate.py
    covers: [ACD-1200b-1, ACD-1200b-1-i]
    type: unit
    rationale: "Readiness classification is pure dict logic; unit tests cover both partitioned and all-approved inputs"
  - path: unit_tests/ac_store/test_readiness_gate.py
    covers: [ACD-1200b-2]
    type: integration
    rationale: "The three-choice branch covers IT PO v3 dispatch; mock IT PO v3 to test re-evaluation loop"
```

## Implementation Tasks

- [ ] Add `classify_readiness(leaf_ids, store_root) -> dict` to `goal_to_epic.py`
      — reads `readiness` field from each leaf AC YAML, no writes
- [ ] Add all-approved fast-path: detect all-approved before prompting, print
      confirmation message, proceed
- [ ] Add readiness report output format: "N of M leaf ACs are approved. X ACs need approval: ..."
- [ ] Add three-choice prompt in `build-ac` agent template:
      "Proceed with M approved ACs only? (yes / review-all / cancel)"
- [ ] "yes" path: filter leaf list to approved IDs, pass to ticket generation step
- [ ] "review-all" path: dispatch IT PO v3 via Agent tool for unapproved AC IDs;
      after completion, re-read readiness from disk and re-evaluate gate
- [ ] "cancel" path: exit cleanly, no file writes
- [ ] "review-all" path: if IT PO v3 does not promote all ACs to approved, re-present
      the readiness report with updated counts (not an infinite loop — re-present once,
      then the user chooses again from the three options)
- [ ] Write unit + integration tests for all 3 ACs

## Risk & Safety

- Touches money? No.
- Touches data? Yes — "review-all" path causes IT PO v3 to mutate AC YAML files
  (readiness promotion). The "cancel" path guarantees zero writes. The
  classification step itself is read-only.
- Reversibility? High — readiness field changes are author-reversible.
- The re-read-from-disk requirement (ACD-1200b-2 it_requirement #4) prevents
  stale cache bugs where IT PO v3 promotes ACs but the gate still sees old values.

## Sign-offs

- [x] test-writer — 2026-06-05 13:00
- [x] python-coder — 2026-06-05 13:10
- [x] llm-expert — 2026-06-05 13:20
- [x] test-runner — 2026-06-05 13:30
- [x] pr-reviewer — 2026-06-05 13:40
- [x] commit — 2026-06-05 13:50
- [x] pull-request — 2026-06-05 14:00

## Comments

_(Append-only log — leave blank when authoring.)_

### 2026-06-05 13:00 — test-writer (status: ok)
feedback-id: fb_2026-06-05_4ca000c9
completion_manifest:
  tests_written: true
  tests_are_red: true
  ac_coverage_table_filled: true
  test_file_importable: true

## Test Writer — Completion Report

### Tests Written
| File | Directory | Framework | Status |
|---|---|---|---|
| test_readiness_gate.py | unit_tests/ac_store/ | pytest | written |

### Verification Run
- Command: `python3 -m pytest unit_tests/ac_store/test_readiness_gate.py -v`
- Result: red (1 collection error — ImportError: cannot import name 'classify_readiness' from 'goal_to_epic'; expected since implementation not yet written)

### Notes
All tests are failing with ImportError on `classify_readiness` — correct red state for TDD. Tests cover ACD-1200b-1 (classify_readiness dict structure, performance, read-only guarantee), ACD-1200b-1-i (all-approved fast-path, print_fast_path_message), and ACD-1200b-2 (three-choice prompt routing: yes, cancel, review-all paths including IT PO v3 dispatch mock and re-read from disk).

red_baseline:
  - test_name: test_ac1_classifies_mixed_leaf_set
    file: unit_tests/ac_store/test_readiness_gate.py
    error: "ImportError: cannot import name 'classify_readiness' from 'goal_to_epic'"
  - test_name: test_ac2_all_approved_returns_empty_unapproved
    file: unit_tests/ac_store/test_readiness_gate.py
    error: "ImportError: cannot import name 'classify_readiness' from 'goal_to_epic'"
  - test_name: test_ac3_yes_path_returns_only_approved_ids
    file: unit_tests/ac_store/test_readiness_gate.py
    error: "ImportError: cannot import name 'classify_readiness' from 'goal_to_epic'"
  - test_name: test_ac3_cancel_path_returns_no_ids
    file: unit_tests/ac_store/test_readiness_gate.py
    error: "ImportError: cannot import name 'classify_readiness' from 'goal_to_epic'"
  - test_name: test_fast_path_prints_confirmation_message
    file: unit_tests/ac_store/test_readiness_gate.py
    error: "ImportError: cannot import name 'classify_readiness' from 'goal_to_epic'"

### 2026-06-05 13:10 — python-coder (status: ok)
feedback-id: fb_2026-06-05_d86efbb5
completion_manifest:
  classify_readiness_implemented: true
  print_fast_path_message_implemented: true
  dispatch_it_po_v3_implemented: true
  readiness_gate_prompt_implemented: true
  gate_integrated_in_run: true
  all_tests_green: true
  ac_coverage_table_filled: true

Implemented classify_readiness() (reads readiness field, classifies into approved/unapproved dict, read-only, <500ms for 100 leaves), print_fast_path_message() (prints confirmation message), dispatch_it_po_v3() (invokes run_it_po_v3.py subprocess for review-all path), and readiness_gate_prompt() (three-choice prompt with yes/review-all/cancel routing including re-read from disk and single re-presentation if IT PO v3 doesn't promote all ACs). Gate integrated into run() before ticket generation begins. All 13 tests green.

### 2026-06-05 13:20 — llm-expert (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  readiness_gate_section_added_to_build_ac: true
  three_choice_prompt_documented: true
  all_approved_fast_path_documented: true
  review_all_re_read_from_disk_documented: true
  cancel_path_no_writes_documented: true
  decision_history_updated: true

Added Step 1b (Readiness Gate) to templates/agents/build-ac.md. The section documents the three-choice prompt (yes/review-all/cancel), the all-approved fast-path that skips the prompt, IT PO v3 dispatch followed by a mandatory re-read from disk, and the single re-presentation rule if IT PO v3 does not promote all ACs. The cancel path explicitly guarantees zero file writes. Decision history updated with rationale.

### 2026-06-05 13:30 — test-runner (status: ok)
feedback-id: fb_2026-06-05_0b5e8572
completion_manifest:
  full_suite_green: true
  new_readiness_gate_tests_green: true
  no_regressions: true

Ran full unit_tests/ac_store/ suite: 54 tests passed (0 failed, 0 errors). Includes 13 new readiness gate tests (TestClassifyReadiness: 6, TestFastPathOutput: 1, TestThreeChoicePromptRouting: 6) and 41 pre-existing tests from tickets 01 and tree traversal. Suite completed in 1.32s.

### 2026-06-05 13:40 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-05_542655f0
completion_manifest:
  implementation_reviewed: true
  tests_reviewed: true
  linter_clean: true
  no_security_issues: true
  no_contract_shrinkage: true

Code review passed. classify_readiness() is correctly read-only (rglob + open, no writes). readiness_gate_prompt() correctly delegates to _route_answer() with is_retry=False for first presentation. dispatch_it_po_v3() checks script existence before subprocess. Gate correctly positioned in run() before ticket generation. Two unused imports fixed by ruff autofix (MagicMock, pytest). build-ac.md Step 1b documents all required routing paths. No regressions in 54-test suite. Approved.

### 2026-06-05 13:50 — commit (status: ok)
feedback-id: fb_2026-06-05_2c2f4ace
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true

Commit ab9ddf0 includes ticket 02 changes: scripts/goal_to_epic.py (+611 lines), templates/agents/build-ac.md (+110 lines), tickets/00_inbox/epics/EPIC-GoalToEpic/02_readiness-gate.md (+241 lines), unit_tests/ac_store/test_readiness_gate.py (+448 lines). All pre-commit hooks passed. SHA: ab9ddf0. Branch: EPIC-GoalToEpic.

### 2026-06-05 14:00 — pull-request (status: ok)
feedback-id: fb_2026-06-05_ca63b198
completion_manifest:
  branch_pushed: true
  pr_exists: true
  no_new_pr_needed: true

Pushed ticket 02 changes to existing PR #69 on branch EPIC-GoalToEpic. Branch was already up to date with origin (commit ab9ddf0 already pushed in the same session that included ticket 03). PR #69 at https://github.com/urlmonitor/leafcutter-ai/pull/69 contains the readiness gate implementation.
