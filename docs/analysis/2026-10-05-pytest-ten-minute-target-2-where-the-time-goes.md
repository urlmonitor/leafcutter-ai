---
title: "Where a build's time goes: one AST walk is 80% of it, and there are two different builds"
description: "Timed in isolation, _check_intra_package_closure_guard is 11.84s of a 14.81s build against an empty target -- 80%. Its two sibling guards cost 0.03s and 0.02s. An earlier 39.07s-of-50.38s figure measured a different, more expensive build shape under load; the share survived, the absolutes did not."
type: explanation
status: active
created: 2026-10-05
last_updated: 2026-10-05
components:
  - build_pipeline
  - testing_quality
---

# Where a build's time goes

Part 2 of five. [Part 1](2026-10-05-pytest-ten-minute-target.md) gives the
verdict and the arithmetic.
[Part 3](2026-10-05-pytest-ten-minute-target-3-four-routes-not-two.md) covers
the mutator taxonomy.
[Part 4](2026-10-05-pytest-ten-minute-target-4-ci-sharding.md) designs the CI
split.
[Part 5](2026-10-05-pytest-ten-minute-target-5-the-combined-plan.md) sizes
everything.

## 1. There is no such thing as "a build" — there are two, and they differ ~3.5×

This has to come first, because almost every earlier number in this programme
conflated them.

| shape | what runs | who does it | measured |
|---|---|---|---|
| **A** | `build.py --target-dir <empty dir>` | the ~77 legacy test sites | **14.81 s** |
| **B** | `build.py --target-dir <its own root>` on a populated repo | `build-self.sh`, the shared-layout fixture, **and the CI pre-pytest step** | **52–56 s** cold, ~42 s warm |

Cost is driven by what is already in the **target**, not by the package source.
A build into an empty directory writes files; a self-targeting build into a
populated tree must additionally reconcile and remove what is already there.

So the circulating figures were never one measurement under different load:

- "59.8 s", "50.38 s", "~55 s" are **Shape B**.
- "~20 s on a GitHub runner", "21.7 s idle local" are **Shape A**.

**The shape the test suite actually pays is A.** That matters directly: the
suite's build burden is ~77 × 14.8 s ≈ **19 minutes** on an idle machine, not
the ~77 minutes a Shape-B price implies.

## 2. The closure guard is 80% of a Shape-A build

Timed by calling each guard directly, outside any build, so the measurement is
not an attribution from a profile (script:
`/home/henzeh/tq600a1-backup/time_guard.py`, read-only):

| guard | time | rc |
|---|---|---|
| `_check_script_reference_guard` | **0.03 s** | 0 |
| `_check_tracked_source_guard` | **0.02 s** | 0 |
| `_check_intra_package_closure_guard` | **11.84 s** | 0 |
| **total** | **11.90 s** | |

Against a 14.81 s Shape-A build that is **80%** of the whole thing, leaving
~2.9 s for everything else — consistent with the separately-measured 3.6 s for
all 35 deploy phases.

**Two corrections to earlier claims in this programme, both mine:**

**The absolutes were wrong.** An earlier pass reported "39.07 s of a 50.38 s
build, 77.6%", with `cProfile` independently agreeing at 78%. The share was
right; the numbers were a Shape-B build under heavy agent-fleet contention,
roughly 3.3× inflated. The proportion survived precisely because numerator and
denominator inflated together — which is why a percentage agreeing across two
methods felt like strong confirmation and was not: both methods measured the
same contended run.

This was caught by a cheap test that should have been run first. The guard's
only argument is `package_root` (§3), so its cost cannot depend on the build
target. A 39 s guard therefore cannot fit inside a 14.81 s build. Two reported
numbers were arithmetically incompatible, and timing the guard in isolation
took one command.

**"One cache covers all three guards" is true but oversells it.** The two
sibling guards are free. The cache is about one function.

The hot frames remain as profiled — Python `ast` walking source trees, with
`iter_child_nodes`, `iter_fields` and ~40 M `isinstance` calls dominating: the
signature of a hand-rolled recursive AST walk, per module, with no memoisation.

## 3. The guard's input does not depend on what is being built

`scripts/build.py:1167`:

```python
def _check_intra_package_closure_guard(package_root: Path) -> int:
```

One argument, and `package_root` is not the build target —
`scripts/build.py:1838` computes it as `Path(__file__).resolve().parent.parent`,
the package's own source directory. Identical for every build launched from a
given checkout regardless of `--target-dir`.

All three guards go through one loop,
`scripts/build_main_helpers.py:181`:

```python
    if not args.validate_only:
        for guard in script_reference_guards:
            if guard(package_root):
                return 1
```

They are uniformly target-independent by construction — the loop could not
pass anything else. So when N tests build against N different temporary
directories from the same checkout, they compute the **same verdict from the
same bytes N times**.

A cache therefore needs one key (a fingerprint of the package source) and one
invalidation point. It must replay the guard's diagnostic output on a cached
*failure*, not just the exit code, or it preserves failure detection while
degrading failure reporting.

## 4. Skipping the guard is not an option, and a test already proves it

`unit_tests/test_bp_900g_8.py`, around line 608, records the experiment having
already been run:

```
#   `if False and _check_intra_package_closure_guard(package_root)` (disconnecting
#   the closure guard from the build, restored immediately after) makes this
```

— the test goes **red**. The `BP-900g-8` family exists to prove the guard
fires: it mutates the package to create a deploy-manifest gap, builds, and
asserts the build *fails*. A guard that never runs cannot fail, so those tests
would invert and go green against a package that stopped checking anything.

The defect class is not hypothetical. `CLAUDE.md` documents **seven**
instances, including `done_proof.py`, whose omission from the deploy manifest
would have blocked every merge in the repo once its gate became required.

**Run once, cache the verdict** preserves the signal exactly and removes only
the redundancy. Part 5 §2 shows that the population it helps is the same one
TQ-600a's migration removes, which decides the sequencing.

## 5. A second, one-line cost in the same build

`scripts/template_compiler.py:123`:

```python
        fm = yaml.safe_load(fm_text) or {}
```

PyYAML's **pure-Python** loader while the C extension is available
(`yaml.__with_libyaml__` is `True` here). Measured against the real 101-block
frontmatter corpus this build compiles: **0.415 s → 0.042 s**, roughly 10× on
that call, about **2.2 s per build**.

Small against 11.84 s, but it is one line, and the same pattern was
independently measured as the dominant cost in the AC store's hot path — 98.8%
of a 54-second run, see
[the fast-lane claim analysis](2026-09-30-fast-lane-claim-cost-2-where-the-time-goes.md).
Two sites, one cause, two measurements: enough to make "use the C loader where
one exists" a candidate convention rather than a local fix.

The guarded form matters, since `CSafeLoader` is absent when PyYAML is built
without libyaml:

```python
try:
    from yaml import CSafeLoader as _Loader
except ImportError:          # PyYAML built without libyaml
    from yaml import SafeLoader as _Loader
```

## 6. Measurement provenance

Every figure in §1 and §2 was taken on this host **while a full instrumented
suite run was in progress**, so all of them are somewhat inflated and the true
idle numbers are lower. They are not inflated *relative to each other*, which
is what the 80% share depends on.

The honest reading: trust the **shares** and the **ratios** here, treat the
absolutes as upper bounds, and re-measure on an idle host before quoting them
as targets. The 39 s error above happened by treating a contended absolute as a
property of the code.
