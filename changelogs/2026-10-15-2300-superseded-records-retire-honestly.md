---
title: "A superseded AC naming existing successors is retired honestly: the commit gates stop holding it to the is-it-built-and-tested-now rules (ACS-900d-4)"
date: "2026-10-15"
time: "23:00"
type: manual
components: 
  - ac_store
  - commit_guardian
summary: "An AC record with status superseded_by (or the older superseded) whose superseded_by list names records that exist, and not itself, is now retired. check-done-proof no longer demands a covering test for it, check-ac-schema no longer demands a test contract, and it neither blocks nor proves its parent. check-ac-schema now refuses a superseded record whose successor is missing, empty, null or itself. INF-600g-3 and INF-600g-3-i are the first records retired this way, superseded by AR-400c-1."
description: "One pure predicate, scripts/ac_store/ac_retirement.is_retired, decides retirement. It needs a superseded status, a non-empty superseded_by, every successor present in the whole store, and no self-reference. deprecated is never retired and req_status is ignored. It replaces the weaker is_superseded_ac (KI-ACS-016), which accepted any non-empty superseded_by or req_status: superseded. Every forward gate consults it: check_done_proof.py on the staged, ci-changed and ci paths (store ids are built once per run and the check fails closed), done_proof.verify_done_eligible, both composite rollups, validate_test_contract (only the must-declare-a-test-contract rule is waived; a contradictory contract is still refused), and check_ac_limits. A live composite whose children are all retired falls back to the single-record rule: it needs its own covers tag or a waiver. VALID_STATUSES and validate_ac_schema now accept superseded, matching config/ac_store_schema.json. A census of the 5,181-record store found no done composite that flips from pass to refuse. Twenty todo records lose their old withdrawn treatment: 16 deprecated records with req_status superseded and no successor, ACS-300g-2, and three active records that carry superseded_by. The how-to (ac-traceability-store.md) and the ac-schema.md status table describe the rule, and KI-ACS-20261015-superseded-records-held-to-forward-rules is resolved."
breaking: false
---

## Entry
