---
title: "The reachability ACs no longer tell a coder to refuse what the observer cannot see"
date: "2026-10-21"
time: "12:00"
type: manual
components: 
  - ac_store
summary: "Five acceptance criteria for the done-proof reachability rule had a technical contract that still described the old observation record, and one of them told the implementer to refuse a criterion whenever the observer could not watch its proof. That is the opposite of what the sibling criterion BO-2900a-2-ii requires. The contracts now agree: an unwatched or undecidable observation gives no verdict, never a refusal."
description: "AC-store records only; no code changes. BO-2900a-1: expects_from now consumes BO-2900a-2's amended reach_record (tri-state reached_through, entry_points list, observation/unwatchable_cause) instead of the pre-amendment shape (one target, two booleans); the constraint 'a missing observation fails closed with refusal_cause observation_unavailable' is replaced by 'an unwatched or undecidable record gives no verdict and is announced on the finding channel'; 'observation_unavailable' is removed from the reachability_verdict and delivers_to refusal_cause enums; the unit is drawn from the AC's own implemented_by rather than from the proof's imports (aligning to BO-2900a-1-iv); the deploy-map citation is corrected to scripts/build_phases_ac_store.py. BO-2900a-1-i: reached_through becomes the tri-state value in its config_schema_fragment and expects_from. BO-2900a-1-ii: 'observation_unavailable' is retired as a cause; the finding record carries unwatchable_cause and undecidable_cause alongside a nullable refusal_cause. BO-2900a-5: the diagram contract depicts the unwatched/undecidable case as a no-verdict pass-through, not as a third refusal. BO-2900a-2: removed a note telling the implementer BO-2900a-1 was still unamended, which this change made false. Protected fields (criteria, title, req_status, depends_on), test_spec, work_status and readiness are unchanged in all five records, so no amended_by entries are needed. validate_ac_schema.py over the BO-2900 folder: OK, all 58 valid."
commits: []
breaking: false
---

## Entry
