---
title: "AC hierarchy was read from covered_by, so ADR-007-schema stores produced empty epics"
date: "2026-08-18"
time: "11:29"
type: manual
components: 
  - ac_store
summary: "Generating an epic from a goal returned nothing on stores that keep their criteria hierarchy in a children field, because the traversal looked for it in the field those stores reserve for test files. It failed silently — no error, just an empty epic."
description: "_dfs_collect_leaves in scripts/ac_store/scan_ac_store.py derived the parent-to-child hierarchy from the covered_by field. Stores following the ADR-007 schema reserve covered_by for test-file paths and keep the hierarchy in a separate children field, so on those stores the traversal walked from the root, found no children, and returned an empty or near-empty leaf set. Goal-mode epic generation then produced an epic with nothing in it, and because an empty result is indistinguishable from a legitimately empty subtree, nothing raised and nothing failed. The lookup now prefers children and falls back to covered_by only when its entries look like AC ids rather than test paths. The discriminator is intentionally narrow: a test path contains a / or a ::, an AC id never does. Stores that overload covered_by to mean children keep working unchanged via the fallback branch, and the recursion continues to visit superseded nodes so replacement children are still collected (ACD-1200a-10). Verification: unit_tests/ac_store/ passes at 487 passed, 3 skipped, 18 subtests, exit 0, which confirms the legacy covered_by-as-children path is not regressed. Not verified: an end-to-end goal-mode run against a store that actually uses children — the evidence here is the unit suite plus static confirmation, not observed behaviour, and this repo's own history says that distinction matters. Provenance: this fix existed as an unpushed local commit (cc19d00d, 2026-06-15) in a consuming repo and was silently lost when that repo advanced its submodule pin to f8cfdfc4 on 2026-08-14. Any consumer on the ADR-007 schema hits the same bug, so it belongs upstream rather than as a downstream patch that the next pin move deletes again."
pr: 471
commits: 
  - f02bb4c4
breaking: false
---

## Entry
