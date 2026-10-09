---
title: "INF-700a-5-iii: a duplicate across unmerged branches is accepted, a loss is not"
date: "2026-10-09"
time: "11:00"
type: manual
components: 
  - knowledge_system
  - infrastructure
summary: "INF-700a-5-iii no longer promises that a learning is written once and never twice. It now matches BrainCandy's 2026-10-08 confirmation mechanism (PR #1071): a learning is never lost between concurrent units of work, and a duplicate across branches that were unmerged at the same time is the accepted, bounded failure."
description: "One content commit (4766795b3), acceptance criteria only. Amends INF-700a-5-iii to match the confirmation mechanism BrainCandy decided on 2026-10-08 (PR #1071, merged as 235a210b). A record is never marked routed at write or commit time, and each run claims only records whose text is already on origin/main. The retracted clause said a learning is 'written to its destination file once and not twice'. That cannot hold when two unmerged branches both stage the same record. The new criteria say four things. A learning is never lost between concurrent units of work. A duplicate is allowed, at most one copy per branch that staged the record without finding its text on the base branch. Once the text is on the base branch, no later run writes it again. Runs that share the claim store do not both claim the same record. Every degraded path fails toward the duplicate. The arbitration-reachability clause now applies to claims, not writes. The title was updated to match. Three test_spec descriptors that asserted the retracted behaviour were rewritten, and two of them renamed. An amended_by entry (by: BrainCandy) records what changed, why, and what is not accepted. work_status stays todo. implemented_by, covered_by and it_requirements are unchanged."
commits: 
  - 4766795b3
breaking: false
---

## Entry

INF-700a-5-iii used to promise that two units of work finishing at the same time write a
learning **once and not twice**. That clashed with the confirmation mechanism BrainCandy
decided on 2026-10-08 (PR #1071). Under that mechanism a record is never marked routed at
write or commit time, and a run claims a record only once its text is already on origin/main.
So when two branches both stage the same record before either merges, both carry it.

- **Criteria amended.** A learning is never lost between concurrent units of work. A
  duplicate across branches that were unmerged at the same time is the accepted failure, and
  it is bounded. Once the text is on the base branch, no later run writes it again. Runs that
  share the claim store do not both claim the same record. Every degraded path fails toward
  the duplicate.
- **Asymmetry stated explicitly.** A learning written twice is visible to readers and
  survivable. A learning lost while marked as routed is not acceptable.
- **Title and three test_spec descriptors** were updated to match. Each rewritten descriptor
  is marked AMENDED.
- **Amendment recorded** in `amended_by` (by: BrainCandy).

Only acceptance criteria changed. No code changes. work_status stays `todo`.
