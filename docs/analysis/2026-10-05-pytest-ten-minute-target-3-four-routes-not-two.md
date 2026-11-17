---
title: "The 64 tests that 'need their own build' are four categories, and only 20 of them do"
description: "TQ-600a routes tests to a shared layout or a private build. An audit of the 64 private-build tests finds 20 genuinely need one, 24 need only a 0.607s copytree, 14 are misclassified read-only, and 6 never deploy at all. The copy route already exists in the repo three times."
type: explanation
status: active
created: 2026-10-05
last_updated: 2026-10-05
components:
  - testing_quality
  - build_pipeline
---

# The 64 tests that "need their own build" are four categories

Part 3 of five. [Part 1](2026-10-05-pytest-ten-minute-target.md) gives the
verdict. [Part 2](2026-10-05-pytest-ten-minute-target-2-where-the-time-goes.md)
locates the cost inside a build.
[Part 4](2026-10-05-pytest-ten-minute-target-4-ci-sharding.md) designs the CI
split. [Part 5](2026-10-05-pytest-ten-minute-target-5-the-combined-plan.md)
sizes everything.

## 1. The binary that is actually a four-way split

`CLAUDE.md` states the TQ-600a routing rule as a clean dichotomy:

> A test that only **reads** a deployed layout must reuse the shared
> session-scoped reference build. … A test that **mutates** the package before
> building … still builds its own copy.

Two routes: shared, or your own build. The migration ledger from TQ-600a-8
records the result of applying it — 945 tests inspected, **3** on the shared
layout, **64** on their own copy, 0 offenders.

That ledger is accurate and the rule is correctly applied. The problem is the
rule itself: it has two outcomes for a population with four shapes. An audit of
all 64 "own copy" files finds:

| | shape | files | what it actually needs |
|---|---|---|---|
| **A** | mutate **before** build — alter the package, build, assert the build FAILS | **20** | its own real build. The failing build *is* the test. |
| **B** | mutate **after** build — build OK, then modify the deployed tree | **24** | its own **copy**. Never its own build. |
| **C** | read-only — misclassified | **14** | the shared layout |
| **F** | never deploys at all | **6** | nothing; marked mutator to quiet a checker |

**Only shape A needs what all 64 are paying for.** Shapes B, C and F are 44
files — 69% of the population — buying a 50-second build to get something
cheaper.

Shape B is the interesting one, because it is the largest and its need is real:
it genuinely must not share a layout, since it writes into the deployed tree.
It just doesn't need a *build* to get an unshared tree.

## 2. A copy is 91× cheaper than a build, measured

| | time |
|---|---|
| One `build.py` | 55.42 s local |
| `shutil.copytree` of the resulting layout | **0.607 s** (median of 5) |

The layout is 907 entries, 10.7 MB. The copy is **91× cheaper** and produces a
tree that is byte-identical to what the build would have produced, writable,
and owned by exactly one test.

For the 24 shape-B files that is a straight substitution with no loss of
isolation: each still gets a private tree nothing else touches.

## 3. This is not a new technique — the repo already does it, three times

The pattern has been independently reinvented three times, which is the usual
sign that it should be a route rather than a habit:

| file | line |
|---|---|
| `unit_tests/commit_guardian/test_ge_127c_1_deployed_reachability.py` | 159 — `shutil.copytree(_SHARED_BUILD_DIR, dst, dirs_exist_ok=True)`, from a module-scope build |
| `unit_tests/portability/test_bp_900h6i.py` | 190 — `shutil.copytree(self._golden_dir, dest)` |
| `unit_tests/portability/test_bp_900h6ii.py` | 217 — same shape, same `_golden_dir` idiom |

Each builds once, then hands every test a copy. The proposal in Part 5 is to
**generalise what these three already do** into a declared route, not to invent
a mechanism. That matters for risk: the behaviour is already proven in this
suite, on this layout, against these tests.

The `commit_guardian` cluster alone is **17 files** of one identical shape —
build, assert returncode 0, write fixture files into the target, run the
deployed check cold. Confirmed by reading
`unit_tests/commit_guardian/test_ge_127f_2_reachability_and_deployed.py:114-176`.
One route change covers all seventeen.

## 4. The trap that would make this silently wrong

Found during the audit, and it is the reason this needs an acceptance
criterion rather than a refactor.

**Four build sites across three files build with a non-default config:**

