---
title: "KI-TQ-20260901-1310 — The red-baseline gate's 60-second pytest budget silently negotiates the AC's required test shape down to whatever fits"
description: "KI-TQ-20260901-1310 — The red-baseline gate's 60-second pytest budget silently negotiates the AC's required test shape down to whatever fits"
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

# KI-TQ-20260901-1310 — The red-baseline gate's 60-second pytest budget silently negotiates the AC's required test shape down to whatever fits

> One known issue, split out of `docs/known-issues/testing-quality.md` on
> 2026-09-14. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** was high.
- **Status:** **RESOLVED 2026-09-07, on CI evidence rather than on the fix landing.**

  > Fixed by **PR #706** (`fde1e75b`). This entry was deliberately held open after that
  > merge: its claim was that a subprocess-level AC could now clear the gate, and a merged
  > fix is not that claim's evidence — a green CI run is. Both arrived:
  >
  > | PR | `Proof-of-done coverage check (BO-2500b)` |
  > |---|---|
  > | #708 | **pass, 2m03s** |
  > | #694 | **pass, 2m51s** |
  >
  > Neither could have completed under the old 60-second ceiling; #694 is the very PR whose
  > `pytest timed out after 60 s` produced this entry.
  >
  > **The budget is composed, not raised** — a 30 s collection floor charged ONCE, plus
  > 300 s per linked test file. A single larger constant would still ignore the AC's own
  > size and reproduce this defect one notch up, which is what the fix direction above
  > warned against; a test pins that ten files get strictly more than one. A timeout is
  > now also distinguishable from an absent test: a non-nodeid-shaped sentinel is threaded
  > through `verify_done_eligible` and `_verify_composite_eligible` so the reason names the
  > budget and the command instead of reading as "these tests do not exist".
  >
  > The per-file figure is deliberately ~2x the measured worst case. The ~142 s that
  > exposed this was measured on a workstation, and a hosted runner is materially slower
  > for subprocess-heavy work — a value chosen to just clear the local number would have
  > reproduced this defect in CI while looking fixed locally.
  >
  > **A second occurrence, recorded before the fix landed and worth keeping.** Building
  > BP-900h-4 the same budget forced its author to optimise the declaring-file inspector
  > from ~7.1 s to ~1.7 s per invocation to fit. That is a genuine improvement, but the
  > prompt was a gate budget rather than a profiler — the first time this pressure produced
  > an optimisation instead of deleted coverage. Two ACs in one day had their test design
  > bent by this number.
- **Occurrences:** 2
- **First seen:** 2026-09-01 · **Last seen:** 2026-09-07
- **Where:** `scripts/ac_store/done_proof.py:896-908` (`_run_pytest_and_parse`, `timeout=60`),
  consumed by `scripts/build_orchestration/fast_lane.py:1482` (`verify_red_baseline`)

**The gate is fail-closed, and that is not the problem.** State this first because it is the
obvious hypothesis and it is wrong: on timeout `_run_pytest_and_parse` returns `{}`, every
newly-added tag then resolves through `_resolve_tag_outcome` to an unrecognised outcome,
`_classify_outcome_bucket` buckets it **inconclusive** rather than red, the `red` list is
empty, and `verify_red_baseline` returns `gate_passed: false` with reason
`no_red_outcome_among_new_tests`. A timeout cannot fake a red baseline. Verified by reading
the full path, not assumed.

**The problem is what the gate does to the tests instead.** The budget is 60 s for the whole
file, and pytest **collection alone in this repository costs ~30–33 s** before any test body
executes (measured directly during the run below). So the real budget is under 30 s. One
`python scripts/build.py --target-dir <tmp>` subprocess costs ~9.5 s; one in-process
`_check_intra_package_closure_guard()` call costs ~6.7 s. Three subprocess-level tests do not
fit. The gate therefore does not reject bad tests — it rejects *expensive* ones, and the only
way the author can proceed is to make them cheaper.

**Observed, on an AC whose entire point was subprocess-level proof.** Building `BP-900g-8-ii`
on 2026-09-01, the test-writer's first gate run blew the timeout and came back
ERROR/inconclusive. It redesigned from six `build.py` subprocess calls down to exactly one
(final wall time ~42–45 s) and the gate passed. Three of the AC's four `test_spec` entries
were quietly weakened to get there:

| `test_spec` required | What passed the gate |
|---|---|
| Entry 2: three separate builds — unmodified → exit 0, data withheld → fail, module withheld → fail | One build with data **and** module withheld together; the unmodified positive control dropped |
| Entry 3: `build.py` as a subprocess, block then round-trip clear | Direct `compute_intra_package_closure()` call |
| Entry 4: `build.py` as a subprocess, exit 0 | Direct closure-function call |

That AC's own text forbids exactly this: *"a guard exercised only through its own function is
not evidence that build.py consumes its verdict"*, and, of the dropped control, *"state (1) is
not optional — a positive-path build alone cannot tell a working guard from an absent one."*
Two of four tests ended up exercising only the function; the third lost its control.

**Why this is worse than a slow gate.** The trade is invisible downstream. The gate emits
`gate_passed: true` and a red baseline that is entirely genuine — every test really is red for
the right reason — so nothing in the verdict, the sign-off, or the diff records that the
production entry point was dropped to afford it. `pr-reviewer` sees four tests covering four
angles. Only reading the AC's `test_spec` against the test bodies reveals the gap, and the
whole point of the fast lane is that nobody does that by hand.

The direction of the pressure is the sharp part: the budget is cheapest to satisfy by removing
the *subprocess* — which is to say, by removing precisely the part that proves the guard is
reachable in production. The gate systematically selects against reachability coverage, which
is the coverage this repository's own `CLAUDE.md` ("Gate / Workflow ACs — Verify Behaviorally,
Not by Grep") treats as non-negotiable.

**Fix direction.** Do not simply raise the number — that buys time and leaves the incentive
intact. Two changes, in order:

1. **Stop charging collection to the test budget.** ~30 s of a 60 s allowance is spent before
   the first assertion, and it scales with the repository rather than with the AC. Run the
   gate's pytest against the specific file with collection narrowed, or measure and exclude
   collection time, so the budget means what it says.
2. **Make the timeout a distinguishable, recorded outcome rather than a shape constraint.**
   A file that cannot finish should report *why it could not be verified* and surface that in
   the verdict — not hand the author an inconclusive result whose cheapest remedy is a weaker
   test. If a budget must bind, the gate should say "this AC's required shape does not fit"
   loudly enough that a human sees the trade.

**Related.** `KI-TQ-010` is the same family from the other side — nothing asks whether a
passing test is *able* to fail; this entry is about a gate that asks correctly and then makes
the honest answer unaffordable. The `BP-900g-8-ii` build that surfaced it is the fifth
occurrence of `KI-BP-003` (`build-pipeline.md`).

**Register hygiene noted in passing:** this file carries two entries numbered `KI-TQ-012`
(lines ~589 and ~840), describing different defects. Sequential ids collided again, which is
the reason for the datetime id used above.

**Pattern:** a quality gate with a resource budget tight enough that the cheapest way to pass
it is to test less — so the gate's own pressure removes the coverage it exists to guarantee,
and reports success while doing it.

---
