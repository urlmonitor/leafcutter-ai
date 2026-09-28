---
title: "ADR-018 Amendment 1 (2026-09-27) — One workspace maker, hardlinked clones, real install files"
description: "The full decision record for ADR-018's 2026-09-27 amendment: why the original per-clone creation-strategy preference order changed, the normative A1.1-A1.7 decision points for the single workspace-maker script, its consequences, and the alternatives considered. Split out of ADR-018 to keep that file under the ADR length ratchet."
type: adr
status: active
created: 2026-09-27
last_updated: 2026-09-27
deciders:
  - leafcutter-engineering-team
components:
  - worktree_manager
  - build_pipeline
  - commit_guardian
related_docs:
  - docs/architecture/adrs/ADR-018-agent-isolation-topology.md
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
  - docs/analysis/2026-09-25-worktree-isolation-decision-memo.md
  - docs/analysis/2026-09-25-worktree-creation-consolidation.md
  - docs/analysis/2026-09-25-worktree-delivered-maker.md
  - docs/architecture/components/worktree-manager.md
---

# ADR-018 Amendment 1 (2026-09-27) — One workspace maker, hardlinked clones, real install files

**Parent document:** [ADR-018 — Agent Isolation Topology](ADR-018-agent-isolation-topology.md#amendment-1--2026-09-27--one-workspace-maker-hardlinked-clones-real-install-files).
This page is the full body of that ADR's "Amendment 1" section, split out to keep
`ADR-018-agent-isolation-topology.md` under the ADR line-length ratchet. The parent file
keeps the Amendment 1 heading, its Status/Amends/Author table, and a link back here; treat
that table as still governing (Amends, Status, Driven by, Supersedes-this-ADR?).

## Why this had to change

The [worktree-consolidation analysis](../../analysis/2026-09-25-worktree-creation-consolidation.md)
found that workspaces were created by several routes (long-running build, quick fix,
requirements-authoring session, agents following a skill, a person at a terminal), each
with its own logic and its own defects (F1–F14). None of those routes had moved to
clones: `gc.auto` was still unset, and `.git/lost-found/` showed an fsck recovery had
already happened on the dev host. The user settled four questions on 2026-09-25:
clones, not worktrees (1); real install files, not a symlink (2); `origin/main` after a
fetch as the base for every kind (3); and one standalone script that creates every
workspace the same way (7). The
[decision memo](../../analysis/2026-09-25-worktree-isolation-decision-memo.md) measured
the clone options on Windows 11/NTFS. There, a hardlinked local-path clone costs about
11 s and shares the pack files through hardlinks. `--reference --dissociate` costs 15.4 s
and 54 MB more and gains nothing, and `cp --reflink` is not available on NTFS. That
makes the original §1 preference order wrong for the reference host.

## Decision

**A1.1 — Creation mechanism.** Every workspace MUST be a hardlinked local-path clone of
the main checkout (`git clone --no-checkout <main> <ws>`). Its `origin` MUST then be
re-pointed at the hub, and `origin main` MUST be fetched. The line of work MUST be checked
out from `origin/main`, or resumed from `origin/<branch>` (BO-4300d-4). This holds for
every kind. The maker MUST NOT use `git worktree`, `git clone --shared` or
`git clone --reference`. A fetch failure MUST end in `FETCH_FAILED` unless the caller
passed `--allow-stale-base`. A main checkout with no `origin` MUST end in `NO_HUB`. The
memo's flip case (an object store of about 1 GB or more on a different volume from the
landing place, where hardlinks are impossible) is out of scope. Supporting it requires a
further amendment.

**A1.2 — One maker.** One stdlib-only script MUST create, clone, locate, list, verify and
remove workspaces. Its tracked source is `templates/scripts/worktree.py`, and it is deployed
to `<install-root>/scripts/worktree.py`. The file name stays provisional until BO-4300a-1
is built; after that, the deployed path is the contract every caller names. The script
MUST expose the verbs `ensure`, `locate`, `list`, `verify`, `remove` and `where`. `ensure`
MUST be the only verb that creates a workspace, and it MUST be idempotent. After BO-4300f-2,
no code path in the package other than the maker MUST create, clone, locate or remove a
workspace, and `setup_ticket_worktree.py` is retired. Every route MUST receive an answer of
the same form, following the BO-4300c-2 result contract, and callers MUST halt on any status
other than `ok`. Agents MUST run the maker as a single command from the workspace skill.
Workflows MUST receive its answer as input, and MUST NOT hand workspace creation to an agent
as free-form shell work. The maker MUST NOT read stdin or prompt. It MUST report any
condition it cannot classify as `INTERNAL_ERROR`, and it MUST NOT print a traceback on
stdout.

**A1.3 — Real install files and proven protections.** On every `ensure`, the maker MUST
run the install build inside the workspace with an explicit config path. That path is
derived from the main checkout's own install config by stripping the `top_level_packages`
prefix. When the derivation is impossible, the maker MUST fail with `NO_CONFIG`. It MUST
NOT fall back to the build's default config or to its own location. Neither the maker nor
the install path it drives MUST use `os.symlink`, `ln -s`, `mklink` or a junction. After the
build, the maker MUST check that the tree is clean. It MUST install the shim for every hook
stage that the workspace's own hook declaration names, and it MUST prove each stage with a
canary commit that is rejected (ADR-031 §1). Canary commits MUST run with the working
directory set to the workspace and MUST NOT be spelled `git -C <path> commit`, because the
commit-delegation hook matches only the literal `git commit`.

