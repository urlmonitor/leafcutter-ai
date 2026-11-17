---
title: "The combined plan: why skipping is the wrong lever, and why two of the three fixes are substitutes"
description: "Skipping the source guards would turn 20 tests green that exist to prove those guards fire. Run-once-and-cache preserves the signal exactly. But the cache and the TQ-600a migration target the same builds, so they are substitutes — sequencing them wrong pays twice for one benefit."
type: explanation
status: active
created: 2026-10-05
last_updated: 2026-10-05
components:
  - testing_quality
  - build_pipeline
---

# The combined plan

Part 5 of five. [Part 1](2026-10-05-pytest-ten-minute-target.md) gives the
verdict. [Part 2](2026-10-05-pytest-ten-minute-target-2-where-the-time-goes.md)
locates the cost in a build.
[Part 3](2026-10-05-pytest-ten-minute-target-3-four-routes-not-two.md) covers
the mutator taxonomy.
[Part 4](2026-10-05-pytest-ten-minute-target-4-ci-sharding.md) designs the CI
split.

## 1. "Can we skip some?" — no, but we can stop repeating them

The question that prompted this part was whether the expensive work could be
skipped, or whether it would be better to run it once rather than several
times. The second is right and the first is specifically wrong, and the
difference is worth stating because the two sound like degrees of the same
idea.

**Skipping the source guards breaks the tests that exist to prove they fire.**
`unit_tests/test_bp_900g_8.py`'s DECISION HISTORY (around line 608) records the
experiment already having been run: disconnecting the closure guard with
`if False and _check_intra_package_closure_guard(package_root)` makes the test
go **red**. That is not a brittle test — it is the test working. The
`BP-900g-8` family mutates the package to create a deploy-manifest gap and
asserts the build *fails*. A guard that never runs cannot fail, so all 20 of
those tests would invert and go green on a package that no longer checks
anything.

The defect class this protects against is not hypothetical: `CLAUDE.md`
documents **seven** instances, including `done_proof.py`, whose omission from
the deploy manifest would have blocked every merge in the repo once its gate
became required.

**Running it once and reusing the verdict changes nothing about the signal.**
The guard's only argument is `package_root` (Part 2 §2). Same source, same
answer, every time. Caching removes 59 recomputations of a result that was
never in question; it does not remove a single real check. A failing verdict
must replay the guard's diagnostic output, not just its exit code — otherwise
the cache degrades failure reporting even though it preserves failure
detection.

So: **not skip; cache.** That distinction is the whole answer, and the
instinct behind the question was the correct one.

## 2. The cache and the migration are substitutes — sequence accordingly

This is the finding that changes the plan, and it corrects an earlier reading
of my own in which these two were described as compounding.

A cache keyed on package source content only helps builds whose source is
**unmodified**. Checking which builds those are:

- **Shapes B, C and F (44 files)** invoke the repo's real
  `scripts/build.py`, so `package_root` is the real package, identical on
  every invocation. These **hit** the cache — 44 redundant identical-verdict
  computations.
- **Shape A (20 files)** does not. Confirmed by reading
  `unit_tests/build_guards/test_inf_700a_1_i_reachability.py:66-95`: a helper
  named `_copy_synthetic_package` copies `templates/`, `scripts/` and
  `config/` into a temp `pkg_root`, so the test can "mutate the COPY … and run
  the real build.py against it, without ever touching this repo's own source
  tree." Mutated source, different fingerprint, **cache miss — correctly so**,
  since the mutated verdict is exactly what those tests assert on.

So the cache's test-suite value is concentrated entirely in the 44 files that
**TQ-600a's migration removes from building at all**. The two fixes are aimed
at the same target:

| | guard cache first | migration first |
|---|---|---|
| captures | ~44 builds × 11.84 s guard ≈ **521 s** | ~636 s (Part 3 §6) |
| leaves for the other | ~115 s | **~0 s of suite benefit** |

**Recommendation: land the migration, not the cache, for suite speed.** It
captures more, it removes the work entirely rather than memoising it, it is the
already-specified programme, and it leaves the suite in a state where every
remaining build is legitimately distinct. Doing the cache first would collect a
large-looking number and then watch it evaporate as the migration lands behind
it — paying twice for one benefit.

(Both figures were larger in an earlier draft, which priced the guard at 39 s
and builds at 21.7 s. The *ordering conclusion* is unchanged by the correction
— the migration still captures more — but the gap is narrower than it looked.)

