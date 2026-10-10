---
title: "KI-BO-20261009-epic-worktree-resolution-is-split-brained — whether /build-feature reuses the session's epic worktree depends on an LLM resolver's cwd and wording; when it falls through it opens a second worktree from origin/main, and the driver verifies there while the phase agents work in the first"
description: "high — scenario 1 (reuse) depends on what a status-checker agent reports after running 'test -f .git' from wherever it happens to run. From the self-hosting workspace parent, which holds a .git directory that is not a repository, that test prints 'directory' and the resolver is told to report the epic folder, which can never pass the reuse check. Scenario 2 then opened a new worktree at worktrees/EPIC-<name> from origin/main with stale tickets. Phase agents get the worktree only as prose and kept working and committing in the session's worktree, while the driver read sign-offs from the new one and failed every phase."
type: reference
category: reference
status: active
created: '2026-10-09'
last_updated: '2026-10-09'
components:
  - build_orchestration
  - worktree_manager
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/build-orchestration/resolved/resolved-blocker-ki-bo-20260921-build-feature-abandons-the-epic-worktree-branch.md
  - docs/known-issues/build-orchestration/resolved/resolved-high-ki-bo-20260921-worktree-base-resolver-defaults-to-cwd.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260927-status-checker-runs-workflow-shell-commands.md
  - docs/known-issues/commit-guardian/open-high-ki-cg-20260927-file-size-hook-read-another-worktrees-index.md
---

# KI-BO-20261009-epic-worktree-resolution-is-split-brained — reuse depends on an agent's cwd, and a fall-through splits the drive across two worktrees

- **Severity:** high. When it happens, every phase of every ticket fails verification and the
  run's report blames the phases. The real cause is that the driver and the agents are looking at
  different checkouts. Because each `/build-feature` re-run repeats the resolve (see
  `KI-BO-20261009-one-halted-ticket-stops-the-whole-epic-run`), every re-run is another chance to
  hit it.
- **Status:** open, no AC. The fall-through is a session observation. The two cwd dependencies
  below were verified by running `worktree_repo_facts.py` from the workspace parent on 2026-10-09.
- **Occurrences:** 1 run that split (during the BO-4300 drive, 2026-09-28 to 2026-10-09; run id not
  retained here). The cwd dependence is structural.
- **First seen:** during the BO-4300 drive · **Filed:** 2026-10-09
- **Where:** `templates/workflows-js/build-feature.js` on `origin/main` `c373b005e`: the resolve
  prompt (:1565-1585, the `test -f .git` rule at :1575-1577); scenario 1 (:1638-1642); scenario 2
  (:1643-1667, reuse rule :1652, new worktree from `origin/main` :1656-1666); phase dispatch, which
  passes the worktree only as prose (:2213-2232). Also `templates/scripts/worktree_repo_facts.py`
  (`facts --reference` and `base start`, both defaulting to `"."`, :289-293).

## Symptom

One run did not reuse the session's existing epic worktree. It fell through to scenario 2 and
opened a NEW worktree at `worktrees/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace` from
`origin/main`, whose copy of the epic held stale tickets. The phase agents meanwhile did their work,
and committed it, in the session's existing worktree. The driver read every sign-off back from the
new worktree (`readTicketRecordBack(worktreeTicketPath)`), found none, and failed every phase.

## Mechanism

1. **Scenario 1 trusts an agent's answer about its own cwd.** The resolver is a status-checker
   told to run `test -f .git && echo file || echo directory`. If it gets `file`, it reports its cwd
   as the worktree. If it gets `directory`, it reports "the epic folder path" (:1575-1577). Scenario 1
   accepts the answer only if `facts` says it is a linked worktree of the same repository (:1641).
2. **From the workspace parent, the test gives the wrong answer.** In the self-hosting layout the
   parent `C:/Users/Hendrik/Code/leafcutter` contains a `.git` directory holding only `hooks/` and
   `info/`. It is not a repository (`git rev-parse` fails there). So the test prints `directory`, and
   the resolver reports an epic folder. `facts` on an epic folder returns `is_git_toplevel: false,
   is_linked_worktree: false` (verified), and scenario 1 is skipped.
3. **`same_repository` is cwd-dependent too.** `facts <worktree> --reference "."` from the workspace
   parent returns `same_repository: null` for a healthy worktree (verified). `repoAnchor` is `"."`
   whenever the resolver's `epic_path` is not absolute (:1624), so scenario 1 also fails on a relative
   target. `base` with no start, or with `"."`, returns all nulls from the same directory (verified).
   This is the residual that the closure note of
   `KI-BO-20260921-worktree-base-resolver-defaults-to-cwd` said was not known to occur.
4. **Scenario 2 recognises a worktree only by its branch name.** It reuses an existing worktree at
   `worktrees/<identity>` only if the branch is `epic/<kebab>` or the identity itself (:1652). Context:
   this epic's branch was created as `scaffold/EPIC-BO-4300` and renamed to
   `epic/every-piece-of-separate-work-gets-its-workspace` on 2026-09-28 13:25 (branch reflog). If no
   worktree is at that location, a new one is opened from `origin/main`, or from the branch if that
   is not behind (:1656-1661).
5. **The agents are not bound to the driver's choice.** The phase prompt carries
   `worktree_path: <path>` as text (:2232). Nothing sets the agent's cwd. An agent started in the
   session's worktree can work there. Inferred, but it matches what was observed.

## Impact

The drive split across two checkouts. Committed work was in one, and verification ran against the
other. Every phase was reported failed, the run halted, and the stray worktree had to be found and
removed by hand. A reader trusting the run output would conclude that every phase agent had failed.

## Detection

At the start of a run, compare the journal's `worktree-facts-resolved` and `worktree-setup` steps.
A `worktree-setup` step on an epic that already has a worktree is this defect. Afterwards,
`git worktree list` will show two worktrees for the same epic, one of them created by the run.

## Fix direction

- Resolve the worktree with a script, not an agent: one deterministic call that takes the target
  and the caller's real cwd and answers reuse, open or refuse. Drop the `test -f .git` heuristic,
  which a non-repository `.git` directory defeats.
- Make `--reference` and `start` required in `worktree_repo_facts.py`, or default them to the
  repository of the path being asked about, never to the process cwd.
- When an existing worktree of this repository already holds the target epic folder, refuse to open
  a second one for the same epic. Name both paths in the refusal.
- Give each phase agent a pinned cwd if the engine allows it. Otherwise have the driver check, after
  each phase, that the record it read back is in the same worktree as the agent's last commit.

**Related.** The resolved `KI-BO-20260921-build-feature-abandons-the-epic-worktree-branch` is the
earlier form of this split. Its closure was not verified end-to-end. This run is a live
reproduction by a different route. `KI-BO-20260927-status-checker-runs-workflow-shell-commands`
covers the status-checker relaying shell commands. `KI-CG-20260927-file-size-hook-read-another-worktrees-index`
is the same class one layer down: a git query answered from a checkout other than the one meant.
