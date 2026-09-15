---
title: "KI-KM-008 — 241 ACs are marked `todo` while a covering test already exists, so the store also lies in the direction that hides finished work"
description: "KI-KM-008 — 241 ACs are marked `todo` while a covering test already exists, so the store also lies in the direction that hides finished work"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - knowledge_management
related_docs:
  - docs/known-issues/knowledge-management.md
  - docs/known-issues/README.md
---

# KI-KM-008 — 241 ACs are marked `todo` while a covering test already exists, so the store also lies in the direction that hides finished work

> One known issue, split out of `docs/known-issues/knowledge-management.md` on
> 2026-09-14. Index: [knowledge-management.md](../knowledge-management.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-25 (measured) · **Last seen:** 2026-08-25
- **Where:** the AC store as a whole; the `work_status` field against `# covers:` tags in
  `unit_tests/` and `tests/`

**Symptom.** 241 AC records carry `work_status: todo` while at least one test in the suite
already carries their id in a `# covers:` tag. `KI-KM-002` measures the store lying one
way — done with nothing proving it. This is the mirror image: work that has a test, and a
record that still says it has not been started.

**Why it is not merely cosmetic.** Three consumers read `work_status` and each is misled
differently. `ac_prioritizer.py` picks the next unimplemented AC, so it will keep offering
work that is finished. `depends_on` edges resolve against it, so a downstream AC reads its
dependency as unmet and blocks or re-does it — `BO-2900g-4` sat behind `BO-2900g-3` in
exactly this way for six days. And every "how much is left" figure derived from the store
is inflated by up to 241 records, which makes the roadmap's own progress reporting
unreliable in the optimistic-effort direction.

**Root cause — the same diff-scoping as KI-KM-002, plus a workflow gap.** Nothing
re-examines a record after the commit that touched it. The dominant producer is the
direct-commit drive: `CLAUDE.md` → "AC-store reconciliation when pivoting to a
direct-commit drive" prescribes reconciling `work_status`, `implemented_by` and
`covered_by` before opening the PR, and that step is manual, easy to skip, and has no
gate. `BO-2900g-3` is a worked example — shipped in `ac564814` (PR #505) on 2026-08-19,
still `todo` with empty `implemented_by` and `covered_by` on 2026-08-25.

**Evidence.** Measured 2026-08-25 at `d37687ff` by joining every `# covers:` tag in
`unit_tests/**/*.py` and `tests/**/*.py` against `work_status: todo` records:

| level / readiness | count |
|---|---|
| L2 reviewed | 75 |
| L2 approved | 72 |
| L3 approved | 43 |
| L3 reviewed | 33 |
| L3 draft | 6 |
| L2 draft | 6 |
| L1 reviewed / draft / approved | 4 / 1 / 1 |
| **total** | **241** |

**The count is an upper bound on the lie, not a to-do list — do not bulk-flip it.** A
`# covers:` tag proves a test *names* the AC. It does not prove the test passes, and it
does not prove the test covers what the criteria actually ask for; a tag can be authored
red at the start of a TDD cycle that was then abandoned, and a passing test can cover one
clause of a five-clause AC. Flipping 241 records on the strength of the tag alone would
replace an understatement with an overstatement and manufacture the phantom-done this
repo exists to prevent — and, per the finalize step-3.5 incident, a bulk `work_status`
sweep is the specific operation that has already gone wrong here once. Each record needs
its tests run and its criteria read. `BO-2900g-3` was reconciled individually on
2026-08-25 on exactly that basis: six tests green under `AC_ENFORCE_STRICT=1`, plus both
load-bearing claims re-checked against the files on disk.

**Fix direction.** The measurement is the cheap part and should be automated first: a
store-wide report of `todo`-with-passing-covering-test, run on a schedule rather than in
the per-PR gate, so the population is visible and its trend is known. Retirement is then
per-record triage, and it should reuse whatever `TQ-400d` builds for the `KI-KM-002` pile
rather than growing a second parallel process — the two are the same review ("does this
test actually prove this criterion?") reached from opposite starting states. A ratchet
like `KM-ADM-005`'s would hold the floor in the meantime.

**Related.** `KI-KM-002` (the inverse population, 244 of 607, with an owner in `TQ-400d`).
`KI-ACS-004` (an AC marked done with no link to implementing code — the `implemented_by`
half of the same reconciliation gap). `KI-ACS-008` (the oracle's tag-to-test layer cannot
see async or parametrised tests, so any automated measurement here inherits that
undercount).

---
