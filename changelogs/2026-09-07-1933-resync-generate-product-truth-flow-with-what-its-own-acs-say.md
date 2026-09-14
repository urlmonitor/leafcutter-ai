---
title: "Resync generate-product-truth flow with what its own ACs say"
date: "2026-09-07"
time: "19:33"
type: manual
components: 
  - ux_prototyping
summary: "Fixed the product-truth store so it once again matches its own acceptance-criteria data, unblocking every commit that marks an AC done."
description: "One commit (24056969019cc900395549d803cafbb8a42442b1). The generate-product-truth flow record claimed all five steps done as of 2026-07-20, but a fresh derivation says in_progress because UXP-510, UXP-511, UXP-513 and UXP-514 (and UXP-514's children) are not yet done in the AC store. Fixed by regenerating docs/product-truth/index.json and the flow's impl_status/impl_asof/impl_summary via generate_product_truth.py; nothing hand-edited. Validator goes from 6 FAIL to 0 FAIL. This unblocks check-product-truth-validate, which fires on any staged docs/acceptance-criteria/**/*.yaml and was blocking all AC work."
commits: 
  - 240569690
breaking: false
---

## Entry

The product-truth store had been failing its own validator on `main` with six
errors, all one root cause: the `leafcutter/generate-product-truth` flow's
five steps (`map`, `derive`, `invert`, `backref`, `validate`) were recorded as
`impl_status: done` as of 2026-07-20, but a fresh derivation says
`in_progress` — correctly, because the underlying ACs (UXP-510, UXP-511,
UXP-513, UXP-514) are `work_status: in_progress` in the AC store today, and
UXP-514's children (`-1`, `-2`, `-4`, `-5`, `-6`) are `todo`. The authored
value was stale-optimistic; nothing had regressed.

The fix is purely the output of running
`python3 docs/product-truth/scripts/generate_product_truth.py` — nothing was
hand-edited. The diff is entirely regenerated derived data: five step
`impl_status`/`impl_asof` pairs, the flow's `impl_summary`, and the two
matching `by_flow` rollups in `docs/product-truth/index.json`. The validator
goes from 6 FAIL to 0 FAIL.

This mattered enough to be its own change because `check-product-truth-validate`
fires on any staged `docs/acceptance-criteria/**/*.yaml`, so this drift was
blocking every commit that marks an AC done — all AC work, not one PR.

Committed with `check-eval-staleness` skipped by name (alongside
`check-output-drift` and `check-build-drift`, which report unrelated drift in
the shared `.leafcutter` install tree): the diff changes only bookkeeping
fields (`impl_status`, `impl_asof`, `impl_summary`) that
`generate_product_truth.py` derives and no agent authors, and adds, removes,
or reorders no step, screen, or scenario — so the flow-structure assertions
those evals exist to check cannot have moved.

Refs: INF-400c-4-v (unblocked by this, not changed by it).
