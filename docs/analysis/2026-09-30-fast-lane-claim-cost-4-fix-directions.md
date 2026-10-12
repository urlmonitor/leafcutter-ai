---
title: "Six fix directions for the fast-lane store cost, with sizes and risks"
description: "Directions, not designs, sized XS to M: CSafeLoader, a shared per-process index, dropping YAML parsing for an id-only lookup, an explicit lane budget that distinguishes timeout from refusal, reconciling the phantom-todo and closing its class, and failing closed on done."
type: explanation
status: active
created: 2026-09-30
last_updated: 2026-09-30
components:
  - build_orchestration
  - ac_store
---

# Six fix directions, with sizes and risks

Part 4 of four. [Part 1](2026-09-30-fast-lane-claim-cost.md) has the verdict and
the growth curve, [Part 2](2026-09-30-fast-lane-claim-cost-2-where-the-time-goes.md)
locates the cost, [Part 3](2026-09-30-fast-lane-claim-cost-3-the-phantom-todo.md)
covers the second defect.

**These are directions, not designs. Nothing here has been implemented, and no
acceptance criteria exist yet for any of it.** The intended next step is to take
these through `/plan-feature` so the work is specified as ACs before any code
changes — this repo's rule is that new work starts with acceptance criteria, not
with a ticket or a patch.

Ordered by value per unit of work.

## F1 — Switch the store walks to `CSafeLoader` *(XS: ~10 lines, hours)*

libyaml is already installed (`yaml.__with_libyaml__ == True`). Change `_load_ac`
in `scan_ac_store.py` and `_build_ac_status_map` in
`_done_proof_phase_helpers.py` to `yaml.load(fh, Loader=yaml.CSafeLoader)`, with
a guarded fallback to `SafeLoader` where the C extension is absent — consumer
installs may lack it.

Measured **9.6x**: `claim` 270.7 s → ~29 s. Lowest risk, highest leverage, and it
benefits every AC-store tool in the repo rather than just the fast lane.

**Risk to test honestly:** `CSafeLoader` is stricter on some malformed input. Run
it over all 4 458 real records and diff the parsed output against `SafeLoader`
before believing it is a drop-in. Synthetic fixtures will not surface this — the
store's real content is the test.

## F2 — One shared index per process *(S: ~1 day)*

Pass the index built by the first lifecycle helper into the second rather than
rebuilding it. Minimal version: give `claim`'s branch in `main()` a single
`_build_ac_id_to_path_index` call and add an optional `id_to_path=` parameter to
`filter_already_claimed` and `claim_build_set`.

**The precedent already exists** — `traverse_ac_tree` takes exactly such an
optional `id_index`, added under BO-2400c-6. This extends a decision the module
has already made rather than introducing a new pattern.

Halves `claim`; combined with F1 gives **270.7 s → ~14 s**. The same parameter on
`verify_done_eligible` is what fixes `mark_done`'s O(ids × records), and matters
more there than here.

## F3 — Stop parsing YAML for an id-only lookup *(M: 2-3 days)*

`_build_ac_id_to_path_index` needs exactly one field: `id`. A line-scan for a
column-0 `^id:` does that in **0.79 s** over the whole store — 343x.

**This is the same technique `_update_ac_work_status` already uses** on the write
side: a targeted column-0 line edit, chosen precisely so it does not round-trip
the document. Applying it on the read side is consistent with a decision this
module has already taken.

`filter_already_claimed` and `check_no_stale_todo` need one more field
(`work_status`), also column-0.

**Risks to handle:** multi-document files, a quoted or block-scalar `id`, and the
143-of-3012 records that carry no `work_status` key at all — documented in
`_update_ac_work_status`'s own docstring. Cross-validate against a full
`CSafeLoader` pass over all 4 458 real records, not synthetic fixtures.

## F4 — Give the lane an explicit, honest budget *(S: ~1 day)*

Two separate problems, both in `fast-lane-ship.js`:

**No budget exists.** The workflow passes no timeout, so it silently inherits
whatever the harness happens to default to. Set an explicit one per
store-reading step, sized from the measured costs in Part 1, so the lane's limit
is a stated decision rather than an accident of the host.

