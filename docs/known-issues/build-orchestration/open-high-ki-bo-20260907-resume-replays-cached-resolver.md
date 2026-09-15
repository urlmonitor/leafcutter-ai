---
title: "KI-BO-20260907-resume-replays-cached-resolver — `resumeFromRunId` replays the resolve step's cached `agent()` result instead of re-running it, and the fresh-run alternative is itself blocked by the failed run's leftover worktree"
description: "KI-BO-20260907-resume-replays-cached-resolver — `resumeFromRunId` replays the resolve step's cached `agent()` result instead of re-running it, and the fresh-run alternative is itself blocked by the failed run's leftover worktree"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-20260907-resume-replays-cached-resolver — `resumeFromRunId` replays the resolve step's cached `agent()` result instead of re-running it, and the fresh-run alternative is itself blocked by the failed run's leftover worktree

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-09-07 · **Last seen:** 2026-09-07
- **Where:** this is a runtime/harness-behaviour defect (the Workflow tool's
  `resumeFromRunId` semantics), not a repo-file defect — evidenced by run ids
  (`wf_65c0de2c-f42`) rather than file:line, the way the register's existing fast-lane
  run-behaviour entries above do. The repo artifact it is structured against is
  `templates/workflows-js/fast-lane-ship.js`: its resolve step is an `agent()` call
  (`resolverResult = await agent(...)` at `:656-671`, `agentType: "status-checker"`,
  `label: "resolve-connected"` at `:666-668`) — which is why its result is cached across a
  resume. This is a defect in how the workflow is *structured* against resume semantics (an
  agent-call step is memoized), not a bug in the harness being wrong to cache agent results.

**Symptom.** After fixing `KI-BP-20260907-bootstrap-swallows-build-failure`'s deploy gap by
hand (running `build.py` manually so `.leafcutter/scripts/build_orchestration/` was fully
populated), resuming the halted run via
`Workflow({scriptPath: 'templates/workflows-js/fast-lane-ship.js', resumeFromRunId:
'wf_65c0de2c-f42', args: {ac: 'GE-127b-1'}})` returned the identical error in 79ms with 0
`tool_uses` and 0 `subagent_tokens` — it replayed the stored failure from the resolve step
and never re-ran the resolver against the now-correctly-deployed tree. A fresh run (no
`resumeFromRunId`) was required instead.

That fresh run then itself failed at the worktree-creation phase, because the *previous*
(failed) run's worktree and branch still existed on disk and in git — full recovery required
`git worktree remove --force` plus `git branch -D` on the leftovers before the fresh run
could proceed.

**Why this is two defects, not one.** Fixing only the replay half still leaves an operator
stuck on the leftover-state half, and vice versa:

1. **The documented recovery path (resume) is a no-op for an environmental failure.** The
   resolve step is an `agent()` call, and its result is cached/memoized by run id. When the
   underlying failure was environmental (an incomplete deploy, now fixed) rather than a bad
   AC id or a genuinely-empty build set, resuming cannot help — it does not re-run resolution,
   it replays the resolution that failed before the fix was applied.
2. **The real recovery (a fresh run) collides with the failed run's own leftovers.** A fresh
   run does not detect or clean up the previous run's worktree/branch; it errors on the
   collision instead, so the operator must manually locate and remove the stale worktree and
   branch before a fresh run can even start.

**Distinct from KI-BO-20260831-1331.** That entry is about a worktree that never registered
with `git worktree list` at all — invisible, uncleanable via any documented git command. This
entry's worktree and branch *did* register normally (the prior run had completed enough of
worktree creation to produce a real, listed worktree) — the problem here is that the leftover
artifacts from that failed run collide with the fresh run that recovery requires. The two
share a family (worktree-lifecycle state surviving a failed fast-lane run in a form later
tooling cannot handle) but are separate failure points: one is "not visible to the cleanup
tool," the other is "visible, but blocks the retry path instead of being reused or cleared."

**Fix direction.** Either (a) restructure the resolve step so it is not a cached `agent()`
call on resume — re-run resolution unconditionally on resume, or invalidate the cached result
when the underlying environment/deploy state has changed since the original run — and/or (b)
have a fresh run detect and clean up a previous failed run's worktree/branch automatically
(mirroring the atomic/self-cleaning suggestion in KI-BO-20260831-1331's fix direction) rather
than erroring on collision. Both are needed: (a) alone still leaves a fresh run blocked by
leftovers; (b) alone still leaves resume silently useless for any environmental failure.

**Pattern:** a documented recovery path (resume) that is structurally incapable of re-running
the step whose result changed, paired with a fallback recovery path (fresh run) that a
different piece of leftover state blocks — so neither path recovers alone.

---
