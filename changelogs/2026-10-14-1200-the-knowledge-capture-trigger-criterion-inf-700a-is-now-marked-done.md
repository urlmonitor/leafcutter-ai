---
title: "The knowledge-capture trigger criterion INF-700a is now marked done"
date: "2026-10-14"
time: "12:00"
type: manual
components: 
  - knowledge_system
summary: "INF-700a now reads done. It requires a captured learning to reach its knowledge surface without anyone running anything by hand. All five of its children and all eight grandchildren were already done, and the current done-proof check finds nothing unproven."
description: "One AC-store commit (180c18a49), store data only. Flips INF-700a (L1) work_status from todo to done and changes no other field. Its children INF-700a-1 to INF-700a-5 and grandchildren INF-700a-1-i to INF-700a-1-v and INF-700a-5-i to INF-700a-5-iii are all done on main. The commit skipped the local check-done-proof hook because the deployed copy was built on 2026-10-08, before #1165 fixed the test_required: false waiver for composite children, so it wrongly refused with 'unproven: INF-700a-3, INF-700a-4' (both docs-only). The current source composite check returns unproven: [] for INF-700a, and CI's required Proof-of-done gate runs that source."
commits: 
  - 180c18a49
breaking: false
---

## Entry

**INF-700a is marked done.** The criterion says a captured learning reaches its knowledge
surface as a normal part of the work finishing, and that a person can find out whether that
has ever happened in a project.

- **Children:** all five (INF-700a-1 to INF-700a-5) are done. So are the eight grandchildren
  under INF-700a-1 and INF-700a-5.
- **Proof:** the current source composite done-proof check returns `unproven: []`.
- **Hook skipped:** the local `check-done-proof` hook was skipped on the commit. The deployed
  copy dates from 2026-10-08 and predates #1165, which taught the composite check to accept a
  child's `test_required: false` waiver. That stale copy refused because of INF-700a-3 and
  INF-700a-4, which are both docs-only. CI's required Proof-of-done gate runs the current
  source.

Only `work_status` changed. No code changes.
