---
title: "KI-ACS-20261015-superseded-records-held-to-forward-rules — an AC marked superseded is still held to the forward-build rules, so a done record whose behaviour was deliberately removed cannot be retired honestly"
description: "high — check-done-proof and check-ac-schema apply the same rules to a record with status superseded_by as to a live one. Leaving it work_status done demands a covering test for behaviour that no longer exists; setting it to todo demands a test contract for work nobody will do. The only exits are gaming the record (readiness or change_target) or leaving a false done in the store. Hit on AR-400 slice 2b-i with INF-600g-3 and INF-600g-3-i."
type: reference
category: reference
status: active
created: '2026-10-15'
last_updated: '2026-10-15'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
---

# KI-ACS-20261015-superseded-records-held-to-forward-rules — retiring a done AC has no honest path

> Filed 2026-10-15 during AR-400 slice 2b-i. Index: [ac-store.md](../../ac-store.md).
> Filename severity is the three-level index bucket (`high`); the original grading is the
> `**Severity:**` line below.

- **Severity:** high. The store keeps claiming `done` for behaviour that was deliberately
  deleted, which is the phantom-done failure the store exists to prevent, and the commit
  gates actively block the correction.
- **Status:** **RESOLVED** (ACS-900d-4, branch `feature/acs-900d-4-superseded-retire`). The
  shared predicate `scripts/ac_store/ac_retirement.is_retired` is consulted by check-done-proof
  (all paths), both composite rollups, the test-contract rule and check-ac-limits.
  check-ac-schema now refuses a missing, empty, null or self successor. Verified by retiring
  INF-600g-3 and INF-600g-3-i (superseded by AR-400c-1) in commit `b988ab475`, which passed
  every AC-store gate with no other field edited.
- **Occurrences:** 2 (the same day, two attempts on one commit).
- **Where:** `scripts/ac_store/done_proof.py` (via `check-done-proof`) and the approved-code
  test-contract rule behind `check-ac-schema` (`validate_ac_schema`). Neither consults
  `status: superseded_by` / `superseded_by:`.

**Symptom.** AR-400c-1 deletes `registry_validator.check_skills_invoked_xref`. The two
records that specified it, INF-600g-3 (L2, `done`) and INF-600g-3-i (L3, `done`, no covering
test), should be marked superseded by AR-400c-1. Doing so on 2026-10-15:

1. `status: superseded_by`, `superseded_by: [AR-400c-1]`, `work_status` left `done`:
   `check-done-proof` refuses — `INF-600g-3-i: no '# covers: INF-600g-3-i' tag found` and the
   composite INF-600g-3 is unproven.
2. Same, with `work_status: todo` (the shape of the already-superseded INF-600a-1):
   `check-ac-schema` refuses both — `approved code AC must declare a test contract — add a
   non-empty test_spec`.

INF-600a-1 passes only because it happens to be `readiness: reviewed` and
`change_target: schema`. Copying that onto these records would be editing requirement fields
to slip past a gate, not retiring them.

**Workaround (retired).** Until the fix, the two INF records stayed as they were on `main`
(`active`, `done`), which was false. Both are now retired honestly (see Status).

**Fix direction.** A record whose `status` is `superseded_by` (with a non-empty
`superseded_by:` list naming existing records) is retired: it is exempt from the forward
rules — done-proof, the test-contract requirement, and anything else that asks "is this
built and tested now?" — while the structural rules (schema shape, the superseding ids exist,
parent/child links) still apply. Its `work_status` then means "what it was when retired" and
is never re-litigated. Once fixed, mark INF-600g-3 and INF-600g-3-i superseded by AR-400c-1.

**Trap.** The two refusals look like two unrelated problems with the record and each has a
plausible one-field "fix" (add a test tag, add a test_spec, change readiness). Each one makes
the store say something false. The defect is that neither gate knows what superseded means.
