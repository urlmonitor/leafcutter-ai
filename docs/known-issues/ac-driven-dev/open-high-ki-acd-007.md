---
title: "KI-ACD-007 — Product-truth artifacts are written to the user's main checkout, not the authoring worktree"
description: "KI-ACD-007 — Product-truth artifacts are written to the user's main checkout, not the authoring worktree"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
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

---
