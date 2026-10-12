---
title: "A composite with documentation children can never be marked done"
status: in_progress
components:
  - ac_store
created: 2026-10-10
last_updated: 2026-10-10
depends_on: []
priority: high
roadmap_phase: phase_1
change_target: infrastructure
risk_surface: internal
requires_diagram: false
requires_adr: false
agents:
  test-writer: signed_off
  python-coder: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
---

# A composite with documentation children can never be marked done

## Actor / Goal
In order for a feature whose children include documentation to reach done, the composite proof must accept a documentation child the same way the leaf proof does.

## Context
- **Found 2026-10-10** closing the DK-600 decision-lifecycle tree. Every leaf is done (46 of 54), including nine documentation ACs with `test_required: false` and a `test_rationale`, marked done through `mark_ac_done.py` under the BO-2500a-1-ii waiver. Yet `mark_ac_done.py` refuses all eight parents (DK-600c-5, DK-600d-5, DK-600a to DK-600e, DK-600): "unfinished children: DK-600c-5-i, DK-600c-5-ii" and so on.
- **Cause:** `scripts/ac_store/_done_proof_composite.py` `_unproven_composite_children` requires every done leaf child to carry its own `# covers: <child-id>` tag (`elif child_id_str not in all_covered_ids`). It never consults `is_covers_tag_waived` (`_done_proof_phase_helpers.py`), which the leaf path has honoured since the KI-ACS-20260914 fix (`01601fbb`, #861).
- The same predicate feeds `check_staged_done_proofs`, so a hand edit to `done` would be refused at commit too.
- **Which AC this completes:** BO-2500a-1-ii (done) requires the waiver at "any layer that decides" an AC's done-status, with "the same verdict" from "one shared rule". The composite check decides each child's done-status without that rule, so this fix completes BO-2500a-1-ii; BO-2500b-1-iii's criteria stay as they are (a waived child is done and proven).

## Scope
1. In `_unproven_composite_children`, a done leaf child whose record passes `is_covers_tag_waived` (test_required false and a non-empty test_rationale) counts as proven without a covers tag. Every other rule stays fail-closed.
2. Tests: a composite whose children are one tagged code leaf and one waived documentation leaf is proven; a documentation leaf without a rationale still fails; a composite with no AC-id children still fails.
3. Mirror `templates/` and `scripts/` through the build.
4. Then mark DK-600c-5, DK-600d-5, DK-600a to DK-600e and DK-600 done through `mark_ac_done.py` and regenerate product-truth derived data.

## Out of Scope
- Changing the leaf waiver itself.

## Test Requirements

```yaml
tests:
  - name: test_a_composite_with_a_waived_documentation_child_is_proven
    location: unit_tests/commit_guardian/test_bo_2500a_1_ii_composite_waiver.py
    type: unit
    covers: BO-2500a-1-ii
    description: |
      A composite whose covered_by children are one done code leaf carrying its own
      covers tag and one done documentation leaf with test_required false and a non-empty
      test_rationale (no covers tag) is proven: _unproven_composite_children returns [].
  - name: test_a_documentation_child_without_a_rationale_is_still_unproven
    location: unit_tests/commit_guardian/test_bo_2500a_1_ii_composite_waiver.py
    type: unit
    covers: BO-2500a-1-ii
    description: |
      The same documentation leaf with test_required false but an empty or missing
      test_rationale (and no covers tag) is reported as an unproven child.
  - name: test_a_not_done_documentation_child_is_still_unproven
    location: unit_tests/commit_guardian/test_bo_2500a_1_ii_composite_waiver.py
    type: unit
    covers: BO-2500a-1-ii
    description: |
      A waived documentation leaf whose work_status is not done is reported as unproven.
  - name: test_mark_ac_done_marks_a_composite_whose_doc_children_are_waived
    location: unit_tests/commit_guardian/test_bo_2500a_1_ii_composite_waiver.py
    type: integration
    covers: BO-2500a-1-ii
    description: |
      Against a temporary AC store, mark_ac_done.py marks such a composite done (exit 0),
      and check_staged_done_proofs accepts the staged done composite with no violation.
```

## Sign-offs

- [x] test-writer — 2026-10-12 12:55
- [x] python-coder — 2026-10-12 13:20
- [x] pr-reviewer — 2026-10-12 13:40
- [x] commit — 2026-10-12 14:00
- [ ] pull-request

## Comments

### 2026-10-12 12:55 — test-writer (status: ok)
feedback-id: fb_2026-10-12_85fca8ba
completion_manifest:
  cross_layer_seam_answer:
    result: covered
    producing_side: "scripts/ac_store/_done_proof_composite.py _unproven_composite_children"
    consuming_side: "scripts/ac_store/mark_ac_done.py CLI and check_done_proof.check_staged_done_proofs"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "python scripts/ac_store/mark_ac_done.py --ac <id> --ac-root <dir> --test-root <dir> (CLI via subprocess)"
red_baseline:
  - test_name: test_a_composite_with_a_waived_documentation_child_is_proven
    file: unit_tests/commit_guardian/test_bo_2500a_1_ii_composite_waiver.py
    kind: assertion
    error: "AssertionError: Lists differ: ['BO-9201-ii'] != []"
  - test_name: test_mark_ac_done_marks_a_composite_whose_doc_children_are_waived
    file: unit_tests/commit_guardian/test_bo_2500a_1_ii_composite_waiver.py
    kind: assertion
    error: "AssertionError: 'in_progress' != 'done' : no-op BO-9201 work_status=in_progress (unfinished children: BO-9201-ii)"
Wrote 7 tests; 2 red, 5 negative controls (no rationale, not done, test_required true, no AC children, CLI refusal) pass immediately by design and pin the fail-closed rules.

### 2026-10-12 13:20 — python-coder (status: ok)
feedback-id: (submit-failed)
Changed scripts/ac_store/_done_proof_composite.py: _unproven_composite_children and _verify_composite_eligible (the mark_ac_done oracle path) now consult is_covers_tag_waived for leaf children. Scope item 4 (marking DK-600 ACs done) not performed here.
red_baseline_results:
  - test_name: test_a_composite_with_a_waived_documentation_child_is_proven
    result: green
  - test_name: test_mark_ac_done_marks_a_composite_whose_doc_children_are_waived
    result: green

### 2026-10-12 13:40 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
No high-confidence findings. Both predicates (_unproven_composite_children, _verify_composite_eligible) now consult the shared is_covers_tag_waived; fail-closed rules intact; 7 new tests pass.
Suppressed: 0 low, 0 dropped. Escalation: Branch none (medium count 0).
Note: scope item 4 (mark DK-600 ACs done) and templates/ mirror remain for later phases.

### 2026-10-12 14:00 — commit (status: ok)
feedback-id: (submit-failed)
Auto-authorized commit gate: subject "fix(ac_store): composite done-proof honours the documentation waiver"; staged files: scripts/ac_store/_done_proof_composite.py, unit_tests/commit_guardian/test_bo_2500a_1_ii_composite_waiver.py, ticket.
