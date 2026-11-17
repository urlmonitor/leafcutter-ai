---
title: "The test designer now names the wrong versions a guarding test must catch for bug fixes and gates, and none for new behaviour"
date: "2026-10-30"
time: "07:49"
type: manual
components:
  - testing_quality
summary: "TQ-500f-2-ii. templates/agents/test-designer.md gains the must_catch rule. The designer itself judges whether a clause is a bug fix, a gate, both or neither, after reading the code: no keyword matching, but it may read what the requirement says about earlier behaviour. A bug fix names 'revert the fix' plus a wrong version naming the condition; a gate names one 'drop the <X> condition' per condition plus 'the gate always allows'; a clause that is both carries both sets; new behaviour carries no must_catch and no discrimination angle. The worked example is corrected and the dangling 'rule below' reference fixed. Live test-designer eval: 1/3 before (2026-10-25), 3/3 twice with the refined rule. The fails the TQ-200d before-score expected until TQ-500f-2-ii was built are gone."
description: "Prompt change only. templates/agents/test-designer.md: Test Design Procedure points bug-fix and gate records at the must_catch rule (was a dangling 'the rule below' for bug fixes only); the old one-paragraph permission is replaced by the judgement rule (the designer's own, recorded only through must_catch or angle discrimination, no new key), the both case, the bug-fix / gate / new-behaviour bullets, the exact strings 'revert the fix' (runner alias 'the fix undone') and 'the gate always allows', and the conditional discrimination angle; the worked example now puts must_catch and angle discrimination on the bug-fix guard and none on the to_be_created new-behaviour entry; DECISION HISTORY entry added. Tests: unit_tests/evals/tq200d3/test_tq200d3_bug_fix_and_gate.py (test_bug_fix_row_requires_revert_and_a_condition_naming_version, test_gate_row_requires_one_wrong_version_per_condition) and unit_tests/evals/tq200d3/test_tq200d3_trap.py (test_new_behaviour_trap_fails_invented_wrong_versions) now also carry '# covers: TQ-500f-2-ii'. Behavioural substitute named in the AC's test_rationale: the TQ-200d-3 test-designer eval. Live eval runs of the test-designer set: 1/3 before the change (2026-10-25); 2/3 with the first version of the rule (the bug-fix row was judged a gate only); 3/3 and 3/3 with the refined rule (both case, reading stated earlier behaviour); 2/3 after the worked-example fix, where the new-behaviour row blocked on a fixture gap, filed as KI-TQ-20261030-test-designer-trap-fixture-has-no-reference-test (low)."
commits:
breaking: false
---

## Entry

The test designer now writes down, for each requirement it designs tests for, the wrong versions
of the code a guarding test must catch. It decides for itself, after reading the code, whether a
requirement fixes a bug, guards an action behind conditions (a gate), does both, or adds something
new. It does not decide by spotting keywords, but it may read what the requirement says about how
things used to behave.

- A bug fix names "revert the fix" and at least one wrong version that drops the condition
  involved.
- A gate names one "drop the <X> condition" per condition, and "the gate always allows".
- A requirement that is both gets both sets.
- New behaviour gets none, because there is no earlier version to go back to.

The example in the designer's instructions had these the wrong way round and is corrected, and a
reference to "the rule below" that pointed nowhere now points at this rule.

Measured with the test designer's eval (three examples: a bug fix, a gate and new behaviour, run
against the real agent):

| Version | Score |
|---|---|
| Before the change (2026-10-25) | 1/3 |
| First version of the rule | 2/3 (the bug fix was read as a gate only) |
| Refined rule (a requirement can be both; earlier behaviour may be read) | 3/3, and 3/3 again |
| After the example fix | 2/3 (the new-behaviour example was blocked by a gap in the eval's example project, not by the rule) |

The before-score of 2026-10-25 said the test designer's failures on the bug-fix and gate examples
were expected until TQ-500f-2-ii was built. It is now built. The gap in the new-behaviour example
is recorded as a known issue: the example gives the designer no existing test file it is allowed
to find, so a designer that follows its instructions stops instead of guessing.
