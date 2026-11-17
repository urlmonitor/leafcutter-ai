---
title: "KI-BO-20261010-hooks-inactive-answer-omits-why-a-stage-did-not-fire — the workspace maker's HOOKS_INACTIVE answer names the stage that did not fire but not why, and the canary's git report is captured and dropped inside the maker"
description: "low — latent on main; live when epic/every-piece-of-separate-work-gets-its-workspace lands. run_canaries reduces each stage to a bool, so a stage whose canary could not look (git failed, no shim, unusable declaration, failed control commit) and a protection that really accepted the bad input give the same answer: inactive_stages plus the stage name. BO-4300c-6 makes the commit-time canary print 'precommit_canary: git <args> exited <rc>: <stderr>', but the maker captures that with the git commit result and discards it. Carrying it into the answer was left out of BO-4300c-6, because the user chose not to reopen the BO-4300c-1 and BO-4300c-2 answer contract."
type: reference
category: reference
status: active
created: '2026-10-10'
last_updated: '2026-10-10'
components:
  - build_orchestration
  - worktree_manager
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
  - docs/known-issues/commit-guardian/open-low-ki-cg-20260901-precommit-probe-reports-false-where-it-means-could-not-look.md
  - docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300c-1-ii.yaml
  - docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300c-2.yaml
---

# KI-BO-20261010-hooks-inactive-answer-omits-why-a-stage-did-not-fire — "not fired" and "could not look" give the same answer

> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** low. The answer fails closed: a stage that could not be proven refuses with
  `HOOKS_INACTIVE`, so no workspace is handed out with an unproven protection. The cost is
  diagnosis. The caller is told which stage, not why, and the one place the reason exists is
  thrown away. Filed at the user's request.
- **Status:** open, no AC. **Latent on main; live when the branch lands.** The maker's canary and
  readiness code exists only on `epic/every-piece-of-separate-work-gets-its-workspace` (local, not
  on `origin`). Neither `templates/scripts/worktree_canaries.py` nor
  `templates/scripts/worktree_readiness.py` exists on `origin/main` `d03830e7c`. The answer
  contract it would extend (BO-4300c-1-ii, BO-4300c-2) is on main.
- **Occurrences:** 0 observed in a real drive. Found while specifying BO-4300c-6 (2026-10-09
  investigation, user decision `dec-0ed3e2e3a1cd8340`, 2026-10-10).
- **First seen:** 2026-10-10 · **Last seen:** 2026-10-10
- **Where:** cited on the epic branch at `d8f4efd08` (read with
  `git show epic/every-piece-of-separate-work-gets-its-workspace:<path>`):
  - `templates/scripts/worktree_canaries.py`: `run_canaries` returns `dict[str, bool]` (:244-266).
    `_hook_rejected` (:150-152) reads only the `PRECOMMIT_CANARY_REJECTED` marker and drops the
    rest of the captured output. Every per-stage driver (`_pre_commit_fires` :161-176,
    `_commit_msg_fires` :179-207, `_post_merge_fires` :210-241) returns a plain `False` on every
    failure path.
  - `templates/scripts/worktree_git.py`: `run_git` runs git with `capture_output=True` (:70-75).
    The canary drivers never forward that output. `install_shims` does (`wa.forward_child_output`,
    `worktree_canaries.py:98`).
  - `templates/scripts/worktree_readiness.py`: `prove_ready` builds the refusal from the bools
    (:235-244). The answer carries `checks` (the `hooks_*_fired` bools), `inactive_stages` and
    `hooks_stages_declared`, and nothing else about the stage.
  - The AC: `docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300c-6.yaml`,
    added to the epic branch by `60d3feba5` (staged first on `epic-side/bo4300-canary-and-main`):
    `delivers_to` (:130-135, "Carrying the git report into the HOOKS_INACTIVE answer is out of
    scope") and `notes` (:522-524).

## Symptom

A readiness check refuses with:

```json
{"status": "refused", "code": "HOOKS_INACTIVE",
 "message": "Declared protections did not fire inside the workspace: pre-commit.",
 "inactive_stages": ["pre-commit"], "checks": {"hooks_pre_commit_fired": false, "...": "..."}}
```

Nothing in the answer says whether the hook ran and accepted the canary file, or whether the canary
could not look. Once BO-4300c-6 is built, the commit-time canary will name the second case on its
stderr: `precommit_canary: git <args> exited <rc>: <git stderr>`. That line goes to the stderr of
the maker's own `git commit`, which `run_git` captures and `_pre_commit_fires` discards. So the
reason does not reach the answer or the maker's stderr.

## Mechanism

`run_canaries` reduces each stage to one bool, and these outcomes all become `False`:

- no canary declared for the stage, or HEAD unreadable (:255-257)
- a stage kind the maker cannot drive (:264-265)
- the known-bad file cannot be written (:163-165)
- no hook shim installed for the stage (:164, :188, :218)
- the hook ran and did not print the marker. This covers both a protection that accepted the input
  and, after BO-4300c-6, a canary whose own git call failed (:168-170, :201-202, :234-235)
- the `--no-verify` control commit failed (:172-173, :204)
- the post-merge setup commit or the merge itself failed (:227-228, :231-233)

`prove_ready` then lists the stage in `inactive_stages`. Only a missing shim and a hook that really
accepts the input mean "this protection is not active". The rest mean "the maker could not show
it". This is the same class as
`KI-CG-20260901-precommit-probe-reports-false-where-it-means-could-not-look`.

## Why it was not fixed in BO-4300c-6

BO-4300c-6 corrects how the canary reads its inputs and makes "git ran and failed" fail closed,
matching "git could not start". Its `delivers_to` states the maker needs no change, because in the
maker's own canary flow every git call exits 0 on a healthy repository. Carrying the report into
the answer would change the BO-4300c-1 / BO-4300c-2 answer contract. The user chose not to reopen
those (BO-4300c-6 notes: "Placed as a sibling of BO-4300c-1 at the user's choice, so BO-4300c-1 and
its done children are not reopened").

## Impact

When a workspace is refused `HOOKS_INACTIVE`, the operator cannot tell a broken install from a
broken repository (corrupt index, a `GIT_DIR` pointing at a non-repository) without re-running the
canary by hand. The BO-4300c-6 notes rate real exposure as low, since pre-commit's own staged-file
listing usually fails first.

## Fix direction

- Have `run_canaries` return a per-stage outcome rather than a bool: fired, or one reason from a
  fixed set (`no_canary_declared`, `no_shim`, `setup_failed`, `hook_accepted`,
  `hook_failed_without_marker`, `control_failed`). Keep the hook's stderr excerpt, trimmed, for
  `hook_failed_without_marker`.
- Add an optional `stage_reasons` field (`{stage: {reason, detail}}`) to the `HOOKS_INACTIVE`
  answer. BO-4300c-2 already allows this: "adding a field is compatible, renaming or removing one
  bumps it" (`BO-4300c-2.yaml:103-104`). It still needs an AC, because the contract is user-owned.
- Until then, forward the captured stderr of a failed canary to the maker's stderr, as
  `install_shims` does. That needs no contract change.

**Pattern:** a check that reports "false" where it means "could not look", with the reason
captured and then dropped.
