---
title: "Sharding the CI suite: duration-balanced splits, and why the concurrency ceiling sets the shard count"
description: "A matrix of pytest-split shards cuts CI wall clock with zero coverage loss and no ruleset edit. Count-based splitting is actively wrong for a suite where 1.1% of tests hold 63% of the clock, so a committed .test_durations is load-bearing. The binding constraint is the account's concurrent-job ceiling, not the arithmetic."
type: explanation
status: active
created: 2026-10-05
last_updated: 2026-10-05
components:
  - testing_quality
  - build_pipeline
---

# Sharding the CI suite

Part 4 of five. [Part 1](2026-10-05-pytest-ten-minute-target.md) gives the
verdict. [Part 2](2026-10-05-pytest-ten-minute-target-2-where-the-time-goes.md)
locates the cost in a build.
[Part 3](2026-10-05-pytest-ten-minute-target-3-four-routes-not-two.md) covers
the mutator taxonomy.
[Part 5](2026-10-05-pytest-ten-minute-target-5-the-combined-plan.md) sizes
everything.

## 1. What sharding is and is not

Split the collected test set into N disjoint groups and run each in its own
parallel CI job. Every test runs **exactly once**, on exactly one shard. Wall
clock falls by roughly N; runner minutes rise slightly.

Stating the properties plainly, because "make CI faster" invites suspicion that
something is being skipped:

- **No test is skipped, deselected, or marked.** The union of shards is the
  full set. This is not test selection, and it is not affected-test detection.
- **No test's behaviour changes.** Each shard is an ordinary `pytest` run over
  a subset of node ids.
- **It buys nothing for the local run.** One developer on one machine still
  waits 1:29:47. Sharding spends parallel runners, which a laptop does not
  have. Part 1 §2 treats the local target separately.

## 2. The mechanism

`pytest-split` provides `--splits N --group K`, which partitions the collected
set and runs one partition. A GitHub Actions matrix supplies K:

```yaml
  test-shard:
    name: Test suite shard ${{ matrix.group }}/${{ strategy.job-total }}
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false          # one shard's failure must not hide the others'
      matrix:
        group: [1, 2, 3, 4, 5, 6, 7, 8]
    steps:
      # ... checkout, python, pip install -r requirements-dev.txt,
      #     build.py --target-dir ., fetch the pinned benchmark corpus ...
      - name: Run test suite shard
        env:
          AC_ENFORCE_STRICT: "1"
        run: >
          python -m pytest tests/ unit_tests/ -q
          --continue-on-collection-errors
          --splits ${{ strategy.job-total }}
          --group ${{ matrix.group }}
```

`fail-fast: false` is not cosmetic. The default cancels sibling jobs on the
first failure, which would turn a one-test regression into "9 shards cancelled,
cause unknown" — strictly less information than the single job gives today.

Two repo-level additions this needs:

- **`pytest-split` in `requirements-dev.txt`.** CI installs from that file, so
  the dependency is CI-only in practice; no local install is required, and the
  plugin is inert unless `--splits` is passed.
- **A committed `.test_durations`.** Load-bearing — see §3.

## 3. Count-based splitting is actively wrong here

`pytest-split` without a durations file falls back to splitting by **test
count**. For most suites that is a reasonable approximation. For this one it is
close to the worst available choice, and the reason is the skew from Part 1 §5:
**60 of 5,318 tests hold 63% of the wall clock.**

Count-based splitting distributes 5,318 tests evenly and the 60 expensive ones
land wherever they fall. At 8 shards the expected count is 7.5 heavy tests per
shard, but nothing enforces it — an unlucky split putting 15 on one shard and 2
on another produces a slowest shard roughly 3× the fastest. The matrix finishes
when its slowest member does, so the whole benefit collapses to that one shard.

