---
title: "KI-ACD-007 — Product-truth artifacts are written to the user's main checkout, not the authoring worktree"
description: "KI-ACD-007 — Product-truth artifacts are written to the user's main checkout, not the authoring worktree"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-23'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
---

# KI-ACD-007 — Product-truth artifacts are written to the user's main checkout, not the authoring worktree

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/workflows-js/plan-feature.js` — PT phase (`mock-data-author` dispatch)

**Symptom.** `mock-data-author` wrote its artifact into the **user's main checkout**
rather than `AUTHORING_WORKTREE_PATH`, and modified a tracked file there. After the run:

```
leafcutter-ai/  (branch: main)
  ?? docs/product-truth/mock-data/guardrails/secret-scanning.mock.json   (510 lines)
   M docs/product-truth/index.json                                        (+68/-1)

worktrees/guardrail-engine/  (branch: ac-authoring/guardrail-engine)
  (no AC or product-truth changes at all)
```

The isolation the skill promises in §MP.1 — *"No AC files are written to the user's main
checkout"* — does not hold for product-truth artifacts. The worktree is created, then
not used.

**Why it matters.** It leaves `main` dirty with unreviewed generated output. In this
repo a dirty `main` is actively dangerous: a concurrent `finalize-feature` run resets it,
and the stray files are then either lost or swept into an unrelated commit. It also
defeats §PRR, whose orphan scan is scoped to the *authoring worktree* and to
`docs/acceptance-criteria/` only — so a stranded product-truth draft in the main
checkout is invisible to the recovery pre-flight that exists to catch exactly this.

**Fix direction.** Anchor the PT-phase agent dispatches to `AUTHORING_WORKTREE_PATH` the
same way the AC-stage commits are anchored with `git -C`. Then extend the §PRR orphan
scan to cover `docs/product-truth/` alongside the AC store, so a stranded draft is
detected on the next run rather than sitting in the user's checkout indefinitely.

**Workaround used 2026-08-18.** Moved the stranded mock-data file into the
`safety-security` worktree, reverted `docs/product-truth/index.json` on `main`, and
removed the untracked file — restoring `main` to clean.

**Re-verified 2026-09-23:** still true. Read the current PT-authoring loop in
`templates/workflows-js/plan-feature.js`. `ptStoreDir` is declared once as a bare
relative literal — `const ptStoreDir = "docs/product-truth";` (`:2693`) — and is never
reassigned to a worktree-anchored absolute path anywhere in the file. Compare this
directly with the AC-store side, which received exactly the fix this entry's "Fix
direction" asked for: `acStoreDir` is overridden from `wtPayload.ac_store_path` (an
absolute path inside the authoring worktree) at `:2513`, and the AC-authoring dispatch
prompt (`:3096-3098`) explicitly tells the agent `Write AC YAML files ONLY to
${acStoreDir}. Do NOT write AC files to docs/acceptance-criteria/ relative to the
current checkout — use the absolute path ${acStoreDir} instead.`

The PT-authoring dispatch prompt that tells `mock-data-author` / `mockup-author` /
`flow-author` where to write (`:2760-2774`) has no equivalent. It reads: `Draft or
extend the ${ptStep.stage} artifact for this request in the product-truth store at
${ptStoreDir}` — i.e. the bare relative string `"docs/product-truth"` — with no
absolute-path anchor and no "do not write relative to the current checkout" warning.
`grep -i "worktree\|cwd\|checkout" templates/agents/mock-data-author.md` returns
nothing: the agent template itself has no independent awareness that it might be
running against the wrong checkout, so it depends entirely on the dispatching prompt
to tell it — and the PT-side prompt does not. The isolation fix landed for one store
and was never mirrored to the other. The mechanism this entry describes is unchanged
and still reproducible by the same path as the original sighting.

---
