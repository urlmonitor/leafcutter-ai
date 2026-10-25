---
title: "KI-BO-20261025-halted-epic-resume-refused-on-new-template-sources — a halted epic cannot be resumed once a ticket has created a new templates/ source, because the maker rebuilds the install, build.py's tracked-source guard refuses the untracked file, and the maker's set-aside step undoes git add -N first"
description: "high — on a /build-feature re-run, worktree.py ensure rebuilds the workspace install. A ticket that halted after creating new templates/scripts/commit_guardian/*.py files (GE-124a-1) leaves them untracked, so build.py's TRACKED-SOURCE GUARD aborts and the maker answers BOOTSTRAP_FAILED. Marking the files intent-to-add does not help: the maker's work_set_aside resets every changed path to HEAD before the build, which turns an intent-to-add entry back into an untracked file. Runs wf_0dba6513-c79 and wf_ed65f446-ee1 were both refused."
type: reference
category: reference
status: active
created: '2026-10-25'
last_updated: '2026-10-25'
components:
  - build_orchestration
  - worktree_manager
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
  - docs/known-issues/build-orchestration/open-low-ki-bo-20261009-one-halted-ticket-stops-the-whole-epic-run.md
  - docs/known-issues/build-pipeline/open-blocker-ki-bp-018.md
  - docs/how-to/get-a-workspace.md
---

# KI-BO-20261025-halted-epic-resume-refused-on-new-template-sources — new source files make a halted epic unresumable

> Filename severity is the three-level index bucket (`high`); the original grading is the
> `**Severity:**` line below.

- **Severity:** high. The drive cannot be resumed through its own entry point. The only way on is a
  hand-run build with the maker's exact arguments and a manual commit of the halted tickets'
  work. That is outside the drive's gates and easy to get subtly wrong (see
  KI-BO-20261025-bare-build-drifts-from-the-maker-build).
- **Status:** open, no AC.
- **Occurrences:** 2 refused runs in one drive: `wf_0dba6513-c79` and `wf_ed65f446-ee1`, GE-124
  epic (`epic/every-screen-says-which-requirement-it-is`), 2026-10-25.
- **First seen:** 2026-10-25 · **Last seen:** 2026-10-25
- **Where:** cited on `origin/main` `0087a1700`:
  - `templates/scripts/worktree.py:126`: an existing workspace runs the readiness build inside
    `wes.work_set_aside(workspace_path)`. Only a freshly created one skips it.
  - `templates/scripts/worktree_ensure_state.py:349-376` (`work_set_aside`): every changed tracked
    path is `git reset -q HEAD --` (:369-370), and paths in HEAD are checked out (:371-372). An
    intent-to-add entry is a changed path that is not in HEAD, so the reset removes it from the
    index and leaves the file untracked for the duration of the build.
  - `templates/scripts/worktree_readiness.py:281-287` (`prove_ready`): runs the install build and
    returns the build's failure code when it fails.
  - `scripts/build.py:1084-1129` (`_check_tracked_source_guard`): any deployable source that git
    does not track prints `[TRACKED-SOURCE GUARD] UNTRACKED SOURCE: <path>` and aborts the build.

## Symptom

1. A ticket in the epic creates new source files under `templates/`. In GE-124 it was ticket
   GE-124a-1, which added new `templates/scripts/commit_guardian/*.py` modules.
2. The drive halts before that ticket is committed. The new files are untracked in the epic
   workspace.
3. `/build-feature` is re-run. It asks `worktree.py ensure` for the epic workspace, and the maker
   rebuilds the workspace install.
4. `build.py` aborts on the tracked-source guard, and the maker answers `BOOTSTRAP_FAILED`. The
   drive never reaches the planner.
5. `git add -N <new files>` and a re-run give the same refusal, because `work_set_aside` clears the
   intent-to-add entries before the build runs and restores them afterwards.

## Mechanism

Three behaviours, each reasonable alone:

- The guard exists so an install is never built from a file that history does not hold.
- The maker sets the work's uncommitted changes aside so the readiness build and canaries run on a
  clean tree. Its docstring says "Untracked files are never touched". That is true, but
  intent-to-add files are tracked going in and untracked during the build.
- The drive does not commit a ticket's files before it halts, so a halt routinely leaves new
  sources uncommitted.

Together they mean any epic whose halted ticket created a new deployable source cannot get its
workspace back from the maker.

## Workaround used

1. `git add -N` the new source files in the epic workspace.
2. Run `build.py` by hand with the maker's exact arguments:
   `LEAFCUTTER_SHIM_STRATEGY=copy python3 <ws>/scripts/build.py --target-dir <ws>
   --config-path <ws>/.leafcutter/derived_skills_config.json --log-root <recorded root>`, where
   `<recorded root>` is the `operational_log_root` the install already declares.
3. Commit the halted tickets' work so the next `ensure` sees tracked sources.

## Fix direction

Any one of these, in order of preference:

1. **The drive commits each ticket before it halts** (or right after its phases finish), so a halt
   never leaves new sources outside history. That also helps
   KI-BO-20261009-parallel-tickets-interfere-through-one-worktree.
2. **`work_set_aside` preserves intent-to-add entries**: skip the `reset` for paths not in HEAD
   whose index entry is intent-to-add, or re-add them with `-N` before the build.
3. **The tracked-source guard accepts intent-to-add files** as tracked. `git ls-files` already
   lists them.

Add a regression case: an existing workspace with a new `templates/scripts/...` file marked
intent-to-add, `ensure` again, assert the answer is `OK`.

**Related.** KI-BO-20261009-one-halted-ticket-stops-the-whole-epic-run (halts are frequent, so
resumes are frequent). KI-BP-018 (why the build guards exist).

**Pattern:** a clean-tree step that is correct for edits silently undoes the one git state that
was meant to bridge a guard.
