---
title: "Per-item verdicts: what makes each slow test slow, and what to do"
description: "Every test in the top 40 read and classified as OPTIMISE, RESTRUCTURE, KEEP or DON'T-RUN-ALWAYS, with the specific change named. The BP-1500g family runs 41 identical fixture builds across 39 tests; two files already do it right and show what right looks like."
type: explanation
status: active
created: 2026-10-05
last_updated: 2026-10-05
components:
  - testing_quality
  - build_pipeline
  - ac_store
---

# Per-item verdicts

Part 4 of five. [Part 1](2026-10-05-slowest-tests-and-what-to-do-about-them.md)
gives the ranking.
[Part 2](2026-10-05-slowest-tests-and-what-to-do-about-them-2-the-speed-programmes-own-tests.md)
covers TQ-600a's own tests.
[Part 3](2026-10-05-slowest-tests-and-what-to-do-about-them-3-the-yaml-parser.md)
covers the YAML parse.
[Part 5](2026-10-05-slowest-tests-and-what-to-do-about-them-5-skipping-and-run-once.md)
answers the skipping and run-once questions.

Verdict vocabulary: **OPTIMISE** (cost is incidental, named change available),
**RESTRUCTURE** (cost is real but misplaced), **KEEP** (the cost is the test),
**DON'T-RUN-ALWAYS** (belongs on a slower cadence).

## 1. Cluster A — `unit_tests/suite_performance/`, 1,534.8 s, 27 tests

Mechanism in Part 2 §2: a real child `pytest` per test, each producing the
shared layout from scratch at **48.94 s** because `run_key()` is a fresh UUID
per OS process.

| file | secs | verdict | change |
|---|---|---|---|
| `test_tq_600a_5.py` | 423.2 | **RESTRUCTURE** | seed the child sessions' layout from one pre-built copy (2.07 s each) |
| `test_tq_600a_3_integration.py` | 343.5 | **RESTRUCTURE** | same |
| `test_tq_600a_5_reporting.py` | 302.7 | **RESTRUCTURE** | same |
| `test_tq_600a_1.py` | 267.2 | **KEEP** | asserts the deploy *count*; a pre-warmed layout makes it observe zero |
| `test_tq_600a_1_i.py` | 99.8 | **KEEP** | asserts "a worker with no consumer **produces nothing**" |
| `test_tq_600a_1_multiworker.py` | 98.4 | **KEEP** | asserts "**exactly one** deploy across workers" |

**Addressable: 1,069.4 s across 17 tests. Projected saving ≈ 950 s.**
**KEEP: 465.4 s across 10 tests**, and that is the cost of proving the
coordination contract this entire programme rests on. If any ten tests in this
repo deserve to be expensive, it is these.

Individually, the top of the list resolves cleanly:

- Ranks 1-6, 22 (`tq_600a_5*`, ~547 s) — **RESTRUCTURE.** Each writes 1-3
  generated consumer tests, spawns a child session, and compares the roots the
  fixture handed out. The *routing decision* is `_select_route` reading markers;
  the *layout* is incidental to the assertion. Seedable.
- Ranks 12-17 (`tq_600a_3_integration`, 343.5 s) — **RESTRUCTURE.** These
  compare a layout against itself before and after a consuming test ran. A
  seeded layout is byte-identical to a built one, which is exactly what the
  comparison needs.
- Ranks 7, 9, 10, 18, 19, 24, 25 (`tq_600a_1*`, 465.4 s) — **KEEP.**

## 2. Cluster B — the `BP-1500g` adopter family, 1,007.6 s, 39 tests

Eight files across `unit_tests/portability/` and `unit_tests/build_guards/`,
all driving `_bp1500g1_harness.run_build`.

**The finding: 41 of the ~78 builds in this family are the same build.**
`fresh_scratch_adopter()` (`_bp1500g1_harness.py:201`) creates an empty
directory and runs `build.py --target-dir` into it. Its own docstring says what
it is for:

> Asserts the initial build exits 0 — a non-zero INITIAL build is a fixture
> failure, never a finding for any AC in this build set (every AC here is
> about what happens to adopter content on the **second** and later builds).

So the first build is **declared fixture setup, by the author, in writing**.
Counted call sites of the three setup helpers:

