---
title: "KI-BO-032 — `/fast-lane-build` silently builds a different batch when the AC you named is not `readiness: approved`"
description: "high — the failure is a green run against the wrong work, with no signal"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-25'
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
- **Status:** **RESOLVED** (`4de20a79`, PR #675 — the orphan `fast-lane-build.js` was
  deleted and `/fast-lane-build` now routes to `fast-lane-ship` with `{ac: $ARGUMENTS}`;
  verified 2026-09-25 by grep for callers plus a live `select_connected` probe and 39
  passing tests — see Resolution)
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

## Resolution

Verified 2026-09-25 on `main` at `d2fe85a1`.

- **The defective runner is gone.** `templates/workflows-js/fast-lane-build.js` was deleted
  in `4de20a79` (PR #675, 2026-09-01 12:30 +0200, "delete the orphaned second fast-lane
  runner"). That commit landed a few hours *before* this KI was filed (`202a8082`, PR #670,
  17:10 the same day), so the entry described a file that was already gone. No file named
  `fast-lane-build*.js` exists in the repo now.
- **No live caller of `select_batch`.** `grep -rln "select_batch\|selectBatch" --include=*.js`
  finds nothing. The function survives in `_fl_selection.py` / `fast_lane.py` as a dormant
  CLI subcommand, and its docstring says that nothing in the shipping lane invokes it.
- **Fix direction half 1 is what shipped.** `/fast-lane-build`
  (`templates/commands/fast-lane-build.md`) is a thin shim:
  `Workflow("fast-lane-ship", { ac: $ARGUMENTS })`. `fast-lane-ship.js` exits with an error
  when no AC id is given ("No AC id was supplied"). It then resolves the named AC through
  `fast_lane.py select_connected --ac ${targetAc}`, which ignores readiness. It has no
  batch fallback.
- **Probe: draft ACs are built, not substituted.** Draft/todo ACs produced these results:
  `select_connected --ac ACD-1200a-8-i` returned a 13-AC set that includes `ACD-1200a-8-i`.
  `--ac ACD-1200` returned its 31-AC subtree. `select_connected --ac TKT-600a-1` (the
  original repro, now `work_status: done`) returns `[]`. That empty result is the clean
  no-op this entry describes, not a substitution.
- **Tests:** `python -m pytest unit_tests/build_orchestration/test_fast_lane_connected.py
  unit_tests/workflows/test_fast_lane_ship_structure.py -q` gave 39 passed.

**Leftover doc staleness (this is not the defect):** `docs/how-to/fast-lane-build.md`
still describes a `select_batch` "Step 1" gate and an "at least one approved AC"
prerequisite. That describes the deleted runner. It misleads readers, but no code path
behaves that way.

---
