---
title: "KI-SS-005 — Concurrent agents in one worktree each report their siblings' files as another session's stray work"
description: "KI-SS-005 — Concurrent agents in one worktree each report their siblings' files as another session's stray work"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - supervisor_system
related_docs:
  - docs/known-issues/supervisor-system.md
  - docs/known-issues/README.md
---

# KI-SS-005 — Concurrent agents in one worktree each report their siblings' files as another session's stray work

> One known issue, split out of `docs/known-issues/supervisor-system.md` on
> 2026-09-14. Index: [supervisor-system.md](../supervisor-system.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open — no AC
- **Occurrences:** 1 (4 agents, 1 dispatch, all four identical)
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `templates/agents/product-owner.md`, `templates/agents/business-analyst.md`,
  `templates/agents/it-po.md` — none states that the agent may be one of several concurrent
  writers in the same tree. The fan-out site inherits the gap rather than causing it.

**Symptom.** Four AC-authoring agents were dispatched in parallel into one shared worktree. Each
ran `git status`, saw untracked AC YAML it had not written, and reported it — unprompted, in its
sign-off — as unrelated pre-existing work from other parallel sessions, recommending it be left
alone. Every file so described had been written minutes earlier by a sibling in the same dispatch.
All four made the same call independently.

**Why it is not just noise.** The inference is locally sound: an agent sees untracked files it did
not create, and nothing in its prompt says a peer might be writing beside it, so "another session"
is the only available explanation. That makes it a systematic misreading rather than a mistake any
one agent could avoid.

Three costs, in ascending order of seriousness:

1. **The operator gets four contamination reports for one clean tree.** Each is individually
   credible and, read together, suggests the worktree is unusable — the exact opposite of the
   truth.
2. **Staging advice is wrong in a way that looks careful.** "Leave these alone, they are not
   yours" is the correct instinct applied to the wrong facts; followed literally at commit time it
   drops the sibling work the same drive just produced.
3. **The failure mode is one step away.** An agent that decides stray untracked files should be
   cleaned up rather than preserved would destroy peer output, and untracked AC and ticket folders
   are unrecoverable. Nothing observed here went that far — no work was lost — and the reason is
   that all four chose the conservative branch, not that anything prevented the other one.

**Fix direction.** Tell the agent what it is. A dispatched agent that may run concurrently should
be told so, and told the rule that follows: files you did not write are peers' work — never
foreign, never stray, never yours to clean up or to characterise in a sign-off. The narrow,
mechanical form of the rule is that an agent stages by explicit path (`git commit -- <paths>`,
already the project's practice) and reports only on paths it wrote, which makes the whole
distinction moot rather than requiring the agent to reason about it correctly.

Resist fixing this by having each agent work out who wrote what — timestamps and `git status`
cannot answer it, and an agent that guesses confidently is what produced the reports above.

**Related:** `build-pipeline.md`'s `KI-BP-20260826-1331` is the same shape at the filesystem layer
— shared mutable state written by parties who do not know each other exist. There, the writers
collide; here, they only misdescribe each other. Project memory *"Commit into a dirty shared
tree"* records the operator-side half of this.

**Pattern:** an agent reasoning correctly from a prompt that never told it it had company.

---
