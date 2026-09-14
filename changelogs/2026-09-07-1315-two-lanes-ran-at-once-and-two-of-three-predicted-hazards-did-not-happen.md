---
title: Two lanes ran at once, and two of three predicted hazards did not happen
date: "2026-09-07"
time: "13:15"
type: manual
components:
  - build_orchestration
summary: "Runs the experiment KI-BO-20260901-1450 was filed ahead of. Two fast lanes launched simultaneously on disjoint acceptance criteria: the git-identity leak is confirmed, and the build-manifest and shared-install-tree hazards are falsified because a lane worktree bootstraps its own copy of each."
description: "The entry predicted three shared process-level surfaces would degrade with parallel lanes. Measured: one does, two do not. A lane worktree holds its own real .leafcutter directory and its own .build_manifest.json, so the only surface it cannot isolate is $GIT_COMMON_DIR/config, which worktrees share by construction. Severity narrowed from unknown to medium, and the entry's scope from three surfaces to one."
---

## Entry

`KI-BO-20260901-1450` was filed deliberately *before* the experiment that would test it, so its predictions could be scored rather than reconstructed afterwards to fit whatever happened. The experiment has now run.

Two fast lanes were launched simultaneously against `BO-2900a-1-i` and `BO-2900d-2`. Their connected sets were confirmed three-way disjoint by AC id and by file beforehand — deliberately, so that any interference **could not** be footprint collision and the shared-state question would be isolated.

### Result

| # | prediction | outcome |
|---|---|---|
| 1 | `.git/config` identity leaks across lanes | **confirmed** |
| 2 | `.build_manifest.json` causes cross-lane `check-build-drift` failures | **falsified** |
| 3 | shared `.leafcutter` — one lane's build clobbers the other's deployed package | **falsified** |

### The falsifications are the useful half

Measured after the run: each lane worktree holds its **own real `.leafcutter` directory**, not a symlink — `ls -ld` returns `drwxr-xr-x` on both. Each holds its **own `.build_manifest.json`**, both 127,211 bytes written at 12:31, while the workspace-root manifest was untouched and still dated 2026-09-01.

The lane's bootstrap builds a genuinely private install tree per run.

The original observations behind surfaces 2 and 3 were real, but they came from **hand-made** worktrees where the `.leafcutter` symlink was created manually, following the documented `CLAUDE.md` setup. Generalising from a hand-made worktree to a lane-made one was the error — and the direction is worth noting: **a lane worktree is better isolated than the ones humans and agents create by following the documented procedure.**

Both lanes bootstrapped within the same minute with no collision of any kind.

### What remains

`$GIT_COMMON_DIR/config` is shared because worktrees share it by construction; the lane cannot bootstrap its way out. The identity was verified clean immediately before launch, and the successful lane's commit landed authored `GE-120e-1-i fixture` — on a pull request.

Root cause and remedy are already recorded in `KI-TQ-012`: a fixture writes an identity with plain `git config` rather than `git config --worktree`, and this repository already sets `extensions.worktreeConfig = true`, so the correctly-scoped form is available today.

So the practical consequence for parallel lanes is much narrower than the entry originally implied. **Parallel lanes do not corrupt each other's build state.** They share a commit identity, and until `KI-TQ-012` is fixed every lane commit risks misattribution — a real defect on a real pull request, but a smaller and more tractable thing than "the isolation story stops at the worktree boundary".

Severity narrowed from unknown to **medium**; scope from three surfaces to one. The still-unchecked surfaces are named in the entry, and a negative result on any of them remains as valuable as a positive one — two of the three original predictions were negative, and that is precisely what made the entry worth filing.
