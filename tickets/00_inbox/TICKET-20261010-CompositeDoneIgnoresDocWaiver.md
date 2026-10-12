---
title: "A composite with documentation children can never be marked done"
status: todo
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
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# A composite with documentation children can never be marked done

## Actor / Goal
In order for a feature whose children include documentation to reach done, the composite proof must accept a documentation child the same way the leaf proof does.

## Context
- **Found 2026-10-10** closing the DK-600 decision-lifecycle tree. Every leaf is done (46 of 54), including nine documentation ACs with `test_required: false` and a `test_rationale`, marked done through `mark_ac_done.py` under the BO-2500a-1-ii waiver. Yet `mark_ac_done.py` refuses all eight parents (DK-600c-5, DK-600d-5, DK-600a to DK-600e, DK-600): "unfinished children: DK-600c-5-i, DK-600c-5-ii" and so on.
- **Cause:** `scripts/ac_store/_done_proof_composite.py` `_unproven_composite_children` requires every done leaf child to carry its own `# covers: <child-id>` tag (`elif child_id_str not in all_covered_ids`). It never consults `is_covers_tag_waived` (`_done_proof_phase_helpers.py`), which the leaf path has honoured since the KI-ACS-20260914 fix (`01601fbb`, #861).
- The same predicate feeds `check_staged_done_proofs`, so a hand edit to `done` would be refused at commit too.

## Scope
1. In `_unproven_composite_children`, a done leaf child whose record passes `is_covers_tag_waived` (test_required false and a non-empty test_rationale) counts as proven without a covers tag. Every other rule stays fail-closed.
2. Tests: a composite whose children are one tagged code leaf and one waived documentation leaf is proven; a documentation leaf without a rationale still fails; a composite with no AC-id children still fails.
3. Mirror `templates/` and `scripts/` through the build.
4. Then mark DK-600c-5, DK-600d-5, DK-600a to DK-600e and DK-600 done through `mark_ac_done.py` and regenerate product-truth derived data.

## Out of Scope
- Changing the leaf waiver itself.

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
