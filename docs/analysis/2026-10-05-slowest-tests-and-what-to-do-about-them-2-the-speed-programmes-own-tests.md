---
title: "Why the speed programme's own tests are the slowest in the suite"
description: "TQ-600a's 27 tests cost 1,535s, 29% of measured time, because each spawns a child pytest session whose run key is a fresh UUID, so the cross-process cache the fixture exists to provide is defeated 23 times. The production code already has the seam that fixes 17 of them."
type: explanation
status: active
created: 2026-10-05
last_updated: 2026-10-05
components:
  - testing_quality
  - build_pipeline
---

# Why the speed programme's own tests are the slowest in the suite

Part 2 of five. [Part 1](2026-10-05-slowest-tests-and-what-to-do-about-them.md)
gives the ranking.
[Part 3](2026-10-05-slowest-tests-and-what-to-do-about-them-3-the-yaml-parser.md)
covers the YAML parse.
[Part 4](2026-10-05-slowest-tests-and-what-to-do-about-them-4-per-item-verdicts.md)
gives per-item verdicts.
[Part 5](2026-10-05-slowest-tests-and-what-to-do-about-them-5-skipping-and-run-once.md)
answers the skipping and run-once questions.

## 1. The number

| file | secs | tests |
|---|---|---|
| `test_tq_600a_5.py` | 423.2 | 5 |
| `test_tq_600a_3_integration.py` | 343.5 | 7 |
| `test_tq_600a_5_reporting.py` | 302.7 | 5 |
| `test_tq_600a_1.py` | 267.2 | 5 |
| `test_tq_600a_1_i.py` | 99.8 | 3 |
| `test_tq_600a_1_multiworker.py` | 98.4 | 2 |
| **total** | **1,534.8 s** | **27** |

**~25.6 minutes, 29.1% of measured time, in 0.5% of the measured tests.** The
programme that exists to delete the suite's build subprocesses is the single
largest consumer of build subprocesses in the suite.

This is worth saying plainly and then not dwelling on, because the interesting
part is *why*, and the why is not carelessness. These are good tests. They
prove cross-process behaviour, and cross-process behaviour can only be proven
by real processes.

## 2. The mechanism, read out of the code

Every one of these tests calls `run_child_session()`
(`unit_tests/suite_performance/_test_helpers_tq_600a_5.py:44`), which does:

```python
cmd = [sys.executable, "-m", "pytest", str(children_dir)]
…
return subprocess.run(cmd, cwd=str(_WORKTREE_ROOT), env=env, …)
```

A real child `pytest`, in a fresh OS process, over a generated test file. The
child requests the `shared_reference_layout` fixture, which lands in
`get_or_produce_shared_layout()`. That function is cached three ways — module
globals, an `fcntl.flock`, and an on-disk published record — and **all three are
scoped by `run_key()`**:

```python
# scripts/suite_performance/_shared_layout_coordination.py:66
def run_key() -> str:
    xdist_uid = os.environ.get("PYTEST_XDIST_TESTRUNUID")
    if xdist_uid:
        return xdist_uid
    if _fallback_run_key is None:
        _fallback_run_key = uuid.uuid4().hex
    return _fallback_run_key
```

Outside xdist, the key is **a fresh UUID per OS process**. Each child session
is a new OS process, so each gets a new key, a new `run_base_dir()`, and
therefore produces the layout from scratch. The cache is not broken; it is
correctly scoped to a run, and each child session genuinely *is* a different
run.

**What one production costs, measured today in-process:**

