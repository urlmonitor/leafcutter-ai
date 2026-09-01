---
title: What the fast lane does not isolate, filed before the experiment that would confirm it
date: "2026-09-01"
time: "14:50"
type: manual
components:
  - build_orchestration
summary: "Files KI-BO-20260901-1450 as UNDER INVESTIGATION: the lane isolates its worktree but not the process-level state around it, and three shared surfaces already misfired with a single lane running. Also closes a stale blocker that was distorting the what-to-build-next answer."
description: "Filed deliberately before running two lanes concurrently, so the predictions are on record before the result rather than reconstructed to match it. The entry is explicitly a request for evidence. Separately, KI-BO-20260831-1330 was still reading blocker/open after being fixed incidentally by the bundle shrink — verified closed, because a stale blocker sits at the top of the severity list and displaces real ones."
---

## Entry

The intended next step is to run two fast lanes concurrently and see what breaks. This files the concern **before** that experiment, so the predictions can be scored honestly instead of reconstructed afterwards to match whatever happened.

### The concern

`/fast-lane-build` isolates the thing everyone thinks about: a fresh worktree per run, off `origin/main`, with the run's acceptance criteria claimed before any build work. Two lanes cannot take the same criterion.

What it does not isolate is the process-level state every worktree shares. Three such surfaces misfired on 2026-09-01 **with only one lane running**:

| surface | what happened |
|---|---|
| `.git/config` | A test fixture set `user.name`/`user.email` inside a worktree it created. Worktrees share `$GIT_COMMON_DIR/config`, so **four** commits landed misattributed across three worktrees. |
| `.build_manifest.json` | A build targeted at a worktree wrote a manifest with no usable `output_mappings`; a later commit **in a different tree** was blocked by `check-build-drift` reporting 170 false gaps. |
| shared `.leafcutter` | Worktrees symlink to one install tree, so a build through the link replaces the deployed package for every other tree. |

Each is a single shared resource written by every run, so each should degrade with N rather than improve. That is the hypothesis, and it is stated in the entry so it can be falsified.

### Why the existing coverage does not reach it

`ACD-2000b-4` governs parallel safety at requirement grain, and its unit is the **acceptance criterion's file footprint**. That is a real and separate gap — its host was decided earlier today as the claim path. None of the three surfaces above is an AC footprint. They are process-level singletons no criterion in the store mentions, so building `ACD-2000b-4` in full would leave all three untouched.

### The entry asks for things rather than only recording them

It is filed incomplete on purpose, with **no severity assigned**, and asks for: a parallel-lane failure that surfaced in a *different* worktree from the one that caused it; a fourth shared surface (the pre-commit cache, allowlist resolution through the symlink, the feedback sink, and concurrent claim-record writers are all unchecked); evidence that a listed surface is actually *safe*; and a severity judgement from anyone who has measured this.

It also states plainly what is **not** claimed: that parallel lanes are unsafe. They may be fine. The claim is only that the isolation story stops at the worktree boundary and three surfaces past it have already misfired at N=1.

### A stale blocker, closed

Reviewing the fast-lane register to decide what to build next turned up `KI-BO-20260831-1330` — *"the fast lane invokes `assemble-bundle` with two flags that were deliberately deleted"* — still reading `blocker / open`. It is fixed: `grep -c "conventions\|--acs"` against the live lane returns **0**, and a run has since reached its coder phase with a 20,645-byte bundle. It was closed incidentally by the `BO-2400c-1-vi` bundle shrink, which removed the layers those flags passed, so nobody closed the entry deliberately.

That is recorded as more than bookkeeping. It sat at the **top of the severity list** when the register was consulted today to decide priorities, and it displaced two real entries. A stale blocker is not harmless; re-verify one before planning against it.

The register index was also 15 low across six rows again, having drifted within a day of the last recount. Recounted: 209.
