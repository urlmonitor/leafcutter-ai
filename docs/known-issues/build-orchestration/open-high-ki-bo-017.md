---
title: "KI-BO-017 — A fast-lane re-run whose worktree was pruned silently rebuilds on the old branch tip instead of the latest `origin/main`"
description: "KI-BO-017 — A fast-lane re-run whose worktree was pruned silently rebuilds on the old branch tip instead of the latest `origin/main`"
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

# KI-BO-017 — A fast-lane re-run whose worktree was pruned silently rebuilds on the old branch tip instead of the latest `origin/main`

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open — found while specifying `BO-2400f-13`, deliberately not fixed there
- **Occurrences:** 0 observed directly; reachable today on every AC the lane has already built
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/scripts/setup_ticket_worktree.py:529` — the checkout-only branch of
  `_create_fastlane_worktree`, reached from `cmd_create_fastlane_worktree` at `:1289`

**Symptom.** When the branch `fast-lane/<slug>` exists but its worktree has been pruned or
removed, `_create_fastlane_worktree` takes its checkout-only path — `git worktree add <path>
<branch>` with no start point. That reconnects the workspace at **the old branch tip**, which
is wherever the prior run left it. Nothing re-cuts it from `origin/main` and nothing says it
did not.

**Why this contradicts a `done` criterion.** `BO-2400f-3` (`work_status: done`) promises a
branch "cut from the latest `origin/main` (never from stale local main)". That promise holds
on a first run and silently fails on a reconnect. The lane then builds, tests and reports
green against a mainline that may be days old — a green result measured against a tree that
no longer exists. This is the same hazard that led the Product Owner to reject
reuse-in-place for `KI-BO-015`, arriving through a different door: the reject decision
covered the case where the *worktree* survives, and this is the case where only the *branch*
does.

**Why it is the common case, not an edge.** Every finished run leaves exactly this state
behind once its worktree is cleaned up. `worktrees/` is periodically reclaimed (the
`wsl-reclaim` timer removes merged-and-clean worktrees with no age wait), so the branch
routinely outlives its workspace. So the population at risk is "every AC the lane has ever
successfully built", and it grows monotonically.

**Why it is invisible.** The reconnect succeeds, exits 0, and returns a well-formed payload
with a real `worktree_path`. There is no warning, and the payload carries no indication of
which commit the workspace was cut from. From the lane's point of view — and the operator's
— a stale reconnect and a fresh cut are indistinguishable.

**Evidence.** Read at HEAD, not inferred from a failure. `_create_fastlane_worktree`
branches on `_branch_exists(full_branch, repo_root)`; the true branch runs `git -C <repo>
worktree add <path> <branch>` (no start point, `:529`), while only the false branch cuts from
`origin/main`. `git worktree list` on 2026-08-25 shows three live fast-lane worktrees
(`bo-1500a-5`, `bo-2400e-3`, `bo-2900g-3`); each becomes an instance of this issue the moment
its directory is reclaimed while the branch remains.

**What `BO-2400f-13` does and does not do about it.** `BO-2400f-13-iv` requires that this
residual state — branch present, location free — is **not** refused, because refusing it
would make the lane unusable on every AC it has already built. To keep the divergence from
staying silent, the IT PO specified that the first-phase report carry `base_commit`, read
**from the workspace** (`git -C <worktree> rev-parse HEAD`) rather than from the commit-ish
handed to git, alongside an explicit `base_matches_origin_main`. That makes the staleness
*visible* in phase one. It does not make it *correct*.

**Fix direction — genuinely undecided, and a product call.** Two candidates, and the choice
is not obvious:

- *Re-cut.* Reset the reconnected branch to `origin/main` before building. Correct with
  respect to `BO-2400f-3`, and destructive: it discards any commits the prior attempt made
  that were never merged. Must not be done silently.
- *Reuse and report.* Build on the old tip but state the base commit and its distance from
  `origin/main` in the outcome. Honest and non-destructive, but still ships a green result
  measured against a stale tree, which is what `BO-2400f-3` exists to prevent.

A third shape worth considering is to refuse this case too, consistently with `BO-2400f-13` —
at the cost of making a very common state require manual intervention.

**Do not fix this inside `BO-2400f-13`.** It predates that criterion, it is reachable
independently of any occupancy check, and the implementer of `BO-2400f-13` is explicitly
forbidden from resolving it by reset or rebase. It needs its own criterion once the product
decision is made.

---