**The cache is still worth doing, for a different reason.** Its value outside
the test suite does not decay:

- **Every developer's own build.** `build-self.sh` and any
  `build.py --target-dir` drops from ~50 s to ~11 s. This is the inner loop
  for anyone working on templates.
- **Six other CI jobs run `build.py`** — `done-proof`, `reachability-guard`,
  `ac-store-valid`, `ac-store-valid-whole-store`, `numbering-guarantee-valid`,
  `consumer-install-sim` — plus all 8 shards. Each is a separate runner, so an
  in-process cache does not cross them; an `actions/cache` entry keyed on a
  hash of the package source would, though jobs starting simultaneously in one
  run all miss on the first pass.

So the cache should be justified and sized as a **build-time** improvement,
not a suite-time one. Specifying it as the latter would set up a measurement
that disappoints for reasons nobody recorded.

## 3. The plan, in order

| # | change | worth | size | status |
|---|---|---|---|---|
| 1 | **Shard CI into 8, serial** | CI 53.5 min → ~7 min | S | **implemented**; needs a durations file and a first real run |
| 2 | **Actually migrate the 77 sites** — the shared layout has zero consumers | unlocks everything below | M | TQ-600a-2/-8 built but uncommitted |
| 3 | **Copy route for shape B** (24 files) | −340 s | M | **TQ-600a-9 / -9-i authored** (draft) |
| 4 | **Re-route shape C** (14 files) to the shared layout | −207 s | S | part of item 2 |
| 5 | **Un-mark shape F** (6 files) | −89 s | XS | part of item 2 |
| 6 | **Cache the closure guard** | build 14.8 s → ~3 s | M | **TQ-600a-10 authored** (draft) |
| 7 | **`CSafeLoader` in `template_compiler.py:123`** | −2.2 s/build | XS | **TQ-600a-10-i authored** (draft) |
| 8 | **Cache the build output across shards** | up to 42% of shard wall | M | not specified |
| 9 | **Fix the coverage meter** so 0% migration cannot read clean | makes item 2 verifiable | S | not specified |

**Item 2 is the one that was assumed done and is not.** Everything in Part 3's
taxonomy is a re-aiming of work that has not begun: the fixture exists, is
green, and has seven consumers, all of which are its own tests. Items 4 and 5
are not separate projects — they are what item 2 *is*, once the taxonomy tells
it where to point.

**Item 9 matters more than its size suggests.** The plugin's
`declared_mutator_count` / `undeclared_count` only tick for tests that request
the fixture, so they report migration *quality*, never *coverage* — and read
clean at 0% coverage. A build-heavy subset printed `undeclared=0` while none of
the 77 sites had moved. That is the fourth instance in this repo of a check
that passes having inspected nothing, and it is the instrument item 2 would be
steered by.

Items 3-7 are behaviour changes and start with acceptance criteria per ADR-012.
Item 1 is config, not behaviour, and is already written: an 8-way `test-shard`
matrix plus a `test` aggregator carrying the stable `Test suite (pytest)` name.

## 4. Parallelism: measured, and it pays

`pytest-xdist` is already a dependency (`requirements-dev.txt:26`,
`pytest-xdist>=3.5`; 3.8.0 installed). Measured on a 4-core host over a
build-heavy subset:

| config | wall | speedup | builds executed |
|---|---|---|---|
| serial | 111.32 s | 1.00× | 6 |
| `-n 2 --dist loadfile` | 74.34 s | 1.50× | 6 |
| **`-n 4 --dist loadfile`** | **56.62 s** | **1.97×** | 6 |
| `-n 4` (default `load`) | 67.49 s | 1.65× | **8** |
| `-n 8` (default `load`) | 66.69 s | 1.67× | **10** |

Three things fall out, and the third is the most actionable:

**It pays, and the feared failure mode does not occur.** The shared layout is
produced **once per run, not once per worker** — verified by running the
committed proof, `test_tq_600a_1_multiworker.py`, which spawns a child pytest
at `-n 2` and asserts exactly one deploy event. Both tests passed. The
`fcntl.flock` + `run_key()` design holds.

**But the lock serialises.** The producer holds the flock across the entire
production, so every other worker that reaches a reader test blocks idle for
its full duration — and that duration is **Shape B** (~54–58 s), not Shape A.
Paid once per *run*, which under sharding means once per *shard*. Producing
the layout once in a setup job and distributing it would remove this.

