---
title: "KI-CG-20260831-0713 — PARTIALLY fixed by BP-100k-4-ii; the adopter still cannot commit, for a different reason"
description: "blocker — unchanged. The reported symptom, \"a consumer project cannot make a"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260831-0713 — PARTIALLY fixed by BP-100k-4-ii; the adopter still cannot commit, for a different reason

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** blocker — unchanged. The reported symptom, "a consumer project cannot make a
  commit at all", still reproduces.
- **Status:** open. The kind-based half is fixed; the location-based half is not, and the
  location-based half is the larger population.
- **First seen:** 2026-08-31 · **Last seen:** 2026-09-07

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

**Re-verified 2026-09-23: STILL TRUE — unchanged, kept open.** The kind-based/location-based
distinction this entry describes (and that `BP-100k-4-ii` introduced in direct response to it)
is still exactly as documented — the mechanism is even self-documenting in the current source,
which names this entry by id:

```
$ grep -n "KI-CG-20260831-0713" templates/scripts/commit_guardian/commit_guardian.json
             (appears in __hook_trigger_reachability_nothing_to_match_doc, describing the
             COULD-EVER/DOES-NOW split this entry's "kind-based half" section documents)
```

`hook_trigger_reachability_exemption_registry` still exists and still governs only
location-anchored conditions (`_hook_trigger_reachability_helpers.py`'s
`has_location_anchor()` / `evaluate_gate()`, unchanged in shape from BP-100k-4-ii). The two
named residuals are still live and still un-exempted: `check-surface-components-e3`
(`files: "^(config/agent_registry\\.json|config/skill_registry\\.json|docs/roadmap\\.json)$"`,
`commit_guardian.json:1104`) and `check-eval-staleness`
(`files: "(^scripts/evals/|^docs/product-truth/|^templates/agents/)"`,
`commit_guardian.json:1147`) are both location-anchored `enabled: true` conditions, and neither
appears in `hook_trigger_reachability_exemption_registry`'s entry list. Running
`check_hook_trigger_reachability.py` against this self-hosted checkout (where nearly every
package-internal path is tracked) naturally reports `unreachable=0` — that is the exact trap
"Verify against source, not build output" warns about, since this repo is not the fresh,
minimal consumer install the entry's claim is about, and reproducing the consumer case would
require running `build.py` into a scratch target, which is out of scope for this pass. The
static evidence — the residual conditions exist, are location-anchored, are enabled, and carry
no exemption entry — is unchanged from the entry's own description. Mechanism confirmed
present in code; kept open per the letter of the decision rule (a live mechanism is not closed
for being inconvenient to reproduce).

**Scope note — this closes only the too-strict half.** The check still walks only
*registered* hooks, so a script the registry never mentions remains invisible to it
(`BP-1600a-2` and its siblings, `todo` on `main` as of this fix). That is a distinct, still-open
defect and is not resolved by this entry's closure.

---