**A1.4 — Marker record as the clone registry.** No git command lists clones, so the maker
MUST write a marker record into each workspace. The record is the registry. It MUST hold
`schema_version`, `kind`, `slug`, `branch`, `hub`, `project_root`, `base_commit`,
`maker_version`, `state` (`creating` | `ready`) and `created_at`. The maker MUST write it
atomically (temp file plus replace): with `state: creating` as soon as the clone exists,
and with `state: ready` as the last step. The record MUST live outside version control and
outside anything the install build rewrites or cleans. `locate` and `list` MUST scan the
landing place's markers. They MUST NOT call `git worktree list`. `project_root` is the only
way a workspace identifies its project (BO-4300b-1).

**A1.5 — A separate project-root resolver.** Project-root resolution MUST live in its own
stdlib-only module, importable as a top-level module with no import-time side effects. It
is deployed beside the maker in `<install-root>/scripts/` through its own deploy-manifest
entry. Every call MUST recompute its answer, with nothing cached. The maker MUST import this
module. It MUST NOT re-implement resolution inline. The module MUST NOT reuse, import, wrap
or copy `templates/scripts/commit_guardian/_resolve_root.py`, which walks up from `__file__`
and caches its answer in a module global. This amendment does not fix the resolution order
or its exclusions: BO-4300b-1 owns them.

**A1.6 — One tracked source, named deploy entries.** The only tracked source of the maker and
of the resolver module MUST be `templates/scripts/`. No tracked copy MUST exist under
`scripts/` or anywhere else in the package repository. Each module MUST have its own named
entry in `build_template_standalone_scripts` (`scripts/build_phases_script_deploy.py`) and in
the matching helper in `scripts/build_deploy_manifest_helpers.py`. The shallow glob alone
is not enough, because that deploy phase is non-recursive. Tests MUST exercise the deployed
copy and MUST NOT fall back to the `templates/` source.

**A1.7 — §2 applied per workspace.** `ensure` MUST set `gc.auto 0` and
`maintenance.auto false` in every workspace it makes.

**Not decided here.** These questions stay open for the component's AC authoring: 4 (the
one naming scheme, kept as a single table inside the maker), 5 (where adopter workspaces
live), 6 (whether `leafcutter-ai/.leafcutter/` should exist) and 8 (the discard
authorisation for `remove`).

## Consequences

**Positive:**

- Five creation routes collapse into one. A workspace from any route has the same
  properties: independent clone, fresh `origin/main` base, own install, proven hooks,
  marker, and one landing place.
- Hooks install into the clone's own `.git/hooks`. They no longer overwrite the single
  shared hook file of a worktree family (F7).
- A half-made workspace is identifiable, because its marker is missing or says
  `creating`, and it can be deleted and redone (F5). Temporary clones register nothing in
  the real repository (F14).
- Removing the second tracked copy of the creation script closes the drift class
  (KI-TQ-004) that `scripts/setup_ticket_worktree.py` and
  `templates/scripts/setup_ticket_worktree.py` show today.

**Negative:**

- Every `ensure` pays the install build (about 62 s on the reference host). Symlinking
  would save that time, but it is not possible on this platform.
- The marker becomes persistent state that must stay in step with the clone. A stale
  marker is a new failure surface, and `verify` has to catch it.
- About 250 references to `git worktree` across templates, scripts, tests and docs must
  migrate. The word "worktree" is kept for the landing directory and for the
  `worktree_path` JSON alias to limit the churn.

**Operational:**

- Cut-over chore: `git worktree prune`, then retire the registered worktrees and the WSL
  `background-worktrees` entries. Until then, apply §2 (`gc.auto=0`) to the main
  checkout.
- The landing place and the main checkout must be on the same volume for hardlinks to
  work (see A1.1's out-of-scope flip case).
- An `ensure` excluding the build should finish within 30 s on a project of about 8,500
  tracked files, and read-only verbs within 5 s.

## Alternatives

- **Keep `git worktree` behind the new maker.** Rejected. A worktree's `gitdir:` file
  embeds an absolute path in one platform's spelling, which strands entries across
  Windows and WSL (two are `locked initializing` today). Worktrees also share one hooks
  directory, so any worktree's hook install rewrites every sibling's hooks.
- **`--reference --dissociate` or `cp --reflink` as the first choice (original §1).**
  Rejected. On the reference host `--dissociate` measured 15.4 s and +54 MB against
  hardlinks, with no isolation gain. Reflink is unavailable on NTFS, so the first
  preference never applies there.
- **Symlink the main checkout's `.leafcutter` into each workspace.** Rejected.
  `os.symlink` fails with `WinError 1314` on the host, and under clones the link would
  point into a different repository. `Path(__file__).resolve()` would also follow it into
  the main tree (KI-CG-009, KI-FC-001, KI-BP-017).
- **Reuse `commit_guardian/_resolve_root.py` for project resolution.** Rejected. It walks
  up from `__file__` for `.git` or `CLAUDE.md` and caches the result in a module global.
  In a workspace under a non-repo parent it can resolve the wrong root, and it never
  notices a change of cwd.
- **Keep per-route creation logic and align it by convention.** Rejected. This is the
  current state, and the analysis traces F1, F2, F4, F6 and F9–F13 to divergence between
  routes. Nothing mechanical stops the routes from drifting again.

