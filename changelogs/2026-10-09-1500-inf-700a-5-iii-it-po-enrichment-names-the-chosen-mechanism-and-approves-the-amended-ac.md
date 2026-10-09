---
title: "INF-700a-5-iii IT PO enrichment names the chosen mechanism and approves the amended AC"
date: "2026-10-09"
time: "15:00"
type: manual
components: 
  - knowledge_system
summary: "IT PO pass on INF-700a-5-iii after the duplicate-not-loss amendment (PR #1078). Stale technical fields now match the chosen mechanism and the code on main, and the AC moves from reviewed to approved. Criteria unchanged."
description: "One content commit (4f2f3c033), AC store only. INF-700a-5-iii: readiness reviewed -> approved, on BrainCandy's 2026-10-09 approval of the amended wording. it_requirements line 1 records that the install-scoped state file precondition is met on main (#1064). Line 2 re-sites the off switch from two writes to two claims and names arbitration_enabled on completion_routing.claim_and_confirm_routed. Line 3 rewords 'write-once clause' to 'single-claim clause'. Line 5 names the chosen mechanism (check-the-base-branch before claiming, flock-arbitrated claims, duplicate-not-loss) and the four completion_routing modules. The expects_from INF-700a-5 contract reads 'published' as 'text on origin/main' and names the claim store. The notes paragraph 'MECHANISM IS NOT CHOSEN HERE' is marked superseded and its reasoning kept. One test_spec description has the same 'write-once' -> 'single-claim' rewording, with assertions unchanged. A new it-po amended_by entry records all of this."
commits: 
  - 4f2f3c033
breaking: false
---

## Entry

IT PO enrichment of `INF-700a-5-iii` after the BA amendment merged in PR #1078. The
criteria text is unchanged.

- **readiness** `reviewed` -> `approved`. BrainCandy approved the amended wording on 2026-10-09.
- **it_requirements**:
  - Line 1 now says the install-scoped state file is in place on main (#1064). The fixture
    hazard stays.
  - Line 2: the off switch is about claims now, not writes.
  - Line 3: "write-once clause" is now "single-claim clause".
  - Line 5 names the chosen mechanism (check-the-base-branch before claiming, flock-arbitrated
    claims, duplicate-not-loss) and the `scripts/knowledge/completion_routing*.py` modules.
- **expects_from INF-700a-5**: "published" now means the learning's text is on `origin/main`.
  The contract also names the claim store.
- **notes**: the "MECHANISM IS NOT CHOSEN HERE" paragraph is marked superseded. Its reasoning
  is kept.
- **test_spec**: one description has the same "write-once" -> "single-claim" rewording. Its
  assertions are unchanged.

`work_status` stays `todo`. No code changes.