| file | setup builds | tests |
|---|---|---|
| `portability/test_bp_1500g_1.py` | 11 | 10 |
| `portability/test_bp_1500g_2_i.py` | 8 | 7 |
| `portability/test_bp_1500g_1_i.py` | 6 | 6 |
| `portability/test_bp_1500g_1_ii.py` | 4 | 4 |
| `portability/test_bp_1500g_2.py` | 3 | 3 |
| `build_guards/test_bp_1500g_1.py` | 3 | 4 |
| `build_guards/test_bp_1500g_1_i.py` | 3 | 2 |
| `build_guards/test_bp_1500g_2.py` | 3 | 3 |
| **total** | **41** | **39** |

**Verdict: OPTIMISE, all eight files.** Build one golden adopter per
(config, symlink-mode) combination at module or session scope, then
`shutil.copytree` it per test. The adopter layout is the 907-entry consumer
install, ~0.6 s to copy against ~14.8 s to build. **≈ 41 × 14.2 s ≈ 580 s
(~9.7 min)** at the idle build rate.

Three things make this safe and one makes it non-trivial:

- The second build — the behaviour under test — **stays a real build**. Nothing
  about what these ACs assert changes.
- The copy source is a completed, manifest-verified install, so every test
  still starts from a genuine `build.py` product.
- **The cache key must include the build config.** `_scratch_adopter_with_config`
  pre-seeds `skills_config.json` with `shim_strategy: copy` *before* the first
  build, and `fresh_scratch_adopter_with_symlink_disabled` runs with
  `os.symlink` disabled so `auto` degrades to real copies. These produce
  materially different trees. Handing a `copy`-strategy test a symlinked golden
  install would make it pass against a tree that cannot exhibit the bug —
  the exact config-mismatch hazard the prior analysis named. The key is
  available here (config dict + symlink flag + `extra_args` + `build_script`),
  which makes this the *easy* case, not an argument against doing it.

Individual notes on the family's slowest members:

- Rank 23, `build_guards/test_bp_1500g_1_i.py::…preflight_list_and_the_real_removal_list_are_identical` (48.9 s) — **OPTIMISE.** Two builds, one of them fixture setup.
- Rank 28, `portability/test_bp_1500g_1.py::…no_shims_build_is_not_refused…` (46.5 s) — **OPTIMISE, partially.** It builds a control adopter *and* a subject adopter and compares. Both first builds are default-config setup (golden copy); both second builds differ (`--no-shims` on the subject) and stay real. Saves half.
- Rank 29, `portability/test_bp_1500g_2_i.py::…does_not_report_success_as_though_there_were_no_conflict` (45.8 s) — **OPTIMISE.** Same control/subject shape, same half-saving.
- Rank 32, `…repeated_no_flag_builds_are_byte_stable…` (36.4 s) — **KEEP the two behaviour builds, OPTIMISE the setup build.** Three builds total; byte-stability across two consecutive real builds *is* the assertion.

## 3. Cluster C — real-AC-store sweeps, ~560 s

All of these are dominated by the 24.68 s pure-Python YAML parse (Part 3).
**Verdict for the whole cluster: OPTIMISE via `CSafeLoader`**, plus the
per-file notes below. None needs restructuring; none loses an assertion.

| test / file | secs | note |
|---|---|---|
| `test_authored_test_spec_survives_generation.py` | 131.1 / 7 | Already memoises the generator CLI per `(ac_id, ac_root)` and already uses a raw-text pre-filter. **Exemplary.** Remaining cost is the subprocesses it genuinely cannot avoid, at 24.00 s each. |
| `test_acs_100i_7_store_wide_pass.py` (rank 20) | 50.1 | Runs the commit-time AC check over the store. |
| `test_acs_100i_7_i_pass_is_real.py` (rank 31) | 38.8 | "a directory argument actually examines the records under it" — the anti-no-op guard. **KEEP the behaviour, OPTIMISE the parse.** |
| `test_bo_2900g_2.py` (rank 30) | 38.8 | In-process `rglob` + `safe_load` of the whole store. Pure parse cost. |
| `test_derived_test_reachability_floor.py` (rank 54) | 26.9 | Already uses `@pytest.fixture(scope="module")` for the store load. **Good practice; parse-bound anyway.** |
| `test_scan_ac_store_cycle.py` (rank 56) | 26.2 | Real-store cycle check. Parse-bound. |
| `test_tkt_600b_2.py` | 74.4 / 3 | One test really generates a ticket (24 s subprocess). |
| `test_uxp700d2_i_live_store.py` (ranks 53, 57) | 52.9 / 2 | Two tests, each re-deriving the same ready-set over the live store. **Run-once candidate — see Part 5 §2.** |
| `test_uxp_300.py` | 73.4 / 15 | 15 tests, each spawning the product-truth validator over the store. The *bounded fixture* store is identical across most of them. **OPTIMISE: memoise per argv.** |
| `test_uxp_700d_4.py`, `test_uxp_700d_3_i.py`, `test_uxp_700a_1_ii.py` | 96.1 / 3 | One store-scanning subprocess each. |
| `tests/test_prioritize_ac_integration.py` | 61.3 / 4 | Four subprocesses of `prioritize.py`; **two share identical argv** (ranks 37 and 47, 61.2 s between them). **Straight memoisation.** |