| step | time | size |
|---|---|---|
| `shutil.copytree` of the source tree (producer's ignore set) | **3.58 s** | 11,651 entries, 96.0 MB |
| self-targeting `build.py --target-dir <copy>` | **45.36 s** | — |
| **total production** | **48.94 s** | |
| `shutil.copytree` of the *resulting* layout | **2.07 s** | 12,489 entries, 106 MB |
| **ratio** | **23.7x** | |

(Probe: `/home/henzeh/tq600a1-backup/an_probe_sharedlayout.py`, results in
`an_probe_results.jsonl`. Taken under load, so 48.94 s is an upper bound; the
23.7x is a within-run ratio and holds.)

Now count productions per test. `test_tq600a_5_a_test_declared_a_reader_…`
writes three consumer tests into the child session: a direct caller, a declared
reader, and an undeclared control. Direct + reader share one production; the
undeclared control gets a private copy via `_produce_private_copy()`, which is
*the same copytree-plus-self-targeting-build*. **Two productions, ~98 s.**
Measured: 92.5 s. The model matches the measurement across the file.

Across the six files, roughly **23 full productions** are executed to run 27
tests.

## 3. The trap this exposes for the migration itself

`_produce_private_copy()` (`pytest_shared_reference_layout.py:224`) documents
its own cost as:

> mirroring the status quo every non-migrated test already pays for itself
> today (e.g. `unit_tests/test_bp_900g_8*.py`'s own build.py invocation).

**It does not mirror it. It is 3.3x worse.** The status quo for those tests is
`build.py --target-dir <empty tmp>` — Shape A, **14.81 s** measured in the
prior analysis. `_produce_private_copy()` copies the whole repository and then
runs `build.py --target-dir <that populated copy>` — Shape B, **48.94 s**
measured here.

The consequence is concrete and currently unnoticed: **routing an existing
own-build test onto the TQ-600a mutator marker would make it slower, not
faster.** The migration's 44 shape-B/C/F files are fine — they move to a shared
layout or a copy. But any test that ends up `shared_layout_mutator` and keeps
its build pays 48.94 s where it used to pay 14.81 s. With 20 shape-A files
that is a potential **~680 s regression** introduced by a speed migration.

This is the same defect class the prior analysis flagged for config mismatch:
the route looks like the thing it replaces and is not. It belongs in the
migration's acceptance criteria as a measured bound — "a test moved onto the
mutator route must not get slower" — not as an assumption.

## 4. The seam that fixes 17 of the 27 tests

**The production code already supports it, and the tests already pass an env
dict.** `run_key()` prefers `PYTEST_XDIST_TESTRUNUID` when set; `_produce()`
publishes to `run_base/published` and `check_published()` returns it on any
later call with the same key. So a parent test module can produce the layout
**once**, then set that env var in every child session's environment, and every
child resolves the same `run_base`, finds the published layout, and does zero
work.

`run_child_session()` already builds `env = dict(os.environ)` and applies
`env_overrides`. **No production-code change is required for the shared route.**

For the private-copy route a one-line production change is needed: honour a
seed directory (say `LEAFCUTTER_SHARED_LAYOUT_SEED_DIR`) in
`_produce_private_copy()` and `_produce()`, copying from it (2.07 s) instead of
copy-source-plus-build (48.94 s). A copy of a completed layout is byte-identical
to what the build would have produced, writable, and owned by one caller —
which is precisely and only what the private route promises.

**Which tests may take the seed, and which must not.** The split is not
"readers vs mutators"; it is **whether the number of real deploys is the
subject of the assertion**.

| file | subject | seedable? |
|---|---|---|
| `test_tq_600a_1.py` | "a selection of consumers deploys the package **once**" | **No — KEEP** |
| `test_tq_600a_1_i.py` | "a worker with no scheduled consumer **produces nothing**" | **No — KEEP** |
| `test_tq_600a_1_multiworker.py` | "several workers still execute **exactly one** deploy" | **No — KEEP** |
| `test_tq_600a_5.py` | *which root* a marker routes to | **Yes** |
| `test_tq_600a_5_reporting.py` | routing counts and node-id reporting | **Yes** |
| `test_tq_600a_3_integration.py` | layout integrity comparison before/after | **Yes** |

The first three count `deploy_executed` signals. Hand them a pre-warmed layout
and they observe zero deploys and go red — correctly, because for them the
deploy count *is* the assertion. They stay on real builds, 465.4 s, and that
cost is the test.

The other three assert nothing about how the layout came to exist. They need
*a* real deployed layout (seed copy: byte-identical), *a* distinct private root
(seed copy to a different path: distinct), and *the routing decision* (unchanged
— `_select_route` reads markers, never the producer). **1,069.4 s across 17
tests is addressable.**

Sizing it: ~23 productions become ~6 (the three KEEP files' real deploys) plus
one seed build plus ~16 copies. At the measured rates, **≈ 1,069 s → ≈ 120 s, a
saving of roughly 950 s (~16 min)** on an idle local run — larger than the
entire Part 3 §6 estimate of the ten-minute-target set, and from a population
that analysis never looked at.

## 5. The honest objection, and the answer

**"You are testing the fixture with the fixture."** Seeding means the child
session's layout came from a copy this test harness made, not from a build the
child ran. If `build.py` broke, would these 17 tests notice?

No — and they do not notice today either. That is not their job. The three
`TQ-600a-1` files, which stay on real builds, are the ones that would notice,
and so are the 20 shape-A build-guard tests, and so is every CI job that runs
`build.py` before pytest. The 17 seedable tests assert *routing*, *reporting*
and *integrity comparison*. A seed that is byte-identical to a built layout
changes nothing any of them can observe.

The guard that makes this safe is cheap and should be an AC: **the seed
producer must fail loudly if the seed is absent, incomplete, or built with a
non-default config** — the same `.build_manifest.json` completeness check
`_produce()` already performs before publishing, plus the config fingerprint
the prior analysis identified as the copy route's real hazard. Serving a
mismatched tree silently is the one outcome worse than the current slowness.

## 6. What this says about the programme

TQ-600a is correct and should finish. Nothing here argues otherwise.

But the ordering has been wrong in a way the measurements now make visible.
The programme has **zero real consumers** — `shared_layout_reader` appears in
seven files, all its own tests — and those seven files are simultaneously the
most expensive thing in the suite. So the current state is the worst of both:
all of the cost of the machinery, none of the benefit, and a measurement
surface (`declared_mutator_count` / `undeclared_count`) that reads clean at 0%
coverage.

Fixing the fixture's own tests is not a detour from the migration. It is the
cheapest 16 minutes available, it needs no migration to land first, and it
removes the embarrassment of the speed programme being the slowest thing in
the suite while the migration it gates is still at zero.
