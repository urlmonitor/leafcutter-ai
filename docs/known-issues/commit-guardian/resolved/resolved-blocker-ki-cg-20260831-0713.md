---
title: "KI-CG-20260831-0713 — a fresh consumer install could not make its first commit because check-hook-trigger-reachability failed it (resolved by BP-100k-4-ii and BP-100k-4-iii)"
description: "blocker, RESOLVED 2026-09-28. The hook-trigger reachability gate reported unreachable=28 on a fresh consumer (2026-09-07). BP-100k-4-ii fixed the kind-shaped half and BP-100k-4-iii (PR #886) made untracked stageable paths count. A real consumer install from origin/main now exits 0 with unreachable=0. Regression guard: BP-900h-6-iii."
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-28'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260831-0713 — a fresh consumer install could not make its first commit because check-hook-trigger-reachability failed it (resolved by BP-100k-4-ii and BP-100k-4-iii)

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../../commit-guardian.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.
> Title before resolution: *"PARTIALLY fixed by BP-100k-4-ii; the adopter still cannot
> commit, for a different reason"*.

- **Severity:** blocker. The symptom was "a consumer project cannot make a commit at all".
- **Status:** **RESOLVED** (kind-shaped half by `BP-100k-4-ii`, PR #730; location-shaped half
  by `BP-100k-4-iii`, PR #886, done 2026-09-24; verified 2026-09-28 on a real consumer install
  built from `origin/main` and by an independent harness probe, see Resolution; regression
  guard `BP-900h-6-iii`)
- **Original status (2026-09-07):** open. The kind-based half was fixed; the location-based
  half was not, and it was the larger population.
- **First seen:** 2026-08-31 · **Last seen:** 2026-09-07 · **Verified gone:** 2026-09-28

**This entry was briefly marked CLOSED, and that was wrong.** The closure was written when
`BP-100k-4-ii` landed and it is corrected here rather than quietly amended, because a
blocker-severity entry reading CLOSED over a still-reproducing symptom is the exact failure
this register exists to catch — one level up from the code.

**What BP-100k-4-ii genuinely fixed.** `evaluate_gate` now draws a could-ever/does-now
distinction: a kind-based condition such as `files: '\.py$'`, matching zero tracked paths, is
reported under a fourth verdict `NOTHING-TO-MATCH` and does not fail the run, while a
condition naming a location no checkout could ever produce is still `UNREACHABLE` and still
blocks. See `BP-100k-4-ii.yaml` and `unit_tests/commit_guardian/test_bp_100k_4_ii.py`,
verified against a real `build.py`-deployed consumer tracking zero `.py` files. That work is
sound and is not in question.

**Why the symptom survives it.** Only three registered conditions are kind-shaped. The rest
are location-shaped, and a fresh consumer tracks almost none of those locations. Two
independent measurements on 2026-09-07:

```
runtime, real deployed consumer tracking one placeholder file (pr-reviewer):
  exit 1 · RESULT total=56 unreachable=28 exempt=6 nothing_to_match=7

static, counted from commit_guardian.json hooks_manifest:
  46 conditions carry a files pattern
   3 kind-shaped (check-placeholder-defaults, check-mermaid-complexity, check-exception-handling)
  43 location-shaped
  35 location-shaped AND absent from hook_trigger_reachability_exemption_registry
```

The two numbers differ because the static 35 is an upper bound — some location patterns do
match files a real install leaves tracked. 28 ≤ 35 is the expected relationship, and the
agreement in shape is what makes the runtime figure trustworthy rather than a one-off.

So `BP-100k-4-ii` moved 7 conditions out of the blocking set and left roughly 28 in it. The
adopter's first commit still fails.

**The residual this entry previously named, restored.** The pre-closure text flagged
`check-surface-components-e3` and `check-eval-staleness` as looking like the same omission
with no exemption. Both were re-confirmed still `UNREACHABLE` on 2026-09-07. They are not
special — they are two members of the ~28, and naming only them would understate the
population. They are kept here because they were the two already identified by name and
losing them was how this residual nearly went untracked.

