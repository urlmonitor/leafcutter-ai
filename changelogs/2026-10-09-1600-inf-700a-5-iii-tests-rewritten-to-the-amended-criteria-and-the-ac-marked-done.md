---
title: "INF-700a-5-iii tests rewritten to the amended criteria, and the AC marked done"
date: "2026-10-09"
time: "16:00"
type: manual
components: 
  - knowledge_system
  - infrastructure
summary: "The INF-700a-5-iii concurrency tests asserted criteria that PR #1078 retracted. They are rewritten to the amended criteria and run the real routing CLI over real scratch git with one shared claim store. The three descriptors that had no test now have one. All six pass, so the AC is marked done."
description: "Two commits. 998a39643 rewrites unit_tests/workflows/test_inf_700a_5_iii.py and adds the helper unit_tests/workflows/_inf700a5iii_scratch.py (a bare origin, a base clone, linked worktrees, one shared sink and claim store, and a file-barrier process launcher that checks the runs overlapped). Two retracted tests are replaced under their new descriptor names, test_neither_run_concludes_the_other_has_it is rewritten to its new assertions, and tests are added for the bookkeeping, lost-learning and no-delay descriptors and for the degraded-path clause. 8c9b04a77 flips INF-700a-5-iii work_status from todo to done. The parent INF-700a-5 stays todo because INF-700a-5-i and INF-700a-5-ii are still todo. No production code changed."
commits: 
  - 998a39643
  - 8c9b04a77
breaking: false
---

## Entry

The BA amendment to INF-700a-5-iii (PR #1078) retracted the promise that a learning is written
once across unmerged branches. Two unmerged overlapping runs now both write it: a bounded
duplicate is the accepted failure, and a loss is not. The arbitration now governs the **claim**,
not the write. The old tests still asserted the retracted behaviour, and they only called
`claim_and_confirm_routed` from threads.

- **Rewritten** (998a39643): every test now runs `completion_routing_cli.py`, or the claim step
  for the arbitration off switch that is deliberately not on the CLI, in separate processes. Each
  process works in its own linked worktree of a real scratch install, and all of them share one
  claim store. Each test checks that the runs actually overlapped.
- **Six descriptors covered**: no mark at write or commit time, and at most one copy per branch;
  neither run defers to the other; the claim store survives 20 overlapping pairs; a discarded
  branch loses nothing; a concurrent unit of work gives the same result as a solo run; and
  1 claim with the arbitration on versus 2 with it off.
- **Degraded paths**: an unresolvable or unfetchable base branch writes again and marks nothing,
  and an unopenable lock still claims, unarbitrated.
- **AC** (8c9b04a77): INF-700a-5-iii `work_status: done`. The parent INF-700a-5 stays `todo`
  because -5-i and -5-ii are still `todo`.

No production code changed.
