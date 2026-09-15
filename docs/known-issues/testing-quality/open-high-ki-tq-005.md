---
title: "KI-TQ-005 — Fixtures that never built the collection they assert over, three times in one epic"
description: "KI-TQ-005 — Fixtures that never built the collection they assert over, three times in one epic"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
---

# KI-TQ-005 — Fixtures that never built the collection they assert over, three times in one epic

> One known issue, split out of `docs/known-issues/testing-quality.md` on
> 2026-09-14. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high as a pattern
- **Status:** open as a pattern — the specific test files named below are **not on `main`**
  (they live on unmerged PR #495); the pattern and its diagnostic signature are what this entry
  is for
- **Occurrences:** 3 (one epic)
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-25
- **Where:** PR #495's `test_ge_122a_1.py` and `test_ge_122a_1_i.py`

**Symptom.** Three test files asserted properties of "a collection" while their fixtures never
created two, three, or four of its namespaces. They passed only because the fail-open they
should have caught was masking their own incompleteness:

| File | What the fixture omitted |
|---|---|
| `test_ge_122a_1.py::test_repaired_collection_passes_with_per_namespace_counts` | `tickets/` root and `ticket_lifecycle.json` |
| `test_ge_122a_1_i.py` (three tests) | `docs/architecture/adrs/`, `docs/architecture/diagrams/`, `ticket_lifecycle.json` |

The first of these was asserting *"a repaired collection passes"* over a collection that was
never there.

**Root cause / diagnostic signature.** Each was exposed only when the fail-open was closed —
which is the signature: **fixing a fail-open turns incomplete fixtures red.** Those failures
look exactly like a regression in the fix, and the tempting response is to weaken the new
assertion. That is backwards. In all three cases the assertions were correct as written and the
setup was short.

Note also how the second instance was mis-diagnosed at first. Only the work-items scanner logs
a warning on an unresolvable root (see `commit-guardian.md`'s `KI-CG-031`), so the visible
symptom named one missing file when three namespaces were actually unresolved. A silent failure
made an incomplete fixture look like a smaller problem than it was.

**Detection.** After closing any fail-open, expect newly-red tests and triage each with one
question: *is the assertion wrong, or was the fixture never complete?* Complete the fixture
without touching a single assertion and re-run. Green means the fixture was short. Still red
means the fix is wrong. **Wanting to change an assertion is the signal that you are about to
paper over a real defect.**

**Fix direction (pattern).** A shared fixture builder that constructs **all** of a collection's
namespaces by default, so a test must opt out of one explicitly rather than omit it by accident.
PR #495's `test_ge_122a_1_i.py` grew a `_resolve_non_ac_namespaces` helper doing exactly this,
with a comment warning against tidying it away.

**Pattern:** `docs/reference/false-green-mechanisms.md` — a test passing for the wrong reason,
where the bug and the test's blind spot are the same bug.

---