**Fix direction, and what NOT to do.** Do not extend the exemption registry to ~28 entries to
make the number go to zero. An exemption is an audited statement that a specific condition
legitimately cannot match here, and mass-adding them converts an audited list into a
rubber stamp — the shape `BP-100k-4-i` was written to prevent. The real question is whether a
location-based condition naming a path that a *consumer install does not create* is
"unreachable" at all, or whether reachability must be evaluated against the layout the gate
is running in rather than against the package's own. That is a design decision about the
gate's frame of reference, and it wants an AC of its own rather than a patch.

**Related.** `BP-100k-4-ii` (the kind-based half, done). `BP-1600a-2` (the same gate's
opposite defect — it walks only registered hooks, so an unregistered script is invisible;
`todo`). `BP-900h-6-iii` (the consumer simulation must exercise a language-absent adopter, so
this class is caught by CI rather than by hand).

**Pattern:** a fix that is correct, well-tested, and closes the mechanism it names, mistaken
for a fix that closes the *symptom* — because the symptom had two independent causes and only
one was in scope.

**Scope note — this closes only the too-strict half.** The check still walks only
*registered* hooks, so a script the registry never mentions remains invisible to it
(`BP-1600a-2` and its siblings, `todo` on `main` as of this fix). That is a distinct, still-open
defect and is not resolved by this entry's closure.

## Resolution

Re-measured first-hand on 2026-09-28. The symptom is gone, and neither measurement needed a
new exemption.

- **Real consumer install.** Built from `origin/main` (this branch's base, `8ed47463`, which
  contains `24c03c0a`). The package was vendored at `leafcutter-ai/` as its own git repo, and
  the consumer was a separate git repo tracking nothing.
  `python leafcutter-ai/scripts/ci/check_consumer_install.py --package-dir leafcutter-ai --target-dir .`
  exited 0 with `CONSUMER INSTALL SIMULATION OK`. In the consumer,
  `python .leafcutter/scripts/commit_guardian/check_hook_trigger_reachability.py` then exited 0:

  ```
  check-hook-trigger-reachability: RESULT total=69 unreachable=0 exempt=6 nothing_to_match=1
    compared=72 registered=74 unreferenced=0 declared_non_gate=7
  ```

- **Independent probe.** An IT-PO probe with the `test_bp_100k_4_ii` harness shape (the real
  registry and a `build.py`-deployed synthetic consumer) also exited 0: `total=69
  unreachable=0 exempt=4 nothing_to_match=3`.
- **What fixed the location-shaped half.** `BP-100k-4-iii` (`b8465132`, merged via PR #886,
  done 2026-09-24): existing untracked, stageable paths now count as reachable, not only
  tracked ones. `build.py` deploys `docs/product-truth/` and `docs/roadmap.json` into the
  consumer root, so the two conditions named above, `check-eval-staleness` and
  `check-surface-components-e3`, are now REACHABLE. The `unreachable=28` figure in this
  entry was measured on 2026-09-07, before `-iii` landed.
- **Regression guard.** `BP-900h-6-iii` is being amended on branch `ac-authoring/ac-20260927`
  so that CI's consumer simulation must run `check-hook-trigger-reachability` on the
  adopter's first commit. Today
  `scripts/ci/_use_install_step.py:272` (`_isolate_precommit_registry_for_scratch_fixture`)
  withholds that hook from the scratch fixture, so CI could not have caught this entry's
  symptom.
- **The layout-frame design was withdrawn, not built.** The Fix direction above asked for a
  decision on the gate's frame of reference. Four L3s were drafted under `BP-100k-4` for it,
  then withdrawn by the user once the re-measurement showed no live symptom. The design is
  still available if a location gate that a consumer install cannot satisfy is ever
  registered. That would be a new entry, not a reopening of this one.

---