With durations, `pytest-split`'s default `duration_based_chunks` algorithm
packs groups to equal *time*, which for this distribution means separating the
heavy tests and padding each group with cheap ones. That is the difference
between a split that is **even** and one that is **balanced**, and only the
latter delivers the arithmetic. (`--splitting-algorithm least_duration` is the
alternative; it does not preserve test order within a group, which matters only
if some test in the suite turns out to be order-dependent. Start with the
default and change it only if measurement says to.)

**Therefore the durations file is part of the change, not a tuning extra.** It
is produced by one full instrumented run (in flight as this is written, via a
plugin that accumulates setup+call+teardown per node id and flushes
incrementally, so an interrupted run still yields usable data).

Two consequences worth designing for rather than discovering:

- **It goes stale.** New tests are unknown to the file; `pytest-split` assigns
  them a default and balance drifts. The file needs periodic regeneration — a
  scheduled or `workflow_dispatch` job that runs the suite unsharded and
  uploads a fresh `.test_durations` is the low-maintenance form.
- **Staleness degrades gracefully.** A drifted file makes shards uneven, not
  wrong. No test is lost. This is a performance regression, never a
  correctness one — which is what makes the whole approach safe to land before
  it is tuned.

## 4. The binding constraint is the concurrency ceiling, not the arithmetic

This is the part the arithmetic alone gets wrong, and it sets the shard count.

A pull request today already starts roughly **12–14 concurrent jobs**: about
ten from `ci.yml` (with `test` disabled and `ac-store-valid-whole-store` being
push-only), plus `schema_diff`, `agent-evals`, and `fixture-drift`'s two.

Add a 10-shard matrix and the run wants ~22–24 concurrent jobs. GitHub caps
concurrent jobs per account by plan — 20 for GitHub Free. Above the cap, jobs
**queue** rather than fail, so the consequence is that the last shards start
only as earlier ones finish, and measured wall clock lands well short of the
N× the arithmetic promises.

So:

| shards | concurrent jobs on a PR | fits under a 20-job cap? |
|---|---|---|
| 6 | ~18–20 | yes, at the edge |
| 8 | ~20–22 | marginal |
| 10 | ~22–24 | no — expect queueing |

**Recommendation: start at 8, and measure the real wall clock before raising
it.** Eight is where the arithmetic still gives a comfortable margin against
the ten-minute target while staying near the ceiling rather than over it. The
account's actual plan should be confirmed before assuming 20 — it changes the
answer and it is one lookup.

This also explains why "just use 20 shards" does not work, and why per-shard
`pytest-xdist` (`-n`) is the more promising second axis: it adds parallelism
*inside* a job, which no concurrency cap counts.

**The runner is 4-core, not 2.** `gh repo view` reports this repository
**PUBLIC**, and public repositories get the free 4-vCPU/16 GB standard runner.
That makes `-n 4` the natural ceiling per shard (`-n 8` on 4 vCPU measured
*worse* than `-n 4`), and it means a serial shard leaves three of four cores
idle. Worth confirming with `nproc` in a CI step before sizing, but plan for 4.

Measured on a 4-core host over a build-heavy subset, `-n 4 --dist loadfile`
gave **1.97×**. So `4 shards × -n 4` ≈ 5.2 min beats `10 shards serial`
≈ 6.9 min on ~40% fewer runner minutes.

**This change still ships serial shards, deliberately.** Two reasons, both
correctness rather than performance:

- **All six `TQ-600b` children are `work_status: todo`.** Nothing in the
  parallel-correctness story is implemented, including `TQ-600b-1`, the
  per-test outcome-equivalence gate that is supposed to prove a parallel run
  means the same thing as a serial one.
- **Some tests run `git worktree add` against the real repository.**
  `unit_tests/portability/test_ge_120e_1.py` does
  `_run_git(["worktree", "add", "--detach", str(self.root), "HEAD"], cwd=_REPO_ROOT)`
  at lines 251, 317, 361 and 560, with `worktree remove --force` in teardown.
  That mutates the shared worktree registry, refs and object store. The file's
  own comments record KI-TQ-012, where this fixture family leaked a
  `git config user.email` identity onto ten real commits, several on open pull
  requests. This workspace has also seen 0-byte shadow-object `.git` corruption
  from concurrent activity.

