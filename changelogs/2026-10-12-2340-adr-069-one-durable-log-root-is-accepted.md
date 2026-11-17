---
title: "ADR-069 (one durable log root for every workspace) is Accepted"
date: "2026-10-12"
time: "23:40"
type: manual
components: 
  - infrastructure
  - feedback_collector
summary: "ADR-069 moves from Proposed to Accepted. BrainCandy accepted it on 2026-10-12, after the epic that implements it merged as PR #1169."
description: "One documentation commit (3bc687de8). In docs/architecture/adrs/ADR-069-durable-log-root-for-workspaces.md the Status table now reads Accepted, naming BrainCandy, the date and the PR #1169 merge (818c301c0). The paragraph saying the ADR stays Proposed until the epic merges is replaced by a dated acceptance note with the full merge SHA, and the Implementation record now says the work was built in PR #1169 rather than on the epic branch. Frontmatter status stays active, per write-adr.md section 5. No code changes."
commits: 
  - 3bc687de8
breaking: false
---

## Entry

**ADR-069 is Accepted.** BrainCandy accepted it on 2026-10-12. The epic that implements
it, EPIC-OneDurableLogRootForEveryWorkspace, merged as PR #1169 (`818c301c0`).

- **Status table** now reads `Accepted`, naming the decider, the date and the merge.
- **Acceptance note**: the paragraph saying the ADR stays `Proposed` until the epic merges
  is replaced by a dated note with the full merge SHA.
- **Implementation record** now says the work was built in PR #1169, not on the epic
  branch.

Frontmatter `status` stays `active`, as write-adr.md §5 requires. No code changes.
