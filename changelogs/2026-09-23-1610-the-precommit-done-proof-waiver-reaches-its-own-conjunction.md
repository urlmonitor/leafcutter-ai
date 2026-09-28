---
title: "main is green again: the pre-commit done-proof waiver now reaches the conjunction that was added in front of it"
date: "2026-09-23"
time: "16:10"
type: manual
components:
  - commit_guardian
  - phantom_done_prevention
summary: "main has been red since 01601fbb (PR #861). That PR taught the done-proof gate that test_required: false only waives the covers-tag mandate when a non-empty test_rationale accompanies it, and added is_covers_tag_waived to the pre-commit arm — but left the pre-existing unconditional 'if test_required is False: continue' standing ahead of it, so the new conjunction was structurally unreachable on exactly the records it was added to catch. Deleting the early return makes the shared predicate the only waiver on that path. The two reachability tests #861 shipped red now pass; one sibling test that pinned the superseded single-condition rule is moved onto the amended contract."
description: "WHY main WAS RED AND WHAT IT BLOCKED. Every PR in the repo was stuck: 'Test suite (pytest)' is one of six required checks, and it failed on main itself at 01601fbb and 8e50b2a3 with the same two failures — TestPrecommitCliReachability::test_ac_refuse_test_required_false_missing_rationale and ::test_ac_refuse_test_required_false_whitespace_rationale, both 'AssertionError: 0 != 1 ... Got exit 0'. Reproduced locally at main's tip before changing anything, with byte-identical assertion messages, so the failure was pinned to main rather than inferred from a log. PR #870 and PR #875 each carried the identical two failures and 6426 passes; neither touches done_proof. THE DEFECT. In check_staged_done_proofs (templates/scripts/commit_guardian/check_done_proof.py) the leaf path read: `if data.get(\"test_required\") is False: continue` followed by `if ac_id_str not in all_covered_ids: if is_covers_tag_waived(data): continue`. #861 added the second condition — the ONE shared BO-2500a-1-ii predicate requiring test_required is False AND a non-empty, non-whitespace test_rationale — and left the first. An AC declaring itself untestable with NO recorded reason hit the early return and was waived before the conjunction was ever consulted, so the pre-commit arm kept its pre-#861 behaviour while check_all_done_acs and check_changed_done_acs had moved to the conjunction. This is the 'new guard added behind a pre-existing early return' shape: the code reads as though the rule changed, every direct unit test of the predicate passes, and the only thing that catches it is a test that drives the real entry point — which is precisely what #861's own TestPrecommitCliReachability does, and why it was red. THE FIX is the deletion of those two lines. Removing the early return cannot weaken anything: an AC already in all_covered_ids never reaches the branch, so the only records whose verdict changes are uncovered test_required: false ACs, which is the exact set BO-2500a-1-ii exists to refuse when they carry no rationale. The function docstring is rewritten to describe the conjunction rather than the single condition, and records the early return's removal and why it made the conjunction unreachable, so the next reader does not re-add it. The deliberate level-first ordering (composite guard before waiver, the ACD-400a fail-closed asymmetry against CI) is preserved and its rationale restated. THE ONE TEST THAT HAD TO MOVE, stated plainly because weakening a test to make a change pass is the failure mode this repo exists to prevent. test_done_proof_test_required_exemption.py::test_done_ac_with_test_required_false_and_no_covers_tag_passes (covers BO-2500a-3) built its fixture with test_required=False and no rationale, and asserted no violation — the rule BO-2500a-1-ii deliberately supersedes. It was NOT deleted and NOT skipped: its fixture now carries a test_rationale, so it still asserts the property BO-2500a-3 was authored for — a documentation AC is exempt at pre-commit exactly as it is in CI — under the amended waiver. The case it vacated is not lost: 'test_required: false with no rationale is REFUSED' is asserted, in the opposite direction, by the two rationale_gate tests this change turns green. Net assertions about that input: unchanged in number, corrected in direction. Worth noting how close this came to going unnoticed: that test was xfail-masked locally by pytest_ac_enforcement because BO-2500a-3's work_status is not done, so it reported as a mask rather than a failure. Under AC_ENFORCE_STRICT=1 both files run 18 passed. EVIDENCE. Before: 2 failed, 8 passed in the rationale_gate file at main's tip. After: 10 passed. Both files together under AC_ENFORCE_STRICT=1: 18 passed. ruff clean on both changed files. The wider unit_tests/commit_guardian/ run in this worktree reports ~135 failures, essentially all of them FileNotFoundError on scripts/commit_guardian/commit_guardian.json — a fresh worktree has no deployed layer, which is a known local-environment false-RED and is NOT evidence about this change; CI builds that layer and is the arbiter. NOT DONE HERE: no AC was authored, because this completes BO-2500a-1-ii's already-specified contract on the one arm #861 left behind, and the tests already carry its covers tag. scripts/commit_guardian/ is untracked build output, so only the templates/ copy exists to change."
commits:
breaking: false
---

## Entry

`main` has been red since `01601fbb` (PR #861). Because `Test suite (pytest)` is a
required check, **no PR in the repo could merge** — including two that were
otherwise green and waiting.

### The defect

PR #861 changed the rule: `test_required: false` waives the covers-tag mandate
only when a non-empty `test_rationale` accompanies it. It added that shared
predicate to the pre-commit arm — and left the older unconditional exemption
standing in front of it:

```python
if data.get("test_required") is False:
    continue                      # <- reached first, always
if ac_id_str not in all_covered_ids:
    if is_covers_tag_waived(data):   # <- the new conjunction, unreachable
        continue
```

A rationale-less AC returned at the early exit and was waived, so the pre-commit
arm kept its pre-#861 behaviour while both CI arms had moved on. The fix deletes
the early return.

It cannot weaken anything: a covered AC never reaches the branch, so the only
verdicts that change are uncovered `test_required: false` ACs — exactly the set
BO-2500a-1-ii exists to refuse when no reason is recorded.

### The one test that had to move

`test_done_ac_with_test_required_false_and_no_covers_tag_passes` (covers
BO-2500a-3) pinned the superseded single-condition rule. It was not deleted and
not skipped — its fixture now carries a rationale, so it still asserts what it was
written for (a documentation AC is exempt at pre-commit exactly as in CI) under
the amended waiver. The case it vacated is asserted in the opposite direction by
the two tests this change turns green.

It had been **xfail-masked** locally by `pytest_ac_enforcement`, since BO-2500a-3
is not `done`. Under `AC_ENFORCE_STRICT=1` both files run 18 passed.

### Evidence

Reproduced at main's tip before changing anything — same two failures, byte-identical
messages. After: 10 passed in the rationale-gate file, 18 across both under strict
enforcement, ruff clean.
