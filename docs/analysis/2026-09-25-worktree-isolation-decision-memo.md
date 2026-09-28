---
title: "Isolated workspaces should be per-feature clones with real install files, not worktrees with a symlinked install"
description: "Decision memo answering two open questions from the worktree-consolidation analysis: git worktrees vs per-feature clones (ADR-018) as the isolation mechanism, and real files vs a symlink for .leafcutter inside each workspace. Measured on Windows 11 against the live leafcutter-ai repo. Both recommendations were accepted by the user on 2026-09-25."
type: explanation
status: active
created: 2026-09-25
last_updated: 2026-09-25
components:
  - worktree_manager
  - build_pipeline
  - commit_guardian
---

# Isolated workspaces should be per-feature clones with real install files, not worktrees with a symlinked install

This memo answers open questions 1 and 2 of
[the worktree-consolidation analysis](2026-09-25-worktree-creation-consolidation.md). It was
written by an expert review agent and **accepted by the user on 2026-09-25**. The full decision
record, including the user's own answers to the other questions, is in section 8 of that
analysis.

Two constraints were fixed before this review: every isolated workspace branches from
`origin/main`, and there is exactly one standalone script that creates workspaces, emits one
JSON result, and whose callers halt on anything but `status: "ok"`.

**Where the measurements come from.** Windows 11 on NTFS, Git 2.52, no Developer Mode. They
were taken in a scratch directory against the live `leafcutter-ai` repository:

| Property | Value |
|---|---|
| Tracked files | 8,533 |
| Checkout size | ~84 MB |
| Object store | 54 MB of packs, plus 17 MB / 4,352 loose objects |
| Branches | 339 |
| Registered worktrees | 19 |

## Q1: Worktrees or per-feature clones?

**Recommendation: per-feature clones (ADR-018 §1).** Create each one as a hardlinked
local-path clone of the main checkout, then point `origin` at the hub. Do not use
`--shared` or `--reference`, and do not use `git worktree`.

- **Cost is a wash.**

  | Operation | Time | Extra disk |
  |---|---|---|
  | `git worktree add --detach origin/main` | 6.1 s | ≈ the 84 MB checkout |
  | `git clone <local-path>` with checkout | 10.8 s | ≈ the 84 MB checkout (packs are hardlinked, link count 3 on `objects/pack/*.pack`) |
  | `--reference --dissociate` | 15.4 s | +54 MB, and buys nothing over hardlinks |
  | Incremental `git fetch origin main` from the hub | 0.7 s | — |
  | Bootstrap build (matches CLAUDE.md:401) | 62.3 s | — |

  The build dominates both options, so the 5 s difference on the git step is noise.
- **The shared-`.git` failure class is live on this host.**
  - `.git/lost-found/` holds 81 objects, including 18 commits, and is dated 2026-09-09, so an
    fsck recovery has already happened here.
  - `gc.auto` and `maintenance.auto` are unset. ADR-018 migration step 2 was never applied.
  - `.git/worktrees/` takes 303 MB of the 410 MB `.git`.

  A clone shares no refs, no `packed-refs` lock, no hooks and no automatic gc with the main
  repository.
- **Worktree bookkeeping is broken across platforms today.**
  - Two entries under `/mnt/c/.../.leafcutter/background-worktrees/installation-probe-*` are
    `locked initializing`. They were created from WSL and cannot be used from Windows, because
    the `gitdir:` file embeds an absolute path in one platform's spelling.
  - A clone embeds no absolute path and works from both sides.
- **Hooks land in the right place only under clones.**
  - Worktrees have no per-worktree hooks directory, so `pre-commit install` from any worktree
    rewrites the single shared `.git/hooks/pre-commit`.
  - `install_pre_commit_shims.find_hooks_dir` reads `<root>/.git/config` as a file
    (`templates/scripts/commit_guardian/install_pre_commit_shims.py:74-84`). In a worktree
    that path is a gitfile (F7).
  - In the scratch clone, `build.py` installed pre-commit into the clone's own `.git/hooks`.
