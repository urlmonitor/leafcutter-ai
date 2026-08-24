---
title: "fix(guardrail-engine): resolve the second GE-120 identifier collision, and stop the guard from freezing the tree it protects"
date: "2026-08-18"
time: 2115
type: manual
components: 
  - commit_guardian
  - ac_store
summary: "Two unrelated acceptance criteria were both called GE-120, so the store could not tell which one any piece of finished work belonged to. The newer one is renamed, and the test that guards the older one no longer blocks ordinary work on it."
description: "Two records on main both declared id GE-120: the L0 goal 'Trust that a green check actually checked something' (43 files, landed 2026-08-17 via PR #453) and an unrelated loose L2 about doc-type validation minted by a later /plan-feature run (landed 2026-08-18 via PR #466). The loose L2 shadowed the L0 in the store loader, so all five of the L0's children reported as orphans. The L2 is renamed to GE-118c and parented under GE-118, whose GE-118b is the same defect shape (a hand-counted parents[2] plus a hardcoded path segment resolving somewhere that never existed, so the gate silently no-ops). The id is suffix-shaped rather than a new root number because derive_parent_id returns None for a root-shaped id, so check_ac_parent_covered_by and scan_ac_orphans could not police its parent link at all. Verified store-wide: 3,185 records, 3,185 distinct ids, zero duplicates; the GE-120 orphan group is gone and no new group appeared. The record is marked done on verified evidence rather than on the code looking present: a fresh-subprocess import of the deployed module loads all 10 declared doc types where the bug loaded 7, the real hook accepts a card with no components field and still rejects an undeclared type by name, and the pre-fix code reconstructed from 160d4f47^ turns 3 of the 4 tests red. Its it_requirements #2 is amended to describe the resolver actually built, because marking a record done while one of its stated requirements is unmet is the phantom-done failure this component exists to prevent. Separately, test_ge_122e_1 required the GE-120 folder to be byte-identical to main. That was this ticket's own definition-of-done check and correct for the reconciliation PR, but as a permanent test it froze 43 records that are all work_status: todo — the first PR to implement any of them would have turned it red, and it is what closed the option of parenting the renamed record where it semantically belonged. It now asserts id-stability instead of content-identity: content may change freely, an id disappearing still fails. Proven by mutation in both directions."
breaking: false
---

## Entry
