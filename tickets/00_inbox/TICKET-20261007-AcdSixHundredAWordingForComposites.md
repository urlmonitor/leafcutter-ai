---
title: "ACD-600a: record that a composite AC goes in_progress, and an unproven done one is refused"
status: todo
components:
  - ac_driven_dev
created: 2026-10-07
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
change_target: docs
risk_surface: internal
roadmap_phase: phase_1
advances_current_outcome: false
tags:
  - ac-store
  - ac-amendment
  - mark-ac-done
last_updated: 2026-10-07
files_touched:
  - docs/acceptance-criteria/ac-driven-dev/ACD-600a.yaml
  - docs/acceptance-criteria/ac-driven-dev/ACD-600a-1.yaml
  - docs/acceptance-criteria/ac-driven-dev/ACD-600a-1-ii.yaml
  - docs/acceptance-criteria/ac-driven-dev/ACD-600a-2.yaml
agents:
  business-analyst: needed
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  llm-expert: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
---

# ACD-600a: record that a composite AC goes in_progress, and an unproven done one is refused

## Actor / Goal
In order that a reader of the AC store finds the behaviour `mark_ac_done.py` really has, we need
ACD-600a and its children to say what happens to a composite AC. Then the shipped composite rule is
not read as a violation of the script's own contract.

## Context
- **What ACD-600a promises (L1, `work_status: done`).**
  - "Then the referenced AC YAML file is updated to work_status: done" (`docs/acceptance-criteria/ac-driven-dev/ACD-600a.yaml:16`).
  - "the script is idempotent (re-running on an already-done AC is a no-op exit 0)" (:19). The
    it_requirements entry at :27 says the same.
  - Its children say the same for each path:
    - ACD-600a-1 (`--ticket`): "the AC YAML file is updated so that work_status reads "done""
      (`ACD-600a-1.yaml:20`);
    - ACD-600a-1-ii (`--ac`): the same sentence (`ACD-600a-1-ii.yaml:18`);
    - ACD-600a-2: an already-done AC gives exit 0, "no-op ... already work_status=done", and a
      byte-identical file (`ACD-600a-2.yaml:12-17`).
- **What the script does now.** EPIC-BuildToolingRunsThrough ticket 06 (commit ed2190fd3, BO-202, user
  flag F6) narrowed this for composites: ACs whose `covered_by` lists child AC ids. The rule is
  `_composite_verdict`, `scripts/ac_store/mark_ac_done.py:96-142`:
  - a `todo` or `in_progress` composite with an unfinished child: `marked <id> work_status=in_progress
    (unfinished children: ...)`, exit 0;
  - an already-done composite with an unproven child: stderr `REFUSED: <id> is work_status=done but
    composite children are not done and proven: ...`, exit 3, file unchanged;
  - every child done and proven: `done`, as before.
  Leaves keep the ACD-600a contract (BO-202 it_requirements: "Leaves unchanged ... including the
  ACD-600a contract (preconditions, messages, exit codes, idempotence)").
- So ACD-600a's L1 wording, ACD-600a-1, ACD-600a-1-ii and ACD-600a-2 now overstate for composites.
- **Two ways to record it.** The business-analyst chooses one and the user approves it:
  1. Amend the criteria. Scope the done and idempotence clauses to leaves ("an AC whose covered_by
     lists no child AC ids"), and point composites to BO-202. Add an `amended_by` entry like the one
     BO-202 got on 2026-10-06 (`BO-202.yaml:79-85`).
  2. Leave the criteria as they are and add a narrowing note: an `amended_by` entry with
     `reason: narrowed-by-later-sibling` in the form of `BO-210.yaml:59-64`, naming BO-202 and
     ticket 06.
- **ACD-600a.yaml cannot be staged as it is today.** ACD-600a is `done`, and its `covered_by` lists
  ACD-600a-1 to ACD-600a-4, which are all `todo`. Staging the file makes check-done-proof refuse it:
  "composite ACD-600a is marked done but its covered_by children are not all done-and-covered —
  unproven: ACD-600a-1, ACD-600a-2, ACD-600a-3, ACD-600a-4" (`check_staged_done_proofs`, run
  2026-10-07). The required proof-of-done CI check reads the same rule. So any edit to ACD-600a.yaml
  also needs a decision on its `work_status`; under BO-202's rule it would be `in_progress`. The
  children are `todo`, so editing them is not affected.

## Acceptance Criteria
- [ ] AC-1: ACD-600a, ACD-600a-1, ACD-600a-1-ii and ACD-600a-2 each state, in their criteria or in an `amended_by` narrowing note, that a composite AC follows BO-202: `in_progress` while a child is unfinished, and a refusal (exit 3, file unchanged) when it is already `done` and a child is unproven.
- [ ] AC-2: The leaf contract keeps its wording and meaning: preconditions, messages, exit codes and idempotence.
- [ ] AC-3: Each edited record has an `amended_by` entry naming this ticket, BO-202, EPIC-BuildToolingRunsThrough ticket 06 and the date of the user's approval.
- [ ] AC-4: The edited records pass check-ac-schema and check-done-proof at commit without `SKIP`. If ACD-600a's `work_status` has to change for that, the user approved the new value and its `amended_by` entry records it.
- [ ] AC-5: No code or test file changes.

## Test Requirements

```yaml
tests: []
rationale: |
  AC text only. The composite behaviour these records describe is already tested by ticket 06
  (tests/ac_store/test_mark_ac_done.py, e.g. test_already_done_unproven_composite_is_refused).
  The commit-time hooks (check-ac-schema, check-done-proof) check the edited records.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | (review) | | |
| AC-2 | (review) | | |
| AC-3 | (review) | | |
| AC-4 | (the commit's pre-commit run) | | |
| AC-5 | (diff) | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

### business-analyst (needs the user's approval)
- [ ] Choose option 1 or 2 from Context and get the user's approval.
- [ ] Edit ACD-600a, ACD-600a-1, ACD-600a-1-ii and ACD-600a-2. Add the `amended_by` entries.
- [ ] Decide ACD-600a's `work_status` with the user before staging it (see Context).

### pr-reviewer / commit
- [ ] Check that no leaf clause changed meaning, and that the commit passes without `SKIP`.

## Risk & Safety
- Touches money? No.
- Touches data? AC text and possibly ACD-600a's `work_status`. Reopening ACD-600a moves it out of
  `done` in every report that counts done ACs.
- Reversibility: revert the commit.

## Out of Scope
- Any change to `mark_ac_done.py`.
- Callers that run `mark_ac_done.py` without `--test-root` (`TICKET-20261007-FinalizeFeatureCountsInProgressComposites`).
- ACD-600a-1-i, ACD-600a-3 and ACD-600a-4 (refusals for a deprecated AC, an unknown id and a ticket
  without `source_ac`). The composite rule does not change them.
