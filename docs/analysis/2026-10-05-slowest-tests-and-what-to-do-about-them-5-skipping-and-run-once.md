---
title: "Can we skip some? and where do N tests recompute one answer?"
description: "24 tests are named _MANUAL and the README says they are excluded from the default run. They are not — there is no mechanism, and a default collection picks up all 24. That is the only defensible skipping candidate, and the better answer is to make it unnecessary. Five run-once seams, ranked."
type: explanation
status: active
created: 2026-10-05
last_updated: 2026-10-05
components:
  - testing_quality
  - build_pipeline
  - ac_store
---

# Can we skip some, and where do N tests recompute one answer?

Part 5 of five. [Part 1](2026-10-05-slowest-tests-and-what-to-do-about-them.md)
gives the ranking.
[Part 2](2026-10-05-slowest-tests-and-what-to-do-about-them-2-the-speed-programmes-own-tests.md)
covers TQ-600a's own tests.
[Part 3](2026-10-05-slowest-tests-and-what-to-do-about-them-3-the-yaml-parser.md)
covers the YAML parse.
[Part 4](2026-10-05-slowest-tests-and-what-to-do-about-them-4-per-item-verdicts.md)
gives per-item verdicts.

## 1. Skipping — one real candidate, and it is already half-built

### 1.1 The candidate: `_MANUAL`, a convention with no mechanism

`scripts/suite_performance/README.md:57-59` states:

> Most are suffixed `_MANUAL` (they pay a real ~60s deploy) and **are excluded
> from the fast default run**; only the boundary test that mocks-but-forwards
> `subprocess.run` runs by default.

**They are not excluded. There is no exclusion mechanism anywhere.** Verified
three ways:

- `pytest.ini` registers two markers (`shared_layout_reader`,
  `shared_layout_mutator`). Neither is `manual`. `addopts` carries no `-k`, no
  `-m`, no `--deselect`.
- `grep -rn "_MANUAL"` across `scripts/` and `.github/` returns exactly one
  hit: the README sentence above.
- A plain collection proves it:
  `pytest unit_tests/suite_performance/ --collect-only -q` collects
  **31 tests, 24 of which have `_MANUAL` in the node id.**

So the decision to run these on a slower cadence **was already taken, by the
author, and written down** — and then every run since has executed all 24
anyway. This is the fifth documented-defence-that-is-a-no-op in this
repository, after `feedback_categories.yaml`'s wrong path, the AC validator's
bare-directory glob, the stale `origin/main` merge audit, and
`--strict-markers` inside `addopts`. The pattern is now frequent enough to be
predictable: **a convention expressed only in prose is not a mechanism, and in
this repo it will be believed for months.**

### 1.2 Why I still do not recommend skipping them

Being sceptical as instructed, here is what would reach `main` undetected.

If the TQ-600a routing fixture regresses, **the symptom is not a red test.**
It is one of two silent outcomes:

- **A mutator is handed the shared root.** It writes into the one layout every
  reader shares. The reader tests then fail *somewhere else*, nondeterministically,
  depending on execution order — and under sharding, in a different shard each
  run. That is the hardest class of failure this suite could produce, and the
  tests that detect it directly are precisely the `_MANUAL` ones
  (`test_tq600a_5_a_test_declared_a_mutator_receives_its_own_copy_MANUAL`,
  `…_a_test_declared_a_reader_receives_the_shared_layout_MANUAL`).
- **A reader is handed a private copy.** Nothing fails. The suite just gets
  ~49 s slower per affected test, silently, which is the exact cost the
  programme exists to remove and the exact thing the existing meter cannot see
  (`declared_mutator_count` / `undeclared_count` read clean at 0% coverage).

Both failure modes are invisible by construction. **A skipped test is a
coverage hole that will not announce itself** — and here the regression it
guards against will not announce itself either. Two silences multiply.

### 1.3 What I recommend instead

**Make the question moot.** Part 2 §4 shows 17 of the 27 can be seeded down
from ~49 s to ~2 s each. A test that costs 2 s does not need a cadence policy.
Do that first; it removes the pressure that makes skipping attractive.

**If a cadence is still wanted afterwards**, the only defensible split is the
10 KEEP tests (`test_tq_600a_1.py`, `_1_i.py`, `_1_multiworker.py`, 465.4 s),
and it must be a **path-filtered job, not a blanket deselect**:

| | |
|---|---|
| **always run on PR** when the diff touches | `scripts/suite_performance/**`, `pytest.ini`, `scripts/build.py`, `scripts/build_phases.py`, `scripts/build_helpers.py`, `unit_tests/suite_performance/**` |
| **otherwise** | nightly on `main` |
| **coverage lost in the gap** | the deploy-count collapse contract: "N consumers → exactly one deploy", "a worker with no consumer produces nothing", "several xdist workers still execute exactly one deploy" |
| **what could reach `main` undetected** | a change elsewhere that makes the layout be produced more than once per run — e.g. a new plugin that resets module globals, a `tempfile.gettempdir()` change, an env var collision clearing `PYTEST_XDIST_TESTRUNUID`. None are in the trigger paths above. |
| **when regained** | next nightly, ≤24 h |
| **how a failure is attributed** | by bisecting over a day of merges, which is materially worse than per-PR attribution |

That last row is the honest cost and it should be stated to whoever decides.
**The trigger-path list is the weak point, not the cadence.** Any
path-filtered job is a bet that you enumerated every file that can break the
thing — and the two most expensive bugs in this document's bibliography
(`done_proof.py`'s missing deploy entry, the inert `--strict-markers`) were
both caused by an interaction *outside* the obvious file set.

**If this is adopted, the mechanism must be a registered marker, not the name
suffix.** `strict_markers = true` is correctly set as an ini key, so a
registered `@pytest.mark.slow_deploy` is mechanically enforced and a
misspelling fails collection. A `-k "not _MANUAL"` filter is a string match
with no strictness and would re-create the problem one level up.

### 1.4 Skipping candidates I reject outright

- **`unit_tests/test_bp_900g_8*.py` and the mutate-build-assert-failure
  family.** The failing build *is* the test. `test_bp_900g_8.py`'s DECISION
  HISTORY at line 608 records the experiment: disconnecting the closure guard
  makes this test — and *only* this test — go red. Skipping it, or skipping
  the guard, removes the sole detector for a defect class `CLAUDE.md`
  documents **seven** live instances of. Caching the guard's verdict keyed on
  a source fingerprint is fine; skipping is not.
- **The `BP-1500g` family.** These reproduce KI-BP-009, a *shipped data-loss
  bug* in which `build.py` destroyed adopter-authored content. The cost is
  real and Part 4 §2 halves it honestly. Deferring it off the PR path means a
  data-loss regression merges and is found by an adopter.
- **The AC-store gates** (`test_acs_100i_7*`, `test_derived_test_reachability_floor`,
  `test_bo_2900g_2`). Part 3 makes these ~13x cheaper without touching an
  assertion. Skipping a no-op-detector is the specific move this repo keeps
  regretting.
- **Everything, which is the status quo.** Worth stating: `ci.yml` carries
  `if: ${{ false }}` on the pytest job and the check was removed from the
  required list on 2026-10-02. The suite is currently skipped **entirely** on
  every PR. Any proposal to skip more is answering a question whose premise is
  already maximally satisfied, and it has not helped. The lever that matters is
  getting the gate back on, which is what sharding is for.

## 2. Run-once — five seams where N tests recompute one answer

**Context that frames all five: this repository has ~900 test files, 12 files
with a `scope="module"` fixture, and zero real `scope="session"` fixtures.**
(The three `scope="session"` hits are inside generated child-test source
strings in `suite_performance`, not fixtures of the suite itself.) Expensive
setup is re-done per test almost everywhere by default, because there is no
convention saying otherwise.

| # | seam | N | unit cost | after | saving |
|---|---|---|---|---|---|
| 1 | shared-layout production in `suite_performance` child sessions | ~23 | 48.94 s | 1 seed + copies at 2.07 s | **≈ 950 s** |
| 2 | `fresh_scratch_adopter` default-config build, `BP-1500g` | 41 | ~14.8 s | 1 per config + copies at ~0.6 s | **≈ 580 s** |
| 3 | AC-store YAML parse (`yaml.safe_load` → `CSafeLoader`) | every sweep | 24.68 s | 1.86 s | **≈ 500 s** in suite, plus 20 s on a required CI gate and every pre-commit |
| 4 | store-scanning subprocesses with identical argv | ~20 known | 24.00 s | memoised | **≈ 150 s** |
| 5 | `_check_intra_package_closure_guard` verdict | ~44 builds | 11.84 s | fingerprint cache | ~520 s **minus whatever 1 and 2 already took** |

Seam 4 in detail, because it is the smallest change and already has a worked
precedent in the repo:

- `tests/test_prioritize_ac_integration.py` — ranks 37 and 47, 61.2 s between
  them, run `prioritize.py --include-acs` with **identical arguments** and
  assert different properties of the same output.
- `unit_tests/product_truth/test_uxp_300.py` — 15 tests, 73.4 s, each spawning
  the product-truth validator over a store that is identical for most of them.
- `unit_tests/ac_store/test_uxp700d2_i_live_store.py` — ranks 53 and 57,
  52.9 s, both deriving the same ready-set from the live store.

The precedent is `_CLI_CACHE` in
`unit_tests/ac_store/test_authored_test_spec_survives_generation.py:72`, whose
docstring already states the rule and its one precondition:

> Caching is sound here specifically because `--dry-run` is deterministic and
> side-effect-free. … The REAL entry point is still exercised **once per
> distinct input**, which is the property these tests exist for — what is
> skipped is repetition, not coverage.

That is the correct test for every memoisation in this list, and it is the
sentence that distinguishes seam 4 from a skip. Generalise the helper so the
cache crosses files instead of living as a module global in one of them.

**Seams 1, 2 and 5 are partial substitutes.** All three target builds against
unmodified package source. Whichever lands first collects most of the benefit.
Do not sum them.

## 3. Recommendations, ranked by expected saving

| # | change | saving | size | risk |
|---|---|---|---|---|
| 1 | **Seed the `suite_performance` child sessions** from one pre-built layout; keep the three deploy-count files on real builds | **≈ 950 s (~16 min)** | M | Low. No assertion changes; needs a manifest + config-fingerprint guard on the seed. |
| 2 | **Golden adopter for `BP-1500g`** — one build per (config, symlink-mode), `copytree` per test; second build stays real | **≈ 580 s (~10 min)** | M | Low-medium. Cache key must include config, or a `copy`-strategy test passes against a symlinked tree. |
| 3 | **`CSafeLoader` across the AC-store and guardian readers** | **≈ 500 s suite + ~20 s on a required CI gate + every pre-commit** | S | Low. Needs a differential proof over all 4,635 files and a grep for tests asserting parser error strings. |
| 4 | **Cross-file memoisation of deterministic store-scanning subprocesses** | **≈ 150 s** | S | Low. Precondition is already written down in the existing precedent. |
| 5 | **Make `_MANUAL` mean something** — a registered marker and an explicit default deselect, *or* delete the README claim | **0 s directly** | XS | None. It is currently a false statement about the suite's behaviour. |

Recommendation 5 saves no time and is still worth doing immediately, for the
same reason the other four no-op defences were worth fixing: a false statement
in a README about what the test suite runs will be believed, and the next
person to reason about suite cost will reason from it.

**Sequencing.** 3 first — it is the smallest, it is the only one that does not
decay, it helps a required CI gate and every developer's pre-commit, and it is
independent of the TQ-600a migration entirely. Then 1 (largest, self-contained,
and it stops the speed programme being the slowest thing in the suite). Then 2.
Then 4. Item 5 is a ten-minute fix that can go with any of them.

Against the prior set's plan: **CI sharding remains the dominant CI lever and
nothing here competes with it** — sharding redistributes wall clock, these
four remove work. They compose. But note that 1-4 together are worth roughly
**35 minutes off the local run**, which sharding does nothing for, and the
local run is what determines whether anyone runs the suite before pushing.

## 4. What I could not determine

Stated explicitly so nobody reads silence as a finding.

- **Whether these rankings hold on CI.** All durations are local. CI collects
  ~9,551 tests to the local 7,604; the ~1,950 extra are `tests/kernel/` and
  `tests/knowledge/` modules that cannot import without the pinned deps. They
  contribute **zero** to every number here and are a complete blind spot. The
  8-shard run's 15.4x spread on an even count split is consistent with the
  skew documented here but does not confirm it per-file. **The cheapest way to
  close this is a `--durations=0` artifact from one sharded CI run.**
- **Most root-level `unit_tests/test_*.py`.** The measurement pass was
  interrupted at ~22%, and that directory holds the `BP-900g-8` family. They
  are absent from the ranking, not cheap.
- **The exact per-test build-shape split in `BP-1500g`.** I counted 41 setup
  builds and know the first is Shape A into an empty dir. I did not time the
  *second* build (into a populated adopter), so the "~580 s" uses the idle
  Shape-A rate for the setup build only and is conservative on that basis but
  unverified on the ratio within each test.
- **Whether `CSafeLoader` is behaviourally identical on this store.** I
  measured that it parses all 4,635 files without error at 13.25x. I did
  **not** diff the resulting objects. That diff is the AC, not an assumption to
  carry forward.
- **One oddity worth someone's attention, outside this analysis's scope.** The
  self-targeting build in my probe printed
  `FAIL: jsonschema is required for product-truth validation … Refusing to run`
  on stderr and **exited 0**. That may simply be my environment missing a
  pinned dep, or it may be a phase that announces a refusal and does not
  propagate it. It is not a test-speed question, so I did not pull on it.