- **Push, PR, merge and finalize do not change.**
  - Branches are pushed to the hub and merged by `gh pr merge --merge --auto`
    (`finalize-feature.js:2098`).
  - Clones remove the "branch checked out elsewhere" refusals
    (`setup_ticket_worktree.py:1026`, `:1076`) and the `_worktree_exists` prefix table
    (`:367-410`).
  - Cleanup becomes `rmtree`, keeping the `\\?\` MAX_PATH escape from
    `close-worktree.md:118-143`. There is no `prune` and no `git_recovery.py`
    poisoned-worktree fallback.

**The analysis's failure modes under each option:**

| Failure mode | Clones vs worktrees |
|---|---|
| F1, F2, F4, F6, F9–F13 | Identical. These are contract or caller defects; the script fixes them, not the choice of mechanism. |
| F3 | Slightly better under clones. Inside a clone there is no main-vs-linked ambiguity for `--show-toplevel`. |
| F5 | Clearly better. A half-made clone is a directory without the marker file and can be deleted and redone. A half-made worktree leaves a branch, an admin entry and possibly a corrupt gitfile (KI-BO-20260831-1331). |
| F7 | Better, for the hooks reason above. |
| F8 | Decided by Q2. |
| F14 | Disappears. Temporary clones register nothing in the real repository. |

**Migration cost: moderate, and mostly inside the new script.** `git worktree` appears in 16
template scripts, 7 workflows, 7 skills, 4 agents, 27 `scripts/` files, 56 unit tests and 125
docs. Keep the word "worktree" for the landing directory (`<base>/worktrees/<slug>`) and for
the JSON keys, so those references stay true. Only the create, locate and remove steps change.

**Main risk:** no git command lists clones, and a hardlinked clone inherits the main checkout's
object store without verification.

**Mitigation:**
- A marker file `.leafcutter/workspace.json` in each landing directory records kind, slug,
  branch, hub, base_commit and a manifest hash. The landing directory plus these markers act
  as the registry, exposed through `locate` and `list`.
- Checkout inflates every blob reachable from the tree, so a 0-byte object fails the clone
  loudly.
- The mandatory fetch from the hub validates what it receives.

**What would flip it:** an adopter whose object store is about 1 GB or more **and** whose
landing directory is on a different volume from the main checkout, where hardlinks are
impossible. For that adopter, use `--reference --dissociate`, or fall back to a worktree behind
the same contract. Nothing about Windows, WSL, disk or time favours worktrees for this repository.

## Q2: Real files or a symlink to the main install?

**Recommendation: real files, never `os.symlink`.** `build.py --target-dir <workspace>` runs
inside the workspace on every `ensure`, whether the workspace is new or reused. The answer is
the same under worktrees, and it is mandatory under clones, where a symlink would point into a
different repository.

- **Symlinks do not work here.**
  - `os.symlink` fails with `WinError 1314` on this host, and `core.symlinks=false`.
  - Every live worktree already carries a real `.leafcutter/` (12 MB) and a real
    `.pre-commit-config.yaml`.
  - `install_shims` checks and falls back to copying (`scripts/build_helpers.py:1454`). The
    scratch build copied all nine shims.
  - The "symlink preferred" guidance in CLAUDE.md:531/561 and `_establish_pre_commit_config`
    (`templates/scripts/setup_ticket_worktree.py:1343-1359`) describe a path this platform
    never takes.
- **Real files keep `__file__` resolution inside the workspace.**
  - KI-CG-009, KI-FC-001 and KI-BP-017 all break because `Path(__file__).resolve()` follows
    `.leafcutter` into the main tree. That happens at 62 sites across 41 template scripts.
  - With real files the fallback lands in `<ws>/.leafcutter/...`. That is still one level off:
    the `.claude/` walk-up in `submit_feedback.py:65-77` stops at `<ws>/.leafcutter/.claude`.
    But the result is gitignored and inside the workspace, with nothing leaking into another tree.
  - `check_secrets` reads the allowlist from `find_project_root()`, which is
    `git rev-parse --show-toplevel` (`_resolve_root.py:35-46`). The rule to update both copies
    of the allowlist (CLAUDE.md:575-583) therefore no longer applies.
- **A branch is checked by its own hooks** (ADR-031 §5 parity). The staleness KI-BP-004
  describes, where hooks stay frozen at an old version, is handled by rebuilding on every
  `ensure` and after finalize merges `origin/main`.
- **The cost is already paid.** `_bootstrap` step 5 runs the build in every worktree today
  (`setup_ticket_worktree.py:1541-1553`). The 62 s per `ensure` does not change.
- **KI-BP-016 does not fire in this shape**, because the target is the repository root. The
  scratch build wrote a 0-stub `INDEX.md`.
- **Two side effects of the build:**
  - It **dirtied 61 tracked files**: the link spelling in `docs/INDEX.md`, 59
    `docs/agents/cards/*.card.md` and `LEAFCUTTER_VERSION`. The same 61 files sit uncommitted
    in the live worktree `doc-index-posix-paths`.
  - It ran with **no `skills_config.json` at all**. No live worktree has one in `.claude/`, and
    the build exited 0 on defaults.

**Main risk:** a `git add -A` in the commit phase sweeps changes the build made to tracked
files into a ticket commit, and the build silently uses the default config.

**Mitigation in the script:**
- Pass `--config-path` explicitly. Derive the workspace config from the main install's config,
  stripping the `top_level_packages` prefix. Fail with `NO_CONFIG` if that isn't possible.
- After the build, check that `git status --porcelain` is empty. If it isn't, either restore
  the tracked paths the build touched and report them under `bootstrap.restored_tracked`, or
  fail with `BOOTSTRAP_DIRTIED_TRACKED`.

**What would flip it:** only all three of these together, and only while keeping worktrees:
- hooks and scripts find the root exclusively through `git rev-parse`, with no `__file__` left;
- Developer Mode is on for every Windows host;
- worktrees are kept.

In that case a symlink would save the 62 s without the F8 family of failures. Under clones it
never flips.

## Consequences for the standalone script's contract

1. **`ensure` runs these steps in order:**
   1. Resolve the main checkout.
   2. Read the hub URL from its `origin`. Fail with `NO_HUB` if there is none, which is
      consistent with the fixed `origin/main` base.
   3. Use the landing directory `<base>/worktrees/<slug>`.
   4. If the directory exists, run `verify` (a real `.git` directory, `origin == hub`, the
      branch matches, the marker is present), then repair or refuse.
   5. Otherwise `git clone --no-checkout <main> <ws>`.
   6. `remote set-url origin <hub>`.
   7. `fetch origin main`. Fail with `FETCH_FAILED` unless `--allow-stale-base` is given.
   8. `checkout -B <branch> origin/main`. The reconnect policy consults `origin/<branch>`,
      never the main checkout's local branches.
   9. Set `gc.auto 0` and `maintenance.auto false`.
   10. Copy `.env` and `.mcp.json`.
   11. Run `build.py --target-dir <ws> --config-path <explicit>`, and fail on a non-zero exit.
   12. Check that the working tree is clean.
   13. Prove `pre-commit install` worked with a canary commit that must be rejected
       (ADR-031 §1).
   14. Write the marker file.
   15. Emit the JSON result.
2. **JSON result changes:**
   - Add `mechanism: "clone"`, `hub`, `workspace_path` (keep `worktree_path` as an alias for
     callers), `bootstrap.restored_tracked` and `checks.hooks_canary_rejected`.
   - `checks.is_linked_worktree` becomes `checks.is_independent_repo`.
3. **`locate` and `list`** scan the landing directory and the markers, never `git worktree list`.
4. **`remove`:**
   - Refuses a dirty or unpushed workspace unless `--force` is given.
   - Deletes with `rmtree`, using the `\\?\` prefix on Windows.
   - Optionally deletes the remote branch with `--delete-remote-branch`.
   - Runs no `prune`.
5. **A `scratch` kind** for finalize baselines is a detached clone on the same path, so
   temporary baselines stop touching the main `.git`.
6. **No `os.symlink` anywhere.** The OR-probe from AC-5 (`setup_ticket_worktree.py:1577-1580`)
   is replaced by "a real `.pre-commit-config.yaml` plus the canary commit".
7. **Paths are emitted in both native and POSIX spelling.** Clones can be relocated between
   Windows and WSL, so no `gitdir:` translation is needed.
8. **Cut-over chore:**
   - `git worktree prune`.
   - Retire the 19 registered worktrees and the WSL `background-worktrees` entries.
   - Meanwhile, apply ADR-018 step 2 (`gc.auto=0`) to the main checkout.

## Most relevant files

- `docs/analysis/2026-09-25-worktree-creation-consolidation.md`
- `docs/architecture/adrs/ADR-018-agent-isolation-topology.md`
- `templates/scripts/setup_ticket_worktree.py` (`:1289-1580`, `:1648-1744`)
- `scripts/build_helpers.py:1393-1565`
- `scripts/build_precommit_install.py:84-184`
- `templates/scripts/commit_guardian/_resolve_root.py`
- `templates/scripts/commit_guardian/install_pre_commit_shims.py:60-84`
- `CLAUDE.md:523-583`
- KI-BP-004, KI-BP-016, KI-BP-017, KI-CG-009, KI-FC-001
