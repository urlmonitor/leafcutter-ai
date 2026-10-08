---
title: "The fast lane cannot complete any store-reading step on a 4458-record store"
description: "fast_lane.py claim was reported as hanging. It is not: it completes in 270.72s and is killed at 120s by the agent harness's default Bash timeout, which the workflow then mis-reports as the performer refusing. Measured growth curve, and who owns the cap."
type: explanation
status: active
created: 2026-09-30
last_updated: 2026-09-30
components:
  - build_orchestration
  - ac_store
---

# The fast lane cannot complete any store-reading step on a 4458-record store

Part 1 of four. [Part 2](2026-09-30-fast-lane-claim-cost-2-where-the-time-goes.md)
locates the cost and tests the hypotheses.
[Part 3](2026-09-30-fast-lane-claim-cost-3-the-phantom-todo.md) covers a second
defect found in the same failure. [Part 4](2026-09-30-fast-lane-claim-cost-4-fix-directions.md)
gives six fix directions with sizes.

**Nothing here has been implemented.** This is analysis written so the work can
be specified as acceptance criteria before any code changes. All timing runs
used a throwaway copy of the store at `/tmp/fl_store_copy` and the id
`NONEXISTENT-999`, so no real AC was claimed or mutated.

Repo `origin/main` at `894bff19`, freshly fetched, 2026-09-30.

## 1. Verdict

**It is not hanging.** `fast_lane.py claim` on the full store completes in
**270.72 s**. It was killed at 120 s by the *agent harness's* default Bash
timeout — not by any budget inside the fast lane, which has none.

The cost is honestly linear, with a constant factor roughly 20x larger than it
needs to be, doubled by a redundant second pass:

| Contribution | Factor | Evidence |
|---|---|---|
| Every record fully YAML-parsed just to read `id` / `work_status` | ~20x | 53.4 s of 54.0 s inside `yaml.safe_load` |
| `yaml.safe_load` uses the **pure-Python** loader although libyaml is installed | ~10x of that 20x | `yaml.__with_libyaml__ == True`; `CSafeLoader` 9.6x faster |
| The whole store is walked **twice** per invocation | 2x | `_load_ac` called 446 times = 2 × 223 |

## 2. The growth curve

One process per row, `--ac-ids NONEXISTENT-999`, `/usr/bin/time`, warm page
cache.

| Root | Records | Bytes (KB) | Wall (s) | s / KB |
|---|---|---|---|---|
| `stakeholder-delivery` | 6 | 6.3 | 0.30 | 0.0063 |
| `code-review` | 29 | 55 | 1.31 | 0.0188 |
| `knowledge-management` | 172 | 569 | 6.45 | 0.0109 |
| `testing-quality` | 223 | 1 821 | 20.64 / 17.43 † | 0.0094 |
| `build-orchestration` | 1 193 | 5 675 | 64.53 | 0.0113 |
| **whole store** | **4 458** | **21 730** | **270.72** | **0.0124** |

† two runs of the identical command; variance on this machine is ±25 %. Both
are reported rather than the more convenient one.

**Linear in bytes, not quadratic.** The clinching pair is the last two rows:
bytes grow **3.83x** and time grows **4.19x**. A quadratic term would have
predicted **14.7x**. Across a 3 400x range of store sizes the s/KB constant
stays inside 0.0094–0.0188 with no upward trend.

Cost tracks **bytes, not record count**: `knowledge-management` (172 records)
and `testing-quality` (223 records) differ by 1.30x in records but 3.2x in
bytes, and time follows the bytes. Mean record is 5.0 KB; largest of all 4 458
is `BP-1500d-3.yaml` at 77 KB.

**One full pass over the whole store costs ~135 s.** That number is used
throughout the other three parts.

### Independence from the id count

| `--ac-ids` | Root | Wall (s) |
|---|---|---|
| 1 id | `testing-quality` | 17.43 |
| 20 ids | `testing-quality` | 13.46 |

Twenty times the ids, no increase — the difference is machine noise, and runs
in the *wrong direction* for a per-id re-walk. The number of store walks is
fixed at two whatever the id count.

## 3. Who owns the 2-minute cap: the harness, not the workflow

This matters because it determines where a fix belongs.

- `grep -n "timeout\|maxTurns\|budget"` over `.leafcutter/workflows/fast-lane-ship.js`
  returns **nothing**. The claim step is a plain `await agent(…, {label: "claim-connected"})`
  with no time bound.
- No `BASH_DEFAULT_TIMEOUT_MS` / `BASH_MAX_TIMEOUT_MS` in any settings file.
- Exit **137 = 128 + 9 = SIGKILL** — an externally imposed kill. Not a Python
  exception, not a lock, not a `MemoryError` (peak RSS was 23 MB).
- Decisive: **the identical command finished in 270.72 s when run with an
  explicit 600 s timeout.** Nothing about the command changed; only the
  harness-side cap did.

### Two consequences

**Every store-reading fast-lane step is over the default cap on this store**,
not just `claim`. `select_connected` measured **151.78 s**;
`check_producibility` is one more full pass (~135 s); `mark_done` is far worse
(Part 2 §4). The lane is not "slow at one step" — on a 4 458-record store it is
structurally unable to complete any store-reading step inside a default 120 s
Bash call.

**The workflow mis-reports the timeout as a refusal.** `fast-lane-ship.js:1099`
treats an unusable claim reply as `!claimUsable` and halts with *"the dispatched
performer either declined to run the repository-mutating claim command or
returned no usable result."* A SIGKILLed command produces no JSON, so it lands
in exactly that branch and is reported as the performer *declining*. This is the
launch-failure-is-not-refusal trap, and any diagnosis has to get past that
message first — it cost real time on 2026-09-30 before the 270 s measurement
was taken.
