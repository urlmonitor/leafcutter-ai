---
title: "The record declares a reviewable size for what it holds, and a bound blocks only once nothing predates it"
date: "2026-09-14"
time: "09:05"
type: manual
components: 
  - ux_prototyping
summary: "The product-truth checker now measures journeys, datasets and screens against declared size bounds. It reports each bound's measured count and whether the bound is still in its warning period, and refuses a --tighten request while any artifact is still on an older shape version."
description: "Nothing in the product-truth record had a size limit, so the record could grow until no one reviewed it. The checker now carries one declaration of size bounds (UXP-700e-1): a journey's description (120 characters) and step count (20), a dataset's records per entity (50), and a screen's description (600 characters). Every bound took effect at shape version 2. An artifact over a bound is reported naming the artifact, the field, the measured size and the limit. Each bound states on the run's result line how many artifacts it measured, how many exceeded it, and how many are still on an older shape version, so a bound that measured nothing reads differently from one nothing exceeded. The description bound is the one the measurement motivated: all 14 journeys exceed it today, and since none declares a shape version yet, all 14 are warnings, not blocks. The other three bounds sit above today's largest value, so they add no findings. A bound leaves its warning period only when no artifact of its type is on an older shape version (UXP-700e-1-ii). The checker works this out from the artifacts on every run: no date ends the warning period, and no flag can end it. validate_product_truth.py --tighten BOUND refuses while any artifact is left behind and names each one. Datasets and screens gain the optional shape_version field journeys already had. A new reference, docs/reference/product-truth-size-bounds.md, covers four things: every bound, the rollout order a new bound follows (declare, warn, backfill, tighten), which fields are authored and which are derived, and the measurement behind the bounds (UXP-700e-4)."
commits: 
breaking: false
---

## Entry