| file | line |
|---|---|
| `unit_tests/build_guards/test_command_reachability_guard.py` | 433 |
| `unit_tests/build_guards/test_command_reachability_guard.py` | 567 |
| `unit_tests/workflows/test_bo2400c1v_orphan_runner_removal.py` | 96 |
| `unit_tests/build_guards/test_inf_700a_1_i_reachability.py` | 105 |

each writing, before the build:

```python
json.dumps({"workflows": {"enabled": True}}), encoding="utf-8"
```

The shared reference layout is built with the **default** config, where
workflows are disabled. Hand one of these tests a copy of that layout and the
deployed tree has no `workflows/` directory at all — which is exactly the state
`build.py` leaves behind when `workflows.enabled` is false, and exactly what
`test_command_reachability_guard.py:774` documents as the "workflows switched
off" branch.

The test would then not fail. It would **pass against the wrong tree**: its
fixture is present, the behaviour it checks is absent, and nothing distinguishes
"the reachability guard correctly found no problem" from "there was nothing
there to find". `test_bo2400c1v_orphan_runner_removal.py:141` asserts
`deployed_workflows.is_dir()` precisely because the author anticipated this, and
its message says so — "(workflows.enabled=true was set for this build)".

This is the same defect class as the inert `--strict-markers` that `CLAUDE.md`
already documents: a string present, a behaviour absent, a green test for as
long as the file existed. The copy route must therefore **refuse or re-serve**
a consumer whose build config differs from the shared layout's, rather than
silently handing over a mismatched tree. A route that cannot tell the
difference reintroduces, at scale, the exact failure mode TQ-600a exists to
prevent.

## 5. Why the count-based ledger did not surface any of this

TQ-600a-8's ledger reported `offenders: []` and it was right to. It was asked
whether any test was mis-routed **under the two-route rule**, and none was.
Shapes B, C and F are not rule violations; they are correctly-routed tests
whose route is more expensive than their need.

That is worth naming as a measurement lesson rather than a defect in the
ledger. A checker that validates conformance to a rule cannot tell you the
rule is too coarse — it will report a clean sheet right up until someone asks
a different question. The four shapes only became visible when the 64 files
were read and classified by *what they do to the tree*, which is not a question
the ledger was built to ask.

The same holds for shape C's 14 files and shape F's 6. Both are marked
`shared_layout_mutator`, both pass, and both are honest about it — F's files
carry the marker specifically to silence a checker false positive, which is a
documented workaround rather than a mistake. They cost a build each anyway.

## 6. What this is worth

Taking the shape counts at the **measured Shape-A build rate of 14.81 s**
(Part 2 §1 — the shape these sites actually pay, not the ~55 s self-targeting
shape), against a 0.607 s copy:

| shape | files | now | after | saved |
|---|---|---|---|---|
| B → copy route | 24 | 355 s | 15 s | **340 s** |
| C → shared layout | 14 | 207 s | ~0 | **207 s** |
| F → no layout | 6 | 89 s | 0 | **89 s** |
| A → unchanged | 20 | 296 s | 296 s | 0 |

≈**636 seconds, roughly 11 minutes** off an idle local run, and proportionally
more on a contended one. This is the portion of the work that *also* helps CI,
since it removes build subprocesses rather than redistributing them.

An earlier draft of this table priced builds at 21.7 s and claimed ~940 s. That
was the wrong shape; see Part 2 §1 and §6 for how the two build shapes were
conflated across this whole programme, and Part 2 §2 for the correction that
found it.

**None of this is started.** `shared_layout_reader` appears in 7 files, all of
them the fixture's own tests under `unit_tests/suite_performance/`. All 64
files below are still on their own builds, so every number in the "now" column
is live cost being paid today.

The 20 shape-A files keep their builds, and should: they are the tests that
prove the build's guards fire. Part 2 §4 covers why those specifically cannot
be made cheaper by skipping guards.

They also get **no benefit from the guard cache**, and that is the cache
working correctly rather than a shortfall. Shape A mutates the package source
before building; the source fingerprint therefore changes; the cache misses and
the guard computes a real verdict — which is the entire point, since the
verdict those tests assert on is the one produced by the mutation. A cache that
*did* serve these tests a stored answer would hand them the pre-mutation
verdict and turn all 20 green regardless. So shape A stays at 434 s, and the
only honest way to shrink it further is to reduce the guard's own ~39 s cost
(Part 2 §1 shows it is an unmemoised AST walk) rather than to avoid running it.
