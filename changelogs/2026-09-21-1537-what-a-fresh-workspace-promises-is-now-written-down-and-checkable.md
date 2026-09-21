---
title: "What a fresh workspace promises is now written down, and checkable"
date: "2026-09-21"
time: "15:37"
type: manual
components: 
  - build_orchestration
  - worktree_manager
summary: "BO-4100 states four properties a newly-created workspace must have -- it starts from the current shared line, is judged on what you changed, can be told apart from the ones still holding work, and is honestly described -- plus a fifth for the ones the listing cannot see. Nothing enforces any of them today."
description: "A worktree created by hand on 2026-09-14 ran for hours with every package pre-commit hook silently disabled, because a raw git worktree add skips the bootstrap that installs them. That is the second recorded occurrence. It is already specified -- BO-1700 was written from the same incident class in July and has sat unbuilt since -- so the two failures it covers are not re-authored here. What BO-4100 adds are four failures BO-1700 does not reach, each observed in the same session: the create-only path rooted a branch at a local main that was 39 commits behind while its two siblings rooted at the shared tip; both drift gates refused a commit whose staged diff contained no template file at all, reporting drifted=0 missing=0 while refusing; roughly 150 workspaces had accumulated with no way to tell which still held work; and every branch was labelled a feature regardless of the kind requested. A fifth criterion covers a workspace that is invisible to the listing entirely, cannot be classified, and cannot be removed. The request that prompted this asked for a skill telling an agent how to create a worktree correctly. That framing was rejected: the agent that created the bad worktree read no guidance first, and the guidance that exists today documents the symptom while offering a manual workaround instead of naming the canonical script, so it steers toward the broken path. All five criteria are written to resist their cheapest implementation -- one puts a passing pre-check in its Given so hardening the pre-check cannot satisfy it, another requires the identical commit to be accepted whether the branch is behind or level, another requires a genuinely damaged shared record to still be reported separately so the cheap pass of never mentioning it is closed. Tickets for the branch-naming family are generated and ready to build."
commits: 
breaking: false
---

## Entry
