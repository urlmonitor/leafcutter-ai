---
title: "A reader gets a how-to, a reference, and an automatic checker for the project record"
date: "2026-09-25"
time: "10:07"
type: manual
components:
  - ux_prototyping
  - documentation_system
  - precommit_hooks
summary: "Three EPIC-TruthfulProjectRecord tickets land together: a how-to walking a first-time reader through starting a project record from nothing (UXP-700a-5), a reference stating the ownership rule and required-existence of the fern-and-fig example content (UXP-700d-5), and confirmation that the record's checker already runs automatically as part of the project's pre-commit checks, guarded by a new trigger-scope module and ADR-049 (UXP-700c-3). All three were finished by hand after their /build-feature drive halted before committing — two on a phase-agent schema retry cap, one on a genuine Agent Contracts target_path mismatch that this recovery pass corrected."
description: "Covers UXP-700a-5, UXP-700c-3, and UXP-700d-5, the final three tickets of EPIC-TruthfulProjectRecord. UXP-700a-5 adds docs/how-to/starting-a-project-record-from-nothing.md, walking a reader with no prior context through the empty record's contents, authoring a first journey/dataset/screen, reading the checker's nothing-examined vs checked-and-sound outcomes, and obtaining the separate fern-and-fig example product. UXP-700d-5 adds docs/reference/example-content-separation.md, stating the product-root ownership rule for both the product-truth store and the AC store, the three surfaces that honour the separation, why the example content must keep existing (naming ADR-022 and UXP-593), and how to extend it; its Agent Contracts AC-1 target_path was corrected during this recovery pass from ADR-022 (never edited, per the repo's one-directional reference-to-ADR precedent) to the new reference doc itself, which is what genuinely states the rule. UXP-700c-3 adds docs/product-truth/scripts/product_truth_trigger_scope.py (the record checker's resolvable-pointer trigger-scope constant, re-exported from product_truth_checks.py) and ADR-049, recording that the existing check-product-truth-validate pre-commit hook's files: regex is asserted equal to this constant by a dedicated test rather than hand-restated — confirmed, during this recovery pass, to be a test-tripwire against drift rather than live runtime derivation, since the hook registry files themselves remain hand-written JSON/YAML. All three tickets' documentation-verifier and commit phases, left incomplete by the original drive, were completed by hand in this recovery pass with hook validation performed directly rather than through the automated pipeline."
commits:
breaking: false
---

## Entry

The final three tickets of `EPIC-TruthfulProjectRecord` — `UXP-700a-5`,
`UXP-700c-3`, and `UXP-700d-5` — are finished. A `/build-feature` drive had
already produced the underlying work but halted before committing: two
tickets' phase agents hit a schema retry cap, and one hit a genuine mismatch
between its `## Agent Contracts` `target_path` and what `documentation-expert`
actually authored. This recovery pass finished all three by hand.

**`UXP-700a-5`** adds `docs/how-to/starting-a-project-record-from-nothing.md`:
a first-time reader's walkthrough of an empty product-truth record — what it
contains, how to author a first journey/dataset/screen with a worked example
at each step, how to read the checker's `nothing-examined` vs
`checked-and-sound` outcomes, and how the `fern-and-fig` example product is
obtained separately rather than shipping as part of the reader's own record.

**`UXP-700d-5`** adds `docs/reference/example-content-separation.md`: the
rule that decides which product an artifact or AC belongs to (the product
root, never its content), the three surfaces that honour that separation and
what each returns for example content, why the example content must keep
existing — naming ADR-022 and `UXP-593` as dependents — and how to add to it.
Its `## Agent Contracts` `AC-1` line originally named `ADR-022` as the
target_path, written before the authoring decision; this recovery pass
corrected it to name the new reference doc, which is what actually states the
rule, while leaving ADR-022 itself un-edited, consistent with this repo's
existing one-directional reference-to-ADR linking pattern.

**`UXP-700c-3`** confirms the record's checker runs as one of the project's
automatic pre-commit checks and adds `docs/product-truth/scripts/
product_truth_trigger_scope.py` plus `ADR-049-record-checker-trigger-scope.md`
recording the decision. The new module's `RESOLVABLE_POINTER_TRIGGER_PATTERNS`
constant is asserted equal, by a dedicated test, to the real
`check-product-truth-validate` hook's `files:` regex — a drift tripwire, not a
live derivation the hook registry reads at runtime, which this recovery pass
confirmed by tracing the constant's actual consumers before closing the
ticket.
