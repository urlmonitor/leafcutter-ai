---
title: "KI-BO-20261014-fast-lane-build-targets-the-shared-install — a fast-lane agent step ran build.py with the workspace parent as --target-dir, so one lane's unmerged check_doc_length.py was deployed over the shared install every session's hooks run, for about 20 minutes"
description: "high — fast-lane-ship.js never invokes build.py itself and its coder prompt says nothing about building, so whether a build happens, and into which directory, is an agent's ad hoc choice. During the GE-127g-2-i lane on 2026-10-14 the coder step rebuilt with --target-dir set to the workspace parent (the directory holding the shared .leafcutter/ install) instead of the lane's own worktree. That deployed the branch's intermediate check_doc_length.py over the shared install, live from about 11:22 to 11:42, so every other session's doc-length gate ran unmerged code. Nothing in the lane constrains or checks the target. Code verified on origin/main 95961b718; the incident is session observation."
type: reference
category: reference
status: active
created: '2026-10-14'
last_updated: '2026-10-14'
components:
  - build_orchestration
  - build_pipeline
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
  - docs/known-issues/build-pipeline/open-high-ki-bp-20260826-1331.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260928-fast-lane-worktree-step-runs-another-clones-script.md
---

# KI-BO-20261014-fast-lane-build-targets-the-shared-install — a fast-lane agent step ran `build.py` with the workspace parent as `--target-dir`, so one lane's unmerged `check_doc_length.py` was deployed over the shared install

> Filed 2026-10-14 from the GE-127g lanes. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`).

- **Severity:** high. Silent wrong behaviour that reaches past the lane. For the window it lasted,
  every session's commit gates on the machine ran one branch's unfinished code, and nothing said so.
  A gate that is half-built can refuse correct commits or pass wrong ones in sessions that have
  nothing to do with the lane.
- **Status:** open, no AC.
- **Occurrences:** 1 (GE-127g-2-i fast lane, 2026-10-14, live about 11:22 to 11:42 local time).
- **First seen:** 2026-10-14 · **Last seen:** 2026-10-14
- **Where:**
  - `templates/workflows-js/fast-lane-ship.js` has no `build.py` invocation anywhere
    (`grep -n "build.py\|target-dir"` finds none). The lane's worktree is built once, at bootstrap, by
    `scripts/setup_ticket_worktree.py:1411-1432`, which pins `--target-dir` to the new worktree
    (`:1418`) and passes the main install's recorded log root (`:1419`). Any later rebuild is outside
    that code.
  - The coder dispatch, `fast-lane-ship.js:1597-1623`, names the worktree (`:1600`) and asks for
    implementation plus the green-and-coverage gate. It says nothing about building, about where a
    build may write, or about the shared install.
  - `templates/agents/python-coder.md:555-567` tells the agent that `scripts/` and `.claude/` are
    build outputs of `build.py` and that new hooks go through skills that run `build.py --force`. It
    names no target directory either.

## What happened (session observation)

During the GE-127g-2-i lane, the coder step rebuilt the package so the gate under work would run
from its deployed location. It passed the workspace parent as `--target-dir`, the directory that holds
the shared `.leafcutter/` install, rather than the lane's worktree. The build deployed that branch's
intermediate `check_doc_length.py` (and whatever else differed) over the shared install. Every
session's hooks resolve through that install, so for about twenty minutes the doc-length gate on the
whole machine was the lane's unmerged version.

## Mechanism

1. The lane does not own the build. A build happens only when an agent decides to run one, and the
   agent picks the arguments.
2. No prompt in the lane names the allowed target, and no step compares the deployed tree with the
   worktree afterwards. The lane's own reply schemas carry `files_modified`, not "where did you
   deploy".
3. The shared install is a plausible-looking target from inside a worktree: it is the directory the
   repo's own `CLAUDE.md` describes as the place `build.py --target-dir .` is run from for local
   development. So an agent following the documented self-host recipe from the wrong directory
   lands exactly here.
4. Once deployed, the damage is invisible to the lane. Its gates run from the worktree's own install,
   which was not touched.

This is a new way into the condition `KI-BP-20260826-1331` describes (the shared `.leafcutter/` is a
per-file collage of whatever each writing worktree last wrote). That entry records the result. This
one records a fast-lane agent step as a writer nobody planned for.

## Detection

- During or after a lane, check the mtimes under the shared install's `.leafcutter/scripts/`. Any
  change during the lane's run that no session deliberately made is this defect.
- Compare a deployed gate with main's template, for example
  `cmp <workspace>/.leafcutter/scripts/commit_guardian/check_doc_length.py templates/scripts/commit_guardian/check_doc_length.py`
  run in a clean `origin/main` checkout. A difference is drift.

## Workaround

What was done on 2026-10-14: rebuild the shared install from a clean `origin/main` worktree, with
`--no-shims` and the install's recorded `--log-root`, then confirm that the deployed gate scripts are
byte-identical to main's templates. Rebuild from a clean worktree, not from a lane worktree, or the
rebuild deploys that branch instead.

## Suggested fix

1. **Pin the target in the lane.** Every agent prompt that may build should name the worktree as the
   only allowed `--target-dir` and say that a build outside it is a refusal.
2. **Or keep the build out of agent steps.** If a deployed copy is needed, the workflow runs one
   build itself, into `worktreePath`, through a command step.
3. **Make `build.py` refuse.** A `--target-dir` that is not the checkout `build.py` runs from, nor a
   worktree of it, should need an explicit flag. The shared install would then be reachable only on
   purpose.
4. **Check after the coder.** Before commit, compare the shared install's deployed gate scripts with
   their recorded state and halt if the lane changed them.

**Pattern:** a destructive side effect left to an agent's choice of arguments. The lane constrains
what the agent builds, not where it deploys it.
