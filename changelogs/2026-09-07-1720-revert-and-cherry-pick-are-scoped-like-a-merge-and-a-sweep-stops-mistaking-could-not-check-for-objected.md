---
title: "Revert and cherry-pick are scoped like a merge, an objection names the test it is about, and a sweep stops mistaking could-not-check for objected"
date: "2026-09-07"
time: "17:20"
type: manual
components:
  - commit_guardian
  - testing_quality
  - git_vcs_operations
summary: "Lands GE-120e-4, GE-120e-4-i and GE-120e-2-i: an operation-record derivation that treats revert and cherry-pick like a merge, an objection that names the weakened test file, and a sweep predicate that no longer counts a check which never ran as a check that objected."
description: "Three acceptance criteria, and the two most interesting parts were defects in the tests rather than in the code. GE-120e-4 adds _operation_record.py and extends _authored_change.py so a revert or cherry-pick is scoped the way a merge already was. The derivation combines the states the commit is built on with the operation record rather than branching on whether a merge is in progress — the AC's fourth criterion forbids that marker-switch shape outright, because it reads as a sane default and fails only on the case where the record has expired, which every other fixture in the tree has present. The ordinary-commit negative control still holds: with no operation in progress the change set remains the author's entire staged content. GE-120e-4-i makes check_contract_shrinking.py name the weakened test file in its objection. It previously named the violation and the production files but never the test the author had actually weakened, which tells an author what they changed rather than what they broke — the same name-three-things requirement GE-120e-2-i imposes on its own sweep. Its test file also carried a fixture bug that had nothing to do with the criterion: _init_repo ran git init with cwd set to a directory it never created, so all four tests died at setup regardless of how well the AC was implemented. Fixing that one mkdir took the file from four failures to two passes before any implementation work, which means the bug had been masking real progress for as long as it existed. GE-120e-2-i's sweep contained the most instructive defect. It classified every non-zero exit as an objection, and on that basis accused six handed-its-files checks of objecting to carried-in content. Not one of them had inspected anything: two were handed no file argument and printed their usage text, two needed a product-truth store the second working copy does not carry, and two needed a fuller layout than the fixture provides. The sweep was conflating could-not-check with objected — precisely the distinction GE-120a-1 exists to establish and that check_outcome.py was written to express, committed inside the epic built to eliminate it. A _could_not_run predicate now separates the two, and 53 of the 59 handed-its-files entries run clean while the remaining six are excluded as non-evidence. They are excluded by outcome, not removed from the subject set: narrowing the list would have reinstated the hand-written-list defect GE-120e-2 had just removed, and that AC's own Implementation Notes forbid it. Two guards keep the exclusion from quietly weakening the test. A new assertion fails when the sweep exercised nothing at all, since reporting zero objections over zero checks actually run is the vacuous pass GE-120c-1-i forbids and is exactly the hole that excluding outcomes opens. And the planted-misrecord self-demonstration still passes, which is this AC's own evidence that the sweep can still be made to fail. The prose half of the classifier is marked at its definition as an interim fallback for checks that have not adopted check_outcome's vocabulary yet; it should shrink as GE-120a-2 and GE-120a-5 land, never grow, since a marker added to silence a genuine objection would defeat the criterion. One baseline stays deferred: test_ge_120b_2_i.py needs ticket 10's ge120b2i_verify_unchanged.py CLI, which does not exist, and merging its five tests red would be the failure this epic exists to prevent."
breaking: false
---

## Entry

### Landed

| AC | What | Tests |
|---|---|---|
| `GE-120e-4` | `_operation_record.py` — revert/cherry-pick scoped like a merge, from states **plus** record, never a marker switch | 6/6 |
| `GE-120e-4-i` | the objection now names the **weakened test file**, not just the violation and production files | 4/4 |
| `GE-120e-2-i` | sweep separates **could-not-check** from **objected** | 5/5 |

Full `unit_tests/portability/`: **106 passed** under `AC_ENFORCE_STRICT=1`.

### Two defects that were in the tests, not the code

- A **fixture bug** (`git init` into a directory never created) failed all four of ticket 36's
  tests at setup, masking real progress. One `mkdir`; 4 failed → 2 passed.
- A **predicate defect** made a sweep accuse six checks of objecting when none had run.

### Still open

`test_ge_120b_2_i.py` deferred — ticket 10's CLI does not exist. Tickets 35 and 36 stay
`todo`: `adr-author` outstanding on 35, four phases still `failed` on 36. Green tests are not
passed gates.
