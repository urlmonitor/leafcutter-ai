---
title: "Reference: Commit Guardian Machine-Readable Outcome Vocabulary"
description: "The shared check_outcome.py vocabulary every commit-guardian check reports through — OUTCOME_OK, OUTCOME_COULD_NOT_CHECK and OUTCOME_NOTHING_TO_INSPECT — and the fixed-shape RESULT line emit_result() prints so a caller can read the outcome without parsing prose."
type: reference
status: active
created: 2026-10-25
last_updated: 2026-10-25
components:
  - commit_guardian
related_docs:
  - docs/architecture/components/commit-guardian.md
  - docs/architecture/adrs/ADR-038-commit-guardian-shared-change-set-derivation.md
related_code:
  - templates/scripts/commit_guardian/check_outcome.py
  - templates/scripts/commit_guardian/check_contract_shrinking.py
  - templates/scripts/commit_guardian/check_doc_frontmatter.py
---

# Commit Guardian Machine-Readable Outcome Vocabulary

> **Parent document:** [Commit Guardian](../architecture/components/commit-guardian.md) — see its "Merge-Aware Checks" section for the merge-scoped change set referred to below.

Because the merge-scoped set can legitimately come back empty — a clean
auto-merge where the author changed nothing of their own — both checks must be able
to report that outcome explicitly, without silently widening back to the whole staged
tree and without confusing it with a check that never ran at all. `check_outcome.py`
declares this vocabulary once, for every check in this directory to share:

| Constant | Meaning |
|---|---|
| `OUTCOME_OK` | The check ran its inspection and found nothing wrong. |
| `OUTCOME_COULD_NOT_CHECK` | The check could not perform its inspection at all (e.g. a required helper module was absent) — distinct from a genuine clean pass. |
| `OUTCOME_NOTHING_TO_INSPECT` | The check derived its own (merge-scoped/authored) change set per the parent document's "Merge-Aware Checks" section and that set was empty — there was nothing of the author's to inspect. This is a pass, not a skip: exit status is 0 and the commit proceeds. It must never be produced by falling back to the whole staged tree when the derived set is empty; an empty derived set is an explicit value, not an absence, and is never widened. |

Each value is emitted on stdout as a fixed-shape `RESULT: <outcome>` line via
`check_outcome.emit_result()`, so a caller can detect it with
`line.startswith("RESULT: ")` independent of exit code and without parsing prose.
`check_contract_shrinking.py` and `check_doc_frontmatter.py` both call a
`_report_if_nothing_to_inspect()` helper from their own empty-derived-set pass branch
in `main()` to emit `OUTCOME_NOTHING_TO_INSPECT`. See AC `GE-120e-1-i` under
`docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/` for the
no-widening-on-empty guarantee this vocabulary entry pins down, and AC `GE-120a-1`
for the `OUTCOME_OK` / `OUTCOME_COULD_NOT_CHECK` vocabulary it extends.
