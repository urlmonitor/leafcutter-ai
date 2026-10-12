---
title: "Feedback-sink epic scaffolded: seven tickets ready for build-feature"
date: "2026-10-09"
time: "19:30"
type: manual
components: 
  - feedback_collector
  - infrastructure
summary: "EPIC-OneDurableLogRootForEveryWorkspace is generated from the seven approved INF-500d-4 children, so /build-feature can drive it. The generator output was corrected by hand: dependencies follow the AC's build order, empty files_touched lists are filled from each AC's declared files, and the truncated epic name is replaced. Tickets and AC back-references only; no code changes."
description: "One content commit (3a8f82b5c), tickets and AC store only. goal_to_epic.py --ids generated seven tickets from INF-500d-4-iii, -i, -iv, -v, -vi, -vii and -viii (INF-500d-4-ii is already done and excluded), plus a Master_Plan, in the epic folder EPIC-OneDurableLogRootForEveryWorkspace under tickets/00_inbox/epics/. The folder was renamed because the generator's name was truncated mid-sentence. Hand fixes: depends_on wired to INF-500d-4's sequencing (-iii; then -i, -iv, -v; then -vi; then -vii and -viii); files_touched filled from each AC's declared_files where the generator left it empty, with the ticket's own test file added, and two wrong entries corrected (01 listed two ADRs it only obeys, 07 listed scripts/next_diagram_seq.py, a tool it runs); ac-validator and ac-fulfillment-gate set to needed on 05 and not_needed on 07; requires_diagram true on 07, the diagram ticket. Each AC's implemented_by now names its epic-folder ticket. No criteria, readiness or work_status changed."
commits: 
  - 3a8f82b5c
breaking: false
---

## Entry

The feedback-sink work is now an epic that `/build-feature` can drive:
`EPIC-OneDurableLogRootForEveryWorkspace`, under `tickets/00_inbox/epics/`.

- **Seven tickets**, one per approved INF-500d-4 child. INF-500d-4-ii is already done and
  is not included.
- **Build order** follows INF-500d-4's sequencing: `-iii` (the build declaration and
  worktree bootstrap) first; then `-i`, `-iv` and `-v` (writers and readers); then `-vi`
  (prompt surfaces); then `-vii` (reference docs) and `-viii` (diagram).
- **Generator output corrected by hand.** The dependencies follow that order. Empty
  `files_touched` lists are filled from each AC's declared files. Two wrong entries are
  fixed: ticket 01 listed two ADRs it only has to obey, and ticket 07 listed a script it
  runs rather than edits. The diagram ticket now says it needs a diagram. The truncated
  epic name is replaced.
- **AC back-references.** Each AC's `implemented_by` names its ticket in the epic folder.

No code changes.
