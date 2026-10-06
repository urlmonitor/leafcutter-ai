---
title: "The shared-layout programme cannot reach a ten-minute suite, and what can"
description: "TQ-600a removes build subprocesses from the test suite. Measured against a 1:29:47 run, removing every one of them still leaves 33 minutes, because builds are only 63% of the clock. The ten-minute target needs CI sharding and a cached source guard, and the two are multiplicative."
type: explanation
status: active
created: 2026-10-05
last_updated: 2026-10-05
components:
  - testing_quality
  - build_pipeline
---

# The shared-layout programme cannot reach a ten-minute suite, and what can

Part 1 of five.
[Part 2](2026-10-05-pytest-ten-minute-target-2-where-the-time-goes.md) locates
the cost inside a single build.
[Part 3](2026-10-05-pytest-ten-minute-target-3-four-routes-not-two.md) shows the
64 "needs its own build" tests are four categories, not one.
[Part 4](2026-10-05-pytest-ten-minute-target-4-ci-sharding.md) designs the CI
split and names what it breaks.
[Part 5](2026-10-05-pytest-ten-minute-target-5-the-combined-plan.md) sizes the
whole set and answers "can we just skip things".

**Almost nothing here is implemented.** This is analysis written so the
remaining work can be specified as acceptance criteria first. TQ-600a-1, -3 and
-5 are merged; everything this document recommends beyond them is unbuilt.

Repo `origin/main` at `3ec14b85`, freshly fetched, 2026-10-05.

## 1. Verdict

**The ten-minute target is reachable, but not by the route currently being
built.**

TQ-600a exists to stop tests from spawning their own `build.py`. That is real
work and it is worth finishing — but on its own it cannot reach ten minutes.

The clearest evidence is CI, since CI is the target. Anchoring on the best
observed full CI run, **53m33s (3,213 s)**:

| | |
|---|---|
| Build work: ~77 sites × ~20 s | **1,540 s — 48%** |
| Everything else | **1,673 s — 52%** |

Removing **every** build subprocess — a perfect outcome for the entire TQ-600a
tree — leaves ~**28 minutes**. Nearly three times the target. The shared layout
cannot get there because builds are roughly half the run, not nearly all of it.

That is the finding that reframes the programme. TQ-600a was scoped as *the*
suite-speed fix. It is one of three, and it is not the one that gets to the
number.

**A second finding makes this more urgent, not less.** The TQ-600a machinery is
built, green and proven — and it has **zero real consumers**. `shared_layout_reader`
appears in exactly 7 files, *all* of them under `unit_tests/suite_performance/`,
which are the fixture's own tests. Not one of the ~77 legacy build sites is
migrated. So the 48% above is entirely unclaimed: the thing that would collect
it exists and has not been pointed at anything.

Worse, the progress meter cannot see this. The plugin's `declared_mutator_count`
/ `undeclared_count` figures only tick for tests that *request* the fixture, so
they measure migration **quality**, not **coverage** — and they read clean at
0% coverage. A build-heavy subset run during this investigation printed
`undeclared=0` while none of the 77 sites had moved.

**What gets us there:**

1. **Shard the CI job** (Part 4). Splits wall clock by the shard count without
   skipping a single test. Projected **~7 minutes**. This is the dominant
   lever, it requires no change to any test, and it is independent of
   everything else here.
2. **Finish TQ-600a, but against the right population** (Part 3). The 64 tests
   currently buying their own build are four distinct shapes, and only 20 of
   them need one. Worth ≈**16 minutes** off the local run.
3. **Cache the package source guards** (Part 2). `_check_intra_package_closure_guard()`
   is **77.6%** of a build, and its only input is the package source, which 44
   of those 64 tests do not modify.

**Levers 2 and 3 are substitutes, not multipliers, and the ordering matters.**
They both target the same population — builds that run against unmodified
package source — so whichever lands first collects most of the benefit and the
second finds less left to take. This is the opposite of the "they compound"
reading, and getting it wrong would mean sequencing the expensive one first for
a return the cheap one already captured. Part 5 §2 works the interaction
through and recommends which to do first.

Lever 1 is genuinely independent of both, which is the other reason it goes
first.

## 2. What the target actually means, because it has two answers

"Bring pytest down to 10 minutes" resolves differently depending on which run
is meant, and the two have almost disjoint fixes. This needs stating because
the obvious lever only moves one of them:

| | now | sharding | guard cache | TQ-600a |
|---|---|---|---|---|
| **CI job** (wall clock to a green check) | disabled | **yes — the main lever** | yes | yes |
| **Local full run** (`pytest tests/ unit_tests/`) | 1:29:47 | **no effect at all** | yes | yes |

Sharding is a CI-only lever. It buys wall clock by spending more runners in
parallel; a developer on one machine gets nothing from it. If the ten-minute
target includes the local run, sharding alone does not satisfy it and the
guard cache stops being an optimisation and becomes load-bearing. Part 5 treats
the local run as a first-class target with its own plan, rather than assuming
the CI number answers both.

## 3. The CI job is currently disabled, which changes the risk calculus

`.github/workflows/ci.yml` carries:

```yaml
  test:
    name: Test suite (pytest)
    # Disabled indefinitely by owner request (2026-10-02): full-suite runtime.
    # This check is also removed from the main-branch required-check list.
    if: ${{ false }}
```

Two consequences, and the second is the one that matters:

**The job allocates no runner and runs no step.** A `if: ${{ false }}` at job
level is evaluated before setup, so this is a true zero-cost disable, not a
fast failure.

**The suite is not gating `main` at all right now.** The check was removed from
the required list on the same day. So between 2026-10-02 and whenever this
lands, the only thing standing between a test-breaking change and `main` is
whether the author's local pre-commit hooks are installed and whether they
chose to run the full suite — which, at 1:29:47, is a safe thing to assume
nobody does. Every other required gate (lint, component vocab, done-proof,
changelog, AC store) is a *static* check. None of them run the tests.

This cuts both ways and both directions are worth being explicit about:

- **It lowers the risk of the sharding change.** There is no required check to
  break, no ruleset edit needed, and no window where a half-migrated matrix
  blocks merges. We can land the shard matrix, watch it, and promote it to
  required as a separate deliberate step. The aggregator-job trick normally
  needed to keep a required check name stable is **not** needed here.
- **It raises the urgency.** The reason to shard is not tidiness. It is that
  the repo has had no behavioural merge gate for three days, and the
  documented reason is a number — 90 minutes — that this work exists to fix.
  A disabled gate is the most expensive kind of slow test.

## 4. What was measured, and what is projected

Being explicit about this, because the distinction decides how much weight each
number can carry. An earlier pass through this material presented a contended
worst-case build time as *the* build time throughout, which made every
return-on-investment estimate roughly 3× too optimistic. That error is the
reason for this section.

**Measured, reproducible:**

- **The suite collects 7,604 tests**, measured 2026-10-05. The "5,318" figure
  in `CLAUDE.md` is stale, so every share derived from it understates the
  denominator: the 60 build-spawning tests are **0.8%** of the suite, not 1.1%.
- Locally, **163 modules fail to collect** — `pydantic`, `langgraph`,
  `langchain`, `neo4j` and `langfuse` are pinned in `requirements-dev.txt` but
  absent from this environment. CI installs them, so those modules run there
  and nowhere locally. Any local measurement is blind to that whole subsystem.
- 53m33s best observed full CI run. 1:29:47 full local run, 63% of clock in 60
  tests — **under heavy agent-fleet contention**, and with those 163 modules
  never running, so treat it as neither an upper nor a lower bound but a
  different suite from the one CI runs.
- 77 `build.py` invocation sites across 52 test files; zero `scope="session"`
  fixtures; **zero** of the 77 migrated to the shared layout.
- **Two build shapes, ~3.5× apart** (Part 2 §1). Against an empty target — what
  the 77 sites do — **14.81 s**. Self-targeting on a populated tree — what
  `build-self.sh` and the CI pre-pytest step do — **52–56 s**.
- `_check_intra_package_closure_guard()` timed in isolation: **11.84 s**, which
  is **80%** of a 14.81 s build. Its two sibling guards cost **0.03 s** and
  **0.02 s**. All 35 deploy phases together: 3.6 s.
- `shutil.copytree` of the 907-entry, 10.7 MB deployed layout: **0.607 s**
  median of 5 runs — **91× cheaper** than producing it.
- Collection: 5.33 s. The `pytest_ac_enforcement` plugin fires only on
  failures. Both measured and **ruled out**.
- The runner is **4-core**: `gh repo view` reports this repository PUBLIC, and
  public repos get the free 4-vCPU/16 GB standard runner.

**A correction, because it is the reason this section exists.** An earlier pass
reported the closure guard as "39.07 s of a 50.38 s build, 77.6%", with
`cProfile` independently agreeing at 78%. The **share was right and the
absolutes were wrong** — those were a Shape-B build under contention, roughly
3.3× inflated. Two methods agreeing on a percentage felt like strong
confirmation and was not, because both measured the same contended run.

It was catchable without any new tooling: the guard's only argument is
`package_root`, so its cost cannot depend on the build target, and a 39 s guard
cannot fit inside a 14.81 s build. Two circulating numbers were arithmetically
incompatible. Timing the guard directly took one command and should have been
the first thing done, not the last.

**Projected, with the assumption named:**

- **CI sharded ≈ 7 min at 8 shards.** From the 53m33s anchor plus a per-shard
  fixed cost of ~90 s (runner boot, checkout, `pip install`, the job's own
  `build.py`). That fixed cost is paid by every shard and is untouched by
  sharding — at high shard counts it becomes the dominant term, which is why
  Part 4 does not simply maximise the shard count.

**The first sharded CI run replaces the projection with a measurement.** It is
stated as a projection so that, when the real number disagrees, the
disagreement is visible rather than absorbed.

## 5. Why this was not visible sooner

The suite's cost profile is extraordinarily skewed: **60 of 7,604 tests hold
63% of the wall clock.** That is 0.8% of the tests holding two thirds of the
time.

A skew that sharp defeats the normal ways of noticing. Per-directory timings
look uniformly mediocre, because the expensive tests are scattered across 52
files in a dozen directories rather than clustered somewhere a profile would
point at. `--durations=10` shows ten build-spawning tests and gives no hint
there are fifty more behind them. And each individual test is *defensible* — a
test that deploys the package and checks the result is a good test. Nothing
looks wrong at any single site. The cost is entirely in the repetition, which
is only visible when you count the sites, and counting them is what nobody had
done.

The same skew is also why the fix decomposes so cleanly. There is no diffuse
20%-everywhere slowdown to chase. There are three specific things, each with a
measured size, and Part 5 sizes them against the target.
