---
title: "KI-BO-20260914-a-cached-bad-path-makes-a-workflow-run-permanently-unresumable — resume replays the poisoned agent result in 32ms, so the only escape from a caught hallucination is a fresh run id"
description: "medium — nothing is corrupted and the guard that triggers it is working correctly. The cost is that `resumeFromRunId`, the documented recovery path, is a guaranteed no-op for this class, and its failure is fast and silent enough to look lik"
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

# KI-BO-20260914-a-cached-bad-path-makes-a-workflow-run-permanently-unresumable — resume replays the poisoned agent result in 32ms, so the only escape from a caught hallucination is a fresh run id

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium — nothing is corrupted and the guard that triggers it is working correctly. The cost is that `resumeFromRunId`, the documented recovery path, is a guaranteed no-op for this class, and its failure is fast and silent enough to look like the resume "just didn't help".
- **Status:** open — no AC.
- **Occurrences:** 1 (2026-09-14, `GE-127e-1`), but structural for any guard that validates an agent's own reported value
- **First seen:** 2026-09-14 · **Last seen:** 2026-09-14
- **Where:** `templates/workflows-js/fast-lane-ship.js` worktree phase; the Workflow tool's `resumeFromRunId` result cache

**Symptom.** A `fast-lane-ship` run on `GE-127e-1` halted at the worktree phase:

```text
The worktree location reported for branch fast-lane/ge-127e-1 does not appear in the git
output it was supposedly read from, so it was composed rather than quoted.
Reported: "/home/henzeh/projects/leafcutter/leafcutter-ai"
git worktree list --porcelain returned: ".../worktrees/ge-127e-1"
```

The guard is **right** and is a good guard — it caught an agent stating a path that was not in the command output it claimed to be quoting, which is the failure that sent the resolver to a non-existent directory on `BO-2400f` and `UXP-700d`. The worktree itself was created correctly and verified present in `git worktree list`.

Resuming produced the identical halt in **32 milliseconds with 0 subagent tokens** — the cached agent result, containing the bad path, was replayed verbatim. A second resume would do the same forever.

**Mechanism.** `resumeFromRunId` caches completed `agent()` calls keyed on `(prompt, opts)` and replays their return values. That is the right behaviour for an agent that succeeded expensively. But when the *content* of a cached result is what failed validation, replay reproduces the failure deterministically and cannot clear it. The cache has no notion of "this result was rejected downstream".

So the recovery matrix is inverted from what the tooling suggests: resume is cheapest and always correct for a transient failure, and is *guaranteed useless* for a validated-content failure — which is exactly the case where a halt message tempts you to retry.

**What actually works.** A fresh run (new run id), which re-dispatches the agent and may produce a correct path, or abandoning the workflow and driving the phases directly. The second was chosen here: the worktree existed and was correct, so `test-writer` and `python-coder` were dispatched by hand against it and the AC shipped normally.

**Fix direction.** Either let a halting guard mark the specific cached result as poisoned so a resume re-runs that one agent, or make the halt message say plainly that resume will not help for this class and name the fresh-run escape. The second is cheap and would have saved the wasted resume. Do NOT fix it by disabling the guard — the guard is the valuable part, and a composed path reaching the resolver is the more expensive failure.

**Related.**
- `KI-BO-20260909-worktrees-go-stale-within-minutes` (above) — same component, same session family.
- `docs/reference/false-green-mechanisms.md` — adjacent but distinct: this is a true negative that cannot be cleared, not a false positive.

**Pattern:** a result cache that cannot distinguish "expensive and correct" from "cheap and rejected", so the documented recovery path is deterministically the wrong one.

---