**`--dist load` duplicates the most expensive work in the suite.** The default
schedules per test; this suite uses `unittest` classes with `setUpClass`
builds, so a class split across workers re-runs `setUpClass` on each — 6 builds
became 8 at `-n 4` and 10 at `-n 8`. `--dist loadfile` holds it at 6 and is
worth 16% of wall clock on its own. **Set this before `-n` is ever measured**,
or xdist gets benchmarked with a scheduler that re-runs builds and looks like
it barely helps.

### Wall-clock model

Anchored on 53m33s CI serial, with subset imbalance removed from the measured
efficiencies (E(2)=0.85, E(4)=0.65):

| scenario | n=1 | n=2 | n=4 |
|---|---|---|---|
| today | **53.5 min** | 31.5 | 20.6 |
| + build cut and migration adopted | 31.5 | 18.5 | 12.1 |
| **4 CI shards × n**, today's code | — | 7.6 | **5.2** |
| **8–10 CI shards, serial**, today's code | **~7 min** | 4.6 | 3.6 |

**Sharding alone clears ten minutes immediately and needs no correctness
work.** xdist alone does not, on current code. That asymmetry is the whole
sequencing argument — and Part 4 §4 explains why the shipped change takes the
serial-shard row despite `4 × -n 4` being cheaper in runner minutes.

**The floor, ranked.** Worth knowing before anyone tries to push below ~5 min:

1. **Per-shard fixed cost, ~90 s, paid N times** — runner boot, checkout,
   `pip install`, and the job's own Shape-B `build.py`. At 10 shards × `-n 4`
   it is 42% of shard wall clock. **Caching the build output across shards is
   worth more than any further sharding.**
2. The shared-layout flock barrier, ~54–58 s, once per shard.
3. **The longest single indivisible test, which nobody has measured** — the
   hard floor for the entire plan, and the in-flight durations run will name it.
4. Physical core count; past `n = cores` the return goes negative.

## 5. Risks worth carrying into the ACs

- **The copy route served a config-mismatched tree** (Part 3 §4). Four build
  sites across three files build with `{"workflows": {"enabled": True}}`. Given
  a copy of the default-config layout they would pass against a tree missing
  the thing they test. Any copy-route AC must refuse or re-serve on config
  mismatch, with a can-fail proof.
- **A cache that cannot be shown to invalidate.** The cache's correctness is
  entirely in its invalidation. The AC needs a differential proof — cached
  verdict identical to uncached — and a mutation proof — change the source,
  the verdict changes.
- **A durations file that silently empties.** Covered in the refresh workflow
  by refusing to commit a file with fewer than 1,000 entries. This repo has
  shipped three checks that passed having inspected zero files; the guard
  against being the fourth is cheap.
- **Shard count above the concurrency ceiling** (Part 4 §4). Over the cap,
  jobs queue and the measured gain falls short of the arithmetic with no error
  anywhere. Confirm the account plan before raising 8.
- **`git worktree add` against the real repository.**
  `unit_tests/portability/test_ge_120e_1.py` does this at lines 251, 317, 361
  and 560 with `cwd=_REPO_ROOT`, mutating the shared worktree registry, refs
  and object store. Its own comments record KI-TQ-012, where the fixture leaked
  a git identity onto ten real commits, several on open PRs. Harmless under
  serial shards; a correctness hazard the moment xdist is enabled. Pin the
  family with `@pytest.mark.xdist_group` + `--dist loadgroup`, or move the
  fixtures to a disposable clone, **before** any `-n` lands.
- **Two `TQ-600b` L1 premises are now stale** and should be corrected before
  the BA and IT-PO work against them: it states that pytest-xdist is not
  installed and not in `requirements-dev.txt` (it is, at line 26, 3.8.0
  installed), and that the suite's time is spent "waiting on separate programs
  rather than on any real computation" — whereas the builds are 99.7%-CPU
  single-threaded compute, which is exactly why they cap at the core count.
- **A guard with an empty offender set.** Sweeps of two of the three
  anticipated collision classes — fixed `/tmp` paths and shared jsonl sinks —
  found the large majority are string literals in mocked payloads or already
  use `gettempdir() / uuid4()`. Both are still worth building as standing
  guards, but with near-empty offender sets the deliberate offender must be a
  **permanent committed fixture**, or the guard is indistinguishable from one
  that cannot fail.
