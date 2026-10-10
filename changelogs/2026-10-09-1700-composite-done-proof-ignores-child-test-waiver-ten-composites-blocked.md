---
title: "Composite done-proof ignores a child's test waiver, and 10 composites are blocked by it"
date: "2026-10-09"
time: "17:00"
type: manual
components: 
  - commit_guardian
summary: "The check-done-proof gate refuses to mark a composite AC done when one of its children is a done, docs-only AC with test_required: false and a rationale. The known-issue entry that covers this gets a third occurrence (INF-700a), a reproduction, current code citations, and a list of the 10 composites currently blocked."
description: "One content commit (012453ffa), documentation only. Records Occurrence 3 of KI-CG-20260914-done-proof-precommit-ignores-test-required instead of filing a duplicate. The leaf-level waiver was fixed by #861/#878. The composite derivation still counts a waived child as unproven, both in _unproven_composite_children (pre-commit, scripts/ac_store/_done_proof_composite.py:265-266, reached from templates/scripts/commit_guardian/check_done_proof.py:442-455) and in _verify_composite_eligible (CI, _done_proof_composite.py:315-317). Reproduced on origin/main 4a5dfc1a5 by staging an INF-700a work_status flip and running pre-commit run check-done-proof, which refused with 'unproven: INF-700a-3, INF-700a-4'; the flip was discarded. A read-only store scan lists 10 composites blocked only by done, waived leaf children. The fix direction is stated as accept/refuse conditions. The commit-guardian.md index row is updated. No code changed and no AC flipped."
commits: 
  - 012453ffa
breaking: false
---

## Entry

The `check-done-proof` gate refuses to mark a composite AC `done` when one of its children
is a docs-only AC that is itself `done`, with `test_required: false` and a written rationale.
The leaf-level waiver (`is_covers_tag_waived`, #861/#878) is not applied to children, so
the composite check counts that child as "unproven".

- **KI-CG-20260914-done-proof-precommit-ignores-test-required amended** with Occurrence 3,
  instead of a duplicate entry.
  - `INF-700a` was refused with `unproven: INF-700a-3, INF-700a-4`. This was reproduced with
    the real hook on `origin/main` `4a5dfc1a5`, and the flip was not committed.
  - The gap is cited in both the pre-commit check (`_unproven_composite_children`) and the
    CI check (`_verify_composite_eligible`).
  - Lists the **10 composites** currently blocked only by done, waived children: `ACD-2100d`,
    `ACD-2100e`, `INF-1100d`, `INF-700a`, `INF-700c`, `TQ-500f-4`, `UXP-542`, `UXP-700a`,
    `UXP-700c` and `UXP-700d`.
  - The fix direction: count a done child as proven when it passes the same waiver, and
    keep refusing when the waiver is not met.
- **`docs/known-issues/commit-guardian.md`**: the index row is updated to match.

Documentation only. No code changes, and no AC was flipped.
