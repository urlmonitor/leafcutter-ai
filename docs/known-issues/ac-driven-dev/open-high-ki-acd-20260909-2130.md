---
title: "KI-ACD-20260909-2130 — Two approved ACs in one epic demand opposite verdicts for the same store state, and nothing in the AC store can detect it"
description: "KI-ACD-20260909-2130 — Two approved ACs in one epic demand opposite verdicts for the same store state, and nothing in the AC store can detect it"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
---

# KI-ACD-20260909-2130 — Two approved ACs in one epic demand opposite verdicts for the same store state, and nothing in the AC store can detect it

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** both instances resolved; the CLASS remains open (no gate detects AC-vs-AC contradiction)
- **Occurrences:** 2 (both found on 2026-09-09 while implementing EPIC-TruthfulProjectRecord)
- **First seen:** 2026-09-09 · **Last seen:** 2026-09-09
- **Where:** `docs/acceptance-criteria/ux-prototyping/UXP-700-truthful-project-record/` — `UXP-700b-1-i.yaml` vs `UXP-700b-1-ii.yaml`; `UXP-700a-1-i.yaml` vs `UXP-700b-2-i.yaml`

**Symptom.** Two ACs, both `readiness: approved`, both with tests written by `test-writer`,
specify opposite required behaviour for a store state that is identical in every observable
respect. No implementation can make both suites green.

*Pair 1 — resolved 2026-09-10 by user decision.* A store with journeys present but zero mock-data and zero mockups:

- `UXP-700b-1-i`'s test asserts the outcome **is** `checked-and-sound` ("an all-clean store must report outcome 'checked-and-sound'").
- `UXP-700b-1-ii`'s test asserts the outcome **is not** `checked-and-sound` ("a store with three journeys but zero example data and zero screens must not report the clean-pass outcome").

Both fixtures build the same shape: flows populated, `mock-data/` and `mockups/` created and
left empty, an empty `classifier/eval.jsonl` seeded, flows carrying `entities: []` and steps
with no `screen`. There is no field, count or file that separates them.

**Resolved in `UXP-700b-1-i`'s favour**: a record holding journeys but no screens or example
data yet is young, not defective — everything it holds was checked and was sound, which is
what the clean pass claims. `UXP-700b-1-ii`'s AC-3 clause and its two assertions were amended
to match, and both files record why. What `-1-ii` uniquely contributes is untouched and still
enforced: the report NAMES exactly which artifact types read zero records, in `empty_types`,
and never names a populated one. Emptiness is reported; it does not change the verdict.

*Pair 2 — resolved by construction.* A zero-artifact store whose `classifier/eval.jsonl` is
absent: `UXP-700b-2-i` requires exit 0 ("fail open and list the check as not executed"),
`UXP-700a-1-i` requires non-zero ("a caller consuming this checker's exit code must see a
BLOCK decision"). These were reconciled by the one incidental difference between their
fixtures — `UXP-700b-2-i` creates `classifier/` and omits the file, `UXP-700a-1-i` omits the
directory entirely — read as "not authored yet" (stay open) versus "never installed" (block).
That distinction is defensible and is now implemented and documented in
`validate_product_truth.py`'s DECISION HISTORY, but it was **inferred from fixture
construction, not from either AC's text**.

**Why the store cannot see this.** Every existing gate checks an AC in isolation or against
its own hierarchy: `check-ac-schema` validates shape, `check-ac-tree-limits` counts children,
`check-ac-parent-covered-by` checks the `covered_by` relation, `check-ac-circular-deps`
checks `depends_on`. None compares what two sibling ACs *assert about the same subject*. Two
ACs can therefore both reach `readiness: approved` while being mutually unsatisfiable, and the
contradiction surfaces only when a coder tries to make both test suites pass — after the
tests are written, the tickets generated, and the epic driven.

**Detection.** There is no automated detection today. The manual tell is a red test whose
assertion is the exact negation of a sibling AC's assertion over a fixture of the same shape:

```bash
# both green individually against their own AC's intent, unsatisfiable together
python -m pytest unit_tests/product_truth/test_uxp_700b_1_i.py -k degraded_outcome_vocabulary
python -m pytest unit_tests/product_truth/test_uxp_700b_1_ii.py -k outcome_is_not_the_clean_pass
```

**Fix direction.** (1) *Both instances are now closed* — pair 2 by the installed-vs-authored
distinction, pair 1 by amending `UXP-700b-1-ii`. (2) *The class remains open*: when several ACs constrain one observable (here, the checker's outcome value
and exit code), that observable's value table belongs in ONE place — an AC, or an ADR the ACs
cite — rather than being restated per-AC in prose that reads as compatible until two fixtures
are built. `ADR-042` already declares the outcome vocabulary; it stops short of declaring
which state maps to which value, which is exactly the gap both pairs fell into.

**Pattern:** the AC store's gates all answer "is this AC well-formed?" and none answers "do
these ACs agree?" — so approval certifies shape, and contradiction is discovered by
implementation. **Related:** `ADR-042` (the outcome vocabulary these ACs disagree about),
`GE-120` (green means it was checked — the thesis both ACs are drawing on, and read
oppositely).