**Sharding is immune to both; xdist is not.** Each shard is a separate runner
with its own fresh checkout, and tests within a shard still run serially — so
no two tests ever race the same `.git`, and `TQ-600b-1`'s equivalence gate
stays off the critical path. That is sharding's real advantage over xdist, and
it is why it goes first even though xdist is cheaper per minute saved.

When xdist is adopted, **`--dist loadfile` is mandatory and must be set before
`-n` is ever measured.** The default `--dist load` schedules per *test*, and
this suite uses `unittest` classes with expensive `setUpClass` builds — so a
class split across workers re-runs `setUpClass` on each. Measured: 6 builds
became **8** at `-n 4` and **10** at `-n 8`. On the same subset,
`-n 4 --dist loadfile` was **56.62 s** against `-n 4 --dist load` at
**67.49 s** — 16% of wall clock from one flag, and without it xdist gets
measured with a scheduler that duplicates the most expensive work in the suite
and looks like it barely helps.

## 5. A stable check name, without a ruleset edit

The `test` job is currently disabled **and already removed from the
main-branch required-check list** (Part 1 §3). A matrix changes check names to
`Test suite shard 1/8` … `8/8`, which would normally be a problem: required
checks are matched by name, and a matrix whose size changes invalidates them
every time.

The fix is an aggregator — one job that depends on the matrix and carries the
single stable name:

```yaml
  test:
    name: Test suite (pytest)
    runs-on: ubuntu-latest
    needs: [test-shard]
    if: always()
    steps:
      - name: Fail unless every shard succeeded
        run: |
          echo "shard result: ${{ needs.test-shard.result }}"
          test "${{ needs.test-shard.result }}" = "success"
```

`needs.<matrix-job>.result` aggregates across all matrix legs — it is
`success` only when every leg succeeded — and `if: always()` is required, or the
job is skipped on any shard failure and reports nothing instead of failing.

Because pytest is **not** required right now, this costs nothing today and buys
the option later: the name `Test suite (pytest)` already exists and already
means "all shards green", so promoting it back to required is a ruleset
checkbox with no workflow change. Landing it now rather than at promotion time
is the cheap ordering.

## 6. What sharding costs, and what it interacts with

**Runner minutes rise ~25%.** Each shard repeats the fixed setup: checkout,
`pip install -r requirements-dev.txt`, one `build.py`, the pinned-corpus fetch,
and 5.33 s of collection. At 8 shards that fixed cost is paid 8 times — call it
90–120 s each — against a single job's 52 min. Trading ~25% more runner
minutes for ~7× less wall clock is the intended bargain, and worth stating
explicitly so it is a decision rather than a surprise on the bill.

**It multiplies the shared reference layout.** TQ-600a-1's guarantee is "one
build per run". Under a matrix there are 8 runs, so the shared layout is built
8 times — once per shard, in parallel. Nothing breaks: each shard is an
independent process tree with its own layout, and correctness is per-run. But
the property's name stops matching the deployment, and it makes the Part 2
guard cache **more** valuable rather than less, since it is now 8 identical
guard computations per CI run rather than one.

**TQ-600a-3's integrity guard keeps working per shard.** It fails the run if the
shared layout is mutated, and reports `compared_count > 0` so a comparison that
inspected nothing cannot pass. A shard containing zero reader-marked tests
yields `had_consumers: False`, which a-3 already treats as legitimate rather
than a failure — so the guard neither false-fails on a shard that happens to
get no readers, nor silently passes having checked nothing.

**It does not reduce the cost of any single test.** A shard containing a 60 s
build test still waits 60 s. Sharding is the lever that needs no test to
change, which is exactly why it should land first — and exactly why it is not
sufficient on its own if the target includes the local run.
