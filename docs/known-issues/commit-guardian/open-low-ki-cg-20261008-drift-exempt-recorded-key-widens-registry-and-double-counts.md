---
title: "KI-CG-20261008-drift-exempt-recorded-key-widens-registry-and-double-counts — `check-output-drift` now lets a registry entry excuse content drift on a RECORDED output, contradicting the registry's own charter, and counts that output in both `verified` and `uncomparable`"
description: "medium — a deliberate widening shipped without a design decision; the RESULT line's counts now break ScanResult's documented invariant."
type: reference
category: reference
status: active
created: '2026-10-08'
last_updated: '2026-10-08'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
  - docs/2b_direction_b_output_drift_detection.md
---

# KI-CG-20261008-drift-exempt-recorded-key-widens-registry-and-double-counts — `check-output-drift` now lets a registry entry excuse content drift on a RECORDED output, contradicting the registry's own charter, and counts that output in both `verified` and `uncomparable`

> One known issue, filed while retrofitting acceptance criteria for PR #1013.
> Index: [commit-guardian.md](../commit-guardian.md). Filename severity is the
> three-level index bucket (`low`); the original grading is the `**Severity:**`
> line below.

- **Severity:** medium — no wrong verdict today, but two documented contracts are now false and nothing forces the open decision to be made.
- **Status:** open — the behaviour is specified by `BP-100k-3-iv`, and its limits are pinned by `BP-100k-3-v` (per key, ground-gated) and `BP-100k-3-vi` (missing/unreadable never excused). The counting question is now recorded in [ADR-068](../../architecture/adrs/ADR-068-drift-exempt-gets-its-own-result-column.md) (status **Proposed**, 2026-10-09), which recommends a separate `drift_exempt` field and RESULT column. Defect 2 below stays open until that ADR is accepted and implemented.
- **Occurrences:** 1 · **First seen:** 2026-10-05 · **Last seen:** 2026-10-08
- **Where:** `templates/scripts/commit_guardian/check_output_drift.py`, the Pass 2 hash-mismatch branch (`_reconcile_recorded`); the counting contract is `ScanResult` in `templates/scripts/commit_guardian/_drift_exemptions.py`; the charter is `__drift_gate_exemption_registry_doc` in `templates/scripts/commit_guardian/commit_guardian.json`.

**What changed.** PR #1013 (merged 2026-10-05 as `2d895308`) made Pass 2 consult
`drift_gate_exemption_registry` before recording a hash mismatch as drift. A recorded
output whose hash no longer matches, but which has a grounded registry entry, now
prints `DIRECT-DRIFT: EXEMPT <key> ground=<g>` and does not block. The change was a
hand patch with no AC behind it; the three ACs above were retrofitted on 2026-10-08.

**Defect 1 — the registry can now excuse what its charter says it must not.** Until
#1013, Pass 1 (unrecorded outputs) and Pass 2 (recorded outputs) worked on disjoint key
sets by construction, so a registry entry could only ever excuse an output the build
never recorded: a registration question. The registry's charter says it "is not a way
to silence a finding the gate got right." Now the *same* entry also excuses that key's
**content drift** once `build.py` starts recording the path. Nothing warns the author of
an entry that it has acquired this second meaning. No live entry names an
`output_mappings` key today, so there is no wrong verdict yet — but all nine current
entries carry the latent power.

**Defect 2 — the RESULT line's counts break `ScanResult`'s documented invariant.** A
drift-exempt output is hash-compared, so it increments `verified`; it is then also
counted in `uncomparable` (and so in the derived `exempt` field). `ScanResult`'s
docstring says this never happens: "verified ... Never includes uncomparable artifacts
(AC-4)", and `uncomparable` is "artifacts neither found in the manifest ... nor validly
declared exempt" — a drift-exempt key **is** in the manifest. Reproduced with three
recorded keys (one clean, one exempt-drifted, one unexempt-drifted):

```
check-output-drift: RESULT verified=3 uncomparable=1 exempt=1 gaps=0 drifted=1 ...
```

Three artifacts, four bucket memberships. The `uncomparable == gaps + exempt` identity
that consumers compute `exempt` from still holds, which is why nothing broke.

**Candidate fix.** A separate `drift_exempt` field on `ScanResult` plus its own RESULT
column, appended last. That is exactly how `unreadable` was added under adversarial
finding B-2, for the same "belongs in no existing bucket" reason. It changes a parsed
output contract, so it needs an ADR first. If the ADR moves these keys out of `exempt`,
`BP-100k-3-iv`'s `exempt=N` clauses and their tests in
`unit_tests/commit_guardian/test_drift_exempt_recorded_key.py` must change in the same
commit — `BP-100k-3-iv`'s notes already say so.

**Not in scope here.** Whether the widening itself should be reverted. `BP-100k-3-v`
deliberately makes any further widening (glob or prefix keys, a global switch, reading
the raw registry) retire a named AC in the open, so the current form is at least bounded.
