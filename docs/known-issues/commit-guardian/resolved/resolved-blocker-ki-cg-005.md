---
title: "KI-CG-005 — `check-product-truth-validate` / `check-product-truth-generate` hard-fail on an absent, explicitly optional product-truth store, gating every AC YAML commit"
description: "KI-CG-005 — `check-product-truth-validate` / `check-product-truth-generate` hard-fail on an absent, explicitly optional product-truth store, gating every AC YAML commit"
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

# KI-CG-005 — `check-product-truth-validate` / `check-product-truth-generate` hard-fail on an absent, explicitly optional product-truth store, gating every AC YAML commit

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../../commit-guardian.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** blocker
- **Status:** resolved — see "Re-verified and closed 2026-09-23" below
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/scripts/commit_guardian/commit_guardian.json:986` (`check-product-truth-validate`) and `:999` (`check-product-truth-generate`)

**Symptom.** Both hooks declare `files: "(^docs/product-truth/|^docs/acceptance-criteria/.*\\.yaml$)"`,
so they fire on **any staged AC YAML**, not only on product-truth artifacts, and both invoke
scripts living under `docs/product-truth/scripts/` (`validate_product_truth.py`,
`generate_product_truth.py`). `check-product-truth-validate`'s own `_comment` states the
posture plainly: *"jsonschema is a HARD dependency (validator exits 2 if absent — never a
silent no-op)."* But the product-truth store is **opt-in** — the `/plan-feature` skill
documents the intended behaviour on its absence: *"When the product-truth store is absent
the PT phase self-skips non-silently and AC authoring still proceeds"* (AC UXP-595a). The
defect is the disagreement between these two, not either half on its own: the workflow is
explicitly designed to degrade gracefully when the store is absent, and the hooks treat that
same absence as a hard failure. A consumer who never opted in cannot commit *any* AC YAML —
the optional feature's absence gates the mandatory one.

**Evidence.** Reported by a consumer project (DIAGraph) on 2026-08-18. Their
`docs/product-truth/` directory exists only because `build.py` deploys schemas and scripts
into it; zero of their docs reference the feature and they never opted in. They had been
running `/plan-feature` without the PT phase throughout, exactly as designed — and were then
blocked from committing by these two hooks the first time an AC YAML was staged.

**Relationship to KI-CG-002.** Same root shape as KI-CG-002 above: a guard behaving badly
when a file or store it depends on is not present. KI-CG-002 silently swaps its enum source
for a second one on that absence; this pair fails loudly and totally on it — but in both
cases the guard never asked "is my dependency supposed to be here?" before acting on its
absence.

**Fix direction.** The fix is not "add a guard to the hook" in isolation — the workflow
already encodes the decision that product-truth is optional. Make the hooks agree with it:
skip when the store is absent, the same way the workflow does. Pick one answer to "is this
optional?" and have both halves honour it.

**Re-verified and closed 2026-09-23.** ACD-2100 did not touch this mechanism, but
EPIC-TruthfulProjectRecord (UXP-700a-1 / UXP-700a-2 / UXP-700b-1 / UXP-700b-2, landed
2026-09-09 through 2026-09-17, all in the current worktree) closes it by a different route
than the "skip when absent" direction proposed above: instead of the hooks detecting
"is product-truth opted into?", `build_phases_product_truth.py::_scaffold_product_truth_record`
now write-if-absent scaffolds a complete, runnable, EMPTY record on every `build.py` run
(`flows/`, `mock-data/`, `mockups/` directories, an `index.json` declaring zero artifacts,
and — the file this bug's original repro was missing — `classifier/eval.jsonl`), so the store
is never structurally absent for a deployed consumer, opted in or not. `validate_product_truth.py`
and `generate_product_truth.py` were separately hardened (same epic) to treat an empty store as
`"nothing-examined"`/no-diff rather than crashing or hard-failing (`run_checks()`'s
`_top_level_outcome`, `write_index`'s "A missing `index.json` is rebuilt... rather than
crashing (UXP-700a-2)").

Confirmed by reproducing the exact reported scenario — schemas + scripts deployed, zero
flows/mock-data/mockups authored, one AC YAML with no `product_truth` field, "never opted in"
— against the current source:

```
$ python3 validate_product_truth.py --quiet   # (against a from-scratch, unauthored store)
{"outcome": "nothing-examined", "examined": 0, ...}
exit: 0

$ python3 generate_product_truth.py --check --quiet
(no output)
exit: 0
```

Both hooks' `files:` trigger in `commit_guardian.json` still fires on any staged AC YAML —
that half of the original complaint is textually unchanged — but it no longer matters: a
run against an absent/never-authored store now exits 0 with a stated "nothing-examined"
outcome instead of hard-failing, so the optional feature's absence no longer gates the
mandatory one. The specific mechanism this entry named — jsonschema-hard-dependency-shaped
crash-or-refuse on missing store content — is gone; the `_comment`s in
`commit_guardian.json` describing that dependency refer only to the `jsonschema` **package**
being absent (a different, correctly-hard-failing case, unrelated to this defect).
