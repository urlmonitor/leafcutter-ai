---
title: "KI-BO-20260909-worktrees-go-stale-within-minutes — a branch cut from `origin/main` is behind before the work finishes, and nothing rebases it; only a manual audit stands between that and a push that deletes other people's merged work"
description: "high — the failure mode is silent deletion of merged work on `main`, and it is caught today only by a manual command a human or agent has to remember to run. Four occurrences in a single session, one of which would have deleted work merged "
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

# KI-BO-20260909-worktrees-go-stale-within-minutes — a branch cut from `origin/main` is behind before the work finishes, and nothing rebases it; only a manual audit stands between that and a push that deletes other people's merged work

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high — the failure mode is silent deletion of merged work on `main`, and it is caught today only by a manual command a human or agent has to remember to run. Four occurrences in a single session, one of which would have deleted work merged **earlier in that same session**.
- **Status:** open — no AC.
- **Occurrences:** 4, all on 2026-09-09
- **First seen:** 2026-09-09 · **Last seen:** 2026-09-09
- **Where:** every worktree-creating path — `scripts/setup_ticket_worktree.py`, the fast-lane's own worktree step, and plain `git worktree add ... origin/main`

**Symptom, four times in one session.** Each branch was cut from a then-current `origin/main`, work proceeded for anywhere from minutes to an hour, and `git diff origin/main --numstat` immediately before push showed large deletion counts on files the branch had never touched:

| branch | what the pre-rebase diff would have deleted |
|---|---|
| `fix/ge-127a-1-ordinary-commit-gap` | `TKT-016`'s AC, test and script — 233 lines |
| `ac-authoring/ge-127e-actionable-refusal` | the whole `ACS-1400` and `BP-1500` trees, the `ACD-400` family, `ADR-041` |
| `fast-lane/ge-120g-1` | the whole `ACD-2200` and `ACD-2300` trees + 264 lines of known-issues |
| `ac-authoring/guardrail-injection` | `GE-127e-3-ii`, the `GE-120g` tests and `run_hook.py` changes — **merged earlier in the same session** |

Every one was caught by the additive-only audit and fixed with `git rebase origin/main`. None reached a push.

**Mechanism.** Nothing here is a bug in git. `main` receives merges continuously — this repo has many concurrent sessions — so the window between "cut a worktree" and "push it" is essentially always long enough for `main` to move. A branch that has not rebased carries a tree that lacks whatever landed in that window, and a push followed by a merge presents those absences as deletions.

Two things make it sharper than ordinary staleness:

- **`setup_ticket_worktree.py create-only` roots at LOCAL `main`, not `origin/main`** (its own `_create_worktree()` docstring records this; `create-ac-worktree` and `create-fastlane-worktree` both root at `origin/main`). `/quick-fix` Phase 0.4.2 exists solely to guard that, and it correctly halted on a local `main` 11 commits behind. But in the same session the script then produced a worktree rooted at a commit that was *not* the local `main` the guard had just verified — so passing the guard is not sufficient.
- **`git fetch origin main` updates `FETCH_HEAD`, not `refs/remotes/origin/main`.** So an audit run right after that fetch compares against a ref that may be hours old and reports clean. This is already recorded in `CLAUDE.md` from a 2026-09-07 incident; it recurred twice more today.

**Why the existing defence is not enough.** The additive-only audit works — it caught all four. But it is a *manual step in a runbook*, and its failure mode is omission, not error. It sits at the end of a long pipeline, after the interesting work is done, at exactly the point where attention is lowest. A defence with a 100% hit rate and a 0% enforcement rate is one forgotten command away from the outcome it prevents.

**Fix direction.** Make the rebase automatic rather than the audit diligent — `fetch --prune` followed by a rebase onto `origin/main` immediately before any push, in the paths that push (`quick-fix` Phase 7.1, the fast lane's close step, `finalize-feature`). Keep the audit as the backstop; it is cheap and it is the thing that would catch a bad rebase. Two lower-effort partial fixes worth doing regardless: have `create-only` root at `origin/main` like its two siblings, and replace every `git fetch origin main` in the runbooks with `git fetch origin --prune`, since the former does not update the ref the audit reads.

**Related.**
- `CLAUDE.md` → "Post-origin/main-merge diff audit" — the manual defence this entry proposes to automate; its own text already records the stale-ref variant from 2026-09-07.
- `KI-ACS-20260909-standalone-validator-does-not-derive-declares-side-effect` (`ac-store.md`) — same session, same family: a documented check narrower than it reads.

**Pattern:** a correct defence with no enforcement, positioned at the end of the pipeline where attention is lowest — so its hit rate measures diligence rather than coverage.

---