## 4. Cluster D — genuinely expensive, already well built

These are the ones to leave alone, and they are worth naming so nobody
"optimises" them later without reading this.

| test | secs | verdict | why |
|---|---|---|---|
| `portability/test_bp_1500d_1_i.py::…one_session_builds_both_layouts…` (rank 21) | 49.7 | **KEEP** | Two real `git archive` + `build.py` builds in one session, to prove one directory record states both halves truthfully. Already behind `@pytest.fixture(scope="module")`. The two builds *are* the test. |
| `portability/test_ge_120c_1.py` (rank 39) | 32.5 | **KEEP** | `setUpClass` builds two real ephemeral working copies and seven tests share them. Already the pattern this analysis recommends elsewhere. |
| `portability/test_bp_900h_4_i.py` (rank 41) | 31.2 | **KEEP** | Four `@pytest.fixture(scope="module")` layouts, each a distinct install shape (renamed package dir, git worktree of a consumer install, self-hosted checkout). Four layouts because there are four shapes, not four copies of one. |
| `unit_tests/test_bp_900g_8*.py` family | not fully measured | **KEEP — explicitly** | Mutates a `copytree` scratch copy of the package, then runs the real build and asserts it **fails**. `test_bp_900g_8.py`'s DECISION HISTORY at line 608 records that `if False and _check_intra_package_closure_guard(package_root)` makes this test — *and only this test* — go red. The failing build is the test. Do not share a layout; do not skip the guard. |
| `unit_tests/test_bp_900a_1.py` (rank 60) | 25.4 | **KEEP** | "deployed AC store is idempotent on rebuild" runs two real builds and diffs. Two builds is the assertion. |
| `portability/test_acd_2100d_3.py` (rank 51) | 27.7 | **KEEP** | Before/after install comparison through the real CLI route; the install is the independent variable. |

## 5. The guard-cache question, settled by measurement

The prior analysis proposed caching `_check_intra_package_closure_guard()`
(11.84 s of a 14.81 s build) keyed on a source fingerprint. That remains
correct and remains **not a skip**: same source, same answer, the guard's only
argument is `package_root`.

Two things this analysis adds:

**It helps the `BP-1500g` family less than it looks, because the golden-adopter
change gets there first.** Those 41 fixture builds all run against unmodified
package source, so they are cache hits — but they are also exactly the builds a
golden copy deletes outright. Same substitution problem the prior analysis
identified between the cache and the migration, now with a third claimant.
Whichever lands first collects; sequence deliberately.

**It does not help `suite_performance` at all**, and the reason is
mis-stated if you assume it would. Those builds are Shape B (self-targeting,
45.36 s measured), where the closure guard is a smaller fraction of a much
larger total. Seeding removes the whole 48.94 s; the cache would remove ~12 s
of it. Seed first.

## 6. Summary of verdicts

| verdict | tests | measured secs | share of top-40 cost |
|---|---|---|---|
| **RESTRUCTURE** | 17 | 1,069.4 | 38% |
| **OPTIMISE** | ~45 | ~1,140 | 41% |
| **KEEP** | ~20 | ~590 | 21% |
| **DON'T-RUN-ALWAYS** | 0 | 0 | 0% |

**Nothing in the top 40 earned a DON'T-RUN-ALWAYS verdict.** That is a finding,
not an omission, and Part 5 §1 defends it — including the one candidate that
came closest and why it still fails the test.
