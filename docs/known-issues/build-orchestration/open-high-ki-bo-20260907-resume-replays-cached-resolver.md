---
title: "KI-BO-20260907-resume-replays-cached-resolver — `resumeFromRunId` replays the resolve step's cached `agent()` result instead of re-running it, and the fresh-run alternative is itself blocked by the failed run's leftover worktree"
description: "KI-BO-20260907-resume-replays-cached-resolver — `resumeFromRunId` replays the resolve step's cached `agent()` result instead of re-running it, and the fresh-run alternative is itself blocked by the failed run's leftover worktree"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-27'
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
- **Occurrences:** 2 (fast-lane-ship 2026-09-07; finalize-feature 2026-09-25)
- **First seen:** 2026-09-07 · **Last seen:** 2026-09-25
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

**Occurrence 2 — 2026-09-25, `finalize-feature.js` Step 2: a git-state step replayed after the state
was fixed.** `/finalize-feature` of `feature/doc-index-posix-link-paths` (PR #892) halted at Step 2,
because `git merge origin/main` conflicted. The conflict was resolved by hand, committed as
`dbcc7014` ("Merge remote-tracking branch 'origin/main' into feature/doc-index-posix-link-paths"),
and pushed. Resuming with `resumeFromRunId` halted again **in 559 ms with 0 tokens**, replaying the
cached `{"status": "conflict"}`.

The cause is the same as in the first occurrence, on a step whose result is even more obviously
time-dependent. The Step 2 prompt (`templates/workflows-js/finalize-feature.js:993-1020`, label
`step-2-merge-main`) is static text built from `WORKTREE_ROOT` alone, so the cache key is the same
before and after the fix. That contradicts the file's own header, which says
*"Resumability: each step probes observable state before dispatching. Re-running /finalize-feature
after a mid-run crash resumes from the first incomplete step"* (`:24-25`). That is true for a fresh
run, but false under `resumeFromRunId`, because the probe itself is the cached `agent()` call.
Step 0's baseline (`:782`) is cached the same way, so a resumed run also keeps comparing against
the original baseline SHA. See `KI-BO-20260927-finalize-triage-baseline-predates-merged-main`.

**Workaround used:** a scratch copy of the script with one changed line in the Step 2 prompt,
which busts the cache key for that step only while keeping the earlier cached steps.

**Fix direction, addendum.** Any `agent()` step whose answer depends on git or filesystem state
should put something that changes between attempts in its prompt. Every probe in the E2 engine
is itself a cached `agent()` call, so the value has to come in from outside, for example an
`args.attempt` counter or the expected HEAD SHA passed in by the caller. A new attempt then means
a new cache key for the state-dependent steps.
Alternatively, the halt message for a git-state halt should say plainly that resume will replay
it, and name the fresh-run escape, as `KI-BO-20260914-a-cached-bad-path-makes-a-workflow-run-permanently-unresumable` proposes.

---