**A timeout is reported as a refusal.** The `!claimUsable` halt at line 1099
cannot distinguish "the performer declined" from "the command was SIGKILLed at
120 s". Have the claim agent report the exit status, and branch 137 / 124 into a
distinct "the claim command exceeded its budget" halt. This is the same class of
defect the file already guards elsewhere — its comments at lines 808-835 are
about not mistaking a probe's silence for evidence. The guard is simply missing
on the time axis.

## F5 — Reconcile `TQ-600a-1`, and close the class *(S for the record; M for the gate)*

**The record.** `TQ-600a-1` is implemented, merged (PR #941 / `e2d9cd0d`),
covered by three green `# covers:`-tagged test files, and documented in
`CLAUDE.md` — yet reads `todo`. Until it reads `done`, every fast-lane run aimed
at `TQ-600a-3` or anything else depending on a-1 keeps dragging merged work into
its build set.

Assess `TQ-600a-1-i` and `TQ-600a-1-ii` on their own evidence rather than
flipping them alongside the parent — see Part 3 §6.

**The class.** Nothing currently fails when a merged AC keeps `work_status:
todo`; `check_done_proof` catches only the opposite direction. A phantom-todo
sweep — non-empty `implemented_by` pointing at files that exist on `main`, plus
passing `# covers:`-tagged tests, plus still `todo` — would have caught this and
is the durable fix.

## F6 — Make `filter_already_claimed` fail closed on `done` *(XS: ~5 lines)*

Independent of whether a-1's status is corrected. A `done` AC arriving in a build
set is never something to claim and rebuild; today it is silently claimed.
Partition it into a third bucket (`excluded_done`) and refuse, rather than
letting it fall through the `else`.

This closes the TOCTOU window between `select_connected` and `claim` — two
separate processes, minutes apart — where a concurrent run can legitimately
finish an AC that this run already resolved.

## Suggested grouping

F1, F5 and F6 are all XS/S and together make the lane usable again: the speedup,
the record that keeps re-dragging merged work, and the guard that stops a `done`
AC being rebuilt. F4 is worth pairing with them because the refusal-vs-timeout
conflation is what made this failure expensive to diagnose in the first place.

F2 and F3 are the deeper fixes and carry the real risk — F3 especially, where
the 143 records with no `work_status` key and the quoting edge cases need
deliberate handling. They are better specified as their own ACs with their own
red tests than bundled into a performance pass.

## Reproduction

Store copy — never the live store:

```
cp -r <repo>/docs/acceptance-criteria /tmp/fl_store_copy
```

Timing (any subset root; needs an explicit timeout above 120 s or the harness
kills it):

```
/usr/bin/time -f "%e s" python <repo>/scripts/build_orchestration/fast_lane.py \
    claim --ac-ids NONEXISTENT-999 --ac-root /tmp/fl_store_copy
```

Profile:

```
python -m cProfile -o /tmp/fl_profile_223.prof \
    <repo>/scripts/build_orchestration/fast_lane.py \
    claim --ac-ids NONEXISTENT-999 --ac-root /tmp/fl_store_copy/testing-quality
```

Key source locations:

- `scripts/build_orchestration/fast_lane.py:511-546` — the `claim` dispatch, two lifecycle calls back to back
- `scripts/build_orchestration/_fl_lifecycle.py:38-62` — `_build_ac_id_to_path_index`, the full-store walk
- `scripts/build_orchestration/_fl_lifecycle.py:438-456` — `filter_already_claimed`'s `in_progress`-only test
- `scripts/build_orchestration/_fl_lifecycle.py:326-337` — `claim_build_set`'s `in_progress`-only skip
- `scripts/ac_store/scan_ac_store.py:115-139` — `_load_ac`, the `yaml.safe_load` site
- `scripts/ac_store/_done_proof_phase_helpers.py:77-116` — `_build_ac_status_map`, the per-id walk behind `mark_done`
- `scripts/build_orchestration/fast_lane.py:558-566` — `mark_done`'s per-id loop
- `.leafcutter/workflows/fast-lane-ship.js:1051-1110` — the claim dispatch and its refusal-vs-timeout conflation
