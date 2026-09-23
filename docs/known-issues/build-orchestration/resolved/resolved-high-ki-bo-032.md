---
title: "KI-BO-032 — `/fast-lane-build` silently builds a different batch when the AC you named is not `readiness: approved`"
description: "high — the failure is a green run against the wrong work, with no signal"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-23'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-032 — `/fast-lane-build` silently builds a different batch when the AC you named is not `readiness: approved`

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high — the failure is a green run against the wrong work, with no signal
- **Status:** **RESOLVED 2026-09-23** — see the dated closure note at the foot of this entry.
  Original line, preserved: open
- **Occurrences:** 1
- **First seen:** 2026-09-01 · **Last seen:** 2026-09-01
- **Where:** `templates/workflows-js/fast-lane-build.js` (hardcoded `select_batch`
  invocation) against `fast_lane.py`'s `select_batch`, which filters on `_is_approved`

**Symptom.** An operator says "fast-lane `TKT-600a-1`". `fast-lane-build.js` takes no AC
argument at all — it hardcodes `select_batch --ac-root <root> --limit <N>`, which returns
"the next N **approved** unimplemented ACs by priority". The named AC is never consulted.
If it is not `readiness: approved`, the lane builds five unrelated ACs and reports success.

Measured on the real store at `931b4beb4`:

```
select_batch    --limit 5        -> ["ACS-500g-6-i", "BP-900b-3", "BP-900g-10-i",
                                     "BP-900g-10-ii", "BP-900g-8-ii"]
select_connected --ac TKT-600a-1 -> ["TKT-600a-1"]
```

Zero overlap. Nothing in the run says the requested AC was dropped, because nothing in the
run ever received it.

**Why the readiness field cannot be relied on to prevent this.** `TKT-600a-1` has been
`readiness: draft` for its entire history — including the whole period it was
`work_status: done`. So "draft" here does not mean "not ready to build"; it means nobody
ran the approval gate. Any AC that reached done outside `/plan-feature` is in the same
state, and every one of them is invisible to `select_batch` while looking perfectly
buildable to an operator reading the store.

**Fix direction.** Two independent halves, both cheap:

1. Give `fast-lane-build.js` the `ac` argument its sibling already has. `fast-lane-ship.js`
   accepts `args.ac` and resolves via `select_connected` (dependency-ordered,
   **readiness-agnostic**) — the correct behaviour already exists one file over.
2. Failing that, make the silence impossible: when the caller names an AC that
   `select_batch` did not return, refuse rather than substitute. A lane that cannot build
   what was asked for should say so, not build something else and exit 0.

**Workaround until fixed.** Use `/fast-lane-ship` with `{ac: "<ID>"}` for any targeted
single-AC build, and confirm the resolution before dispatching:

```
python3 <root>/.leafcutter/scripts/build_orchestration/fast_lane.py select_connected --ac <ID> --ac-root <store>
python3 <root>/.leafcutter/scripts/build_orchestration/fast_lane.py check_producibility --ac-ids <ID> --ac-root <store>
```

An empty `select_connected` result is a clean no-op in the lane, so checking first is the
difference between a diagnosis and a wasted run.

**Related.** `KI-BP-20260826-1331` — a different fast-lane false-green (install phase), not
this one. The shared shape is worth naming: the fast lane's failure mode is consistently a
**successful run against the wrong inputs**, which no gate downstream of input selection can
detect.

**Closed 2026-09-23.** Re-verified against current code, not this entry's narrative.
`templates/workflows-js/fast-lane-build.js` — the file this entry names as hardcoding
`select_batch --limit N` and dropping the named AC — no longer exists. It was deleted
2026-09-01 in `4de20a79` ("refactor(build-orchestration): delete the orphaned second
fast-lane runner", PR #675 — itself closing the separate `KI-BO-006`; unrelated to the
ACD-2100 epic). `/fast-lane-build`'s command template (`templates/commands/fast-lane-build.md`)
is now a thin shim that passes the named AC straight through:
`Workflow("fast-lane-ship", { ac: $ARGUMENTS })`.

`fast-lane-ship.js:864-866` resolves that id via
`select_connected --ac ${targetAc} --ac-root ${acStoreRoot} --exclude-structural-parent` —
exactly Fix-direction #1 ("Give `fast-lane-build.js` the `ac` argument its sibling already
has"). `scripts/build_orchestration/fast_lane.py`'s own module docstring confirms the
producibility check downstream of that resolution is "positive-declaration-only ... an
unannotated record defaults to producible and readiness/priority/req_status/status are never
read" — genuinely readiness-agnostic, not merely re-labelled.

Confirmed behaviorally:
`python -m pytest unit_tests/workflows/test_bo2400c1v_orphan_runner_removal.py unit_tests/workflows/test_bo2500d_gate_retirement.py unit_tests/workflows/test_fast_lane_ship_structure.py -q`
→ 48 passed (2026-09-23).

This fix predates the ACD-2100 epic (PR #675, 2026-09-01) and is unrelated to it, but the
entry itself was never updated to reflect it.

---
