---
title: "KI-BO-016 — Resolving a one-criterion build set takes ~3 minutes, because every traversal re-parses the entire AC store"
description: "KI-BO-016 — Resolving a one-criterion build set takes ~3 minutes, because every traversal re-parses the entire AC store"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-016 — Resolving a one-criterion build set takes ~3 minutes, because every traversal re-parses the entire AC store

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

> **Renumbered at merge, 2026-08-25: filed as `KI-BO-014`, now `KI-BO-016`.** `main`
> independently minted its own `KI-BO-014` and `KI-BO-015` while this branch was in
> flight. Three acceptance criteria (`BO-2400c-6`, `-6-i`, `-6-ii`) and two commit
> messages cite the old id; they resolve here. Physical position kept where it was
> written rather than moved to the end, so the surrounding merge history stays legible.

- **Severity:** high → medium
- **Status:** the N+1 re-parse is FIXED by **BO-2400c-6** / **-6-i** / **-6-ii**; the entry
  stays open for the residual recorded at the bottom, which has no AC
- **Occurrences:** 1
- **First seen:** 2026-08-24 · **Last seen:** 2026-08-24
- **Where:** `scripts/ac_store/scan_ac_store.py` — `traverse_ac_tree`, against
  `scripts/build_orchestration/fast_lane.py` — `resolve_connected_build_set`

**Kept rather than deleted, deliberately.** This register's policy is to delete a section
when its fix lands. Not done here for two reasons: three acceptance criteria and two commit
messages already cite `KI-BO-014` by id, and deleting it would leave those references
dangling; and the defect as filed — N+1 full parses — is fixed while the cost it was filed
*about* is only reduced. Closing it would read as "resolution is fast now", which is not
what was achieved.

**Symptom.** Phase 2 of every fast-lane run — resolving the connected build set — costs
minutes before any work begins, and the cost grows with the store rather than with the
size of the set being resolved. Resolving a set of **one** criterion is as expensive as
resolving a large one.

**Evidence.** Measured on `main` at `ef8c6343` against the real store of **3,232** AC
files:

```
/usr/bin/time -f "%e seconds" fast_lane.py select_connected \
    --ac BO-2400c-1-i --ac-root docs/acceptance-criteria --exclude-structural-parent
  -> ["BO-2400c-1-i"]
  -> 178.32 seconds
```

Correct answer, one id, just under three minutes. Before the aiming fix (BO-2600b-1) the
same call resolved five ids and exceeded a 120-second probe repeatedly, which was
originally misread as a store-size problem rather than an algorithmic one.

**Mechanism.** `traverse_ac_tree` opens by building a complete id→record index of its own:
it `rglob`s `*.yaml` under the store root and YAML-parses **every** file, on **every
call**. `resolve_connected_build_set` has already built exactly that index before calling
it, and then calls it again once per not-done composite dependency it expands. So a run
pays for N+1 full parses of the whole store where N is the number of composite
expansions — never fewer than two. At roughly 90 seconds per full parse, the tight path
costs ~178s and the wide path (structural-parent walk, pre-fix) costs a multiple of it.
This is also why the exclusion flag looked like a performance fix: it removes traversals,
not just criteria.

**Why it is worse than a slow script.** It is a per-run tax on the lane's whole promise —
"point at one id and get a PR" — paid before the first agent is dispatched, and it scales
with total store size, so it worsens every time anyone authors an AC anywhere in the
repo. It is also invisible as a defect: the command returns the right answer, so nothing
fails and nobody files it. It surfaced only because a probe timed out.

**Fix direction.** Pass the index that already exists. `traverse_ac_tree` should accept an
optional prebuilt id→record map and use it when supplied, with the self-building path kept
for standalone callers; `resolve_connected_build_set` then hands over its own `id_index`
and the run drops to a single parse. Check the other `traverse_ac_tree` call sites in the
same pass — the same re-read is paid by anything that walks the tree in a loop. A
behavioural guard is straightforward: assert the resolver parses the store once for a
multi-expansion set, rather than asserting a wall-clock bound, which would be flaky.

**Outcome, 2026-08-24 — fixed as specified, and the number is worth reading carefully.**
`traverse_ac_tree` gained an optional prebuilt `id_index`; `resolve_connected_build_set`
now builds the index once and passes it. The correctness trap was handled the right way:
it snapshots `dict(id_index)` **before** `_drain_cycles` mutates it and hands the traversal
that undrained view, so cycle-adjacent subtrees still resolve. The self-building path
survives for `goal_to_epic.py`, which holds no index. Guarded by a parse-count assertion,
not a wall clock.

Measured on the same command, `select_connected --ac BO-2400c-1-i
--exclude-structural-parent`, returning the identical `["BO-2400c-1-i"]` throughout:

```
before:  178.32 s
after:    27.10 s  (implementing agent's measurement)
after:    39.11 s  (independent re-measurement, different machine load)
```

Both figures are real; the spread is load, and the honest range is roughly 4.5-6.5×.

**The residual, which is why this entry stays open.** One full parse of 3,232 YAML files
still costs ~30-40 seconds, and that is now the floor. The lane's cold start went from
"unusable" to "noticeable", not to "fast", and it still scales with total store size — so
it will drift back toward a minute as the store grows. Removing the repeated parse was the
filed defect; making a single parse cheap is a different problem and needs a different
answer, most likely a cached or incrementally-maintained index rather than a full YAML
walk per invocation. Not filed as its own entry only because it is the same measurement in
the same place; whoever picks it up should split it out then.

Worth stating plainly so the improvement is not oversold: an operator pointing the lane at
one criterion still waits half a minute before the first agent is dispatched.
