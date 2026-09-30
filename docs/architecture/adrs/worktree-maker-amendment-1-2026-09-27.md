---
title: "ADR-018 Amendment 1 (2026-09-27) — One workspace maker, hardlinked clones, real install files"
description: "The full decision record for ADR-018's 2026-09-27 amendment: why the original per-clone creation-strategy preference order changed, the normative A1.1-A1.7 decision points for the single workspace-maker script, its consequences, and the alternatives considered. Revision 1 (2026-09-30) fixes the project-resolution order (A1.8), the per-project sibling landing root and its only override (A1.9-A1.10), and a config derivation that works in the dev layout (A1.11-A1.12). Split out of ADR-018 to keep that file under the ADR length ratchet."
type: adr
status: active
created: 2026-09-27
last_updated: 2026-09-30
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
related_code:
  - templates/scripts/worktree.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_admin.py
  - templates/scripts/worktree_layout.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
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
run the install build inside the workspace with an explicit config path, derived by A1.11.
When the derivation is impossible, the maker MUST fail with `NO_CONFIG`. It MUST NOT fall
back to the build's default config or to its own location. *(Revised 2026-09-30. The
derivation originally read: "That path is derived from the main checkout's own install
config by stripping the `top_level_packages` prefix." As shipped, that rule never stripped
anything and never looked above the main checkout. See
[Revision 1](#revision-1--2026-09-30--resolution-order-landing-root-and-config-derivation).)*
Neither the maker nor
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
and caches its answer in a module global. The resolution order and its exclusions are
fixed by A1.8 (BO-4300b-1). *(Revised 2026-09-30. This sentence originally read: "This
amendment does not fix the resolution order or its exclusions: BO-4300b-1 owns them.")*

**A1.6 — One tracked source, named deploy entries.** The only tracked source of the maker and
of the resolver module MUST be `templates/scripts/`. No tracked copy MUST exist under
`scripts/` or anywhere else in the package repository. Each module MUST have its own named
entry in `build_template_standalone_scripts` (`scripts/build_phases_script_deploy.py`) and in
the matching helper in `scripts/build_deploy_manifest_helpers.py`. The shallow glob alone
is not enough, because that deploy phase is non-recursive. Tests MUST exercise the deployed
copy and MUST NOT fall back to the `templates/` source. *(Corrected 2026-09-30. Under
BO-4300a-1, `build_template_standalone_scripts` and its `NAMED_STANDALONE_SCRIPTS` list moved
to `scripts/build_phases_script_deploy_standalone.py`. `build_phases_script_deploy.py`
re-exports them. The build deploys into its output root, so deployed copies land in
`<install-root>/.leafcutter/scripts/<name>`, not in `<install-root>/scripts/` as A1.2, A1.5
and this point first said.)*

**A1.7 — §2 applied per workspace.** `ensure` MUST set `gc.auto 0` and
`maintenance.auto false` in every workspace it makes.

**Decided since (user, 2026-09-28).** Question 5 (where workspaces land) is recorded here
as A1.9 and A1.10
([Revision 1](#revision-1--2026-09-30--resolution-order-landing-root-and-config-derivation)).
Questions 4 (one naming scheme `<kind>/<slug>`), 6 (`leafcutter-ai/.leafcutter/` must not
exist) and 8 (a one-time discard token for `remove`) are recorded in the AC store
(BO-4300a-2, BO-4300f-2, BO-4300e-3). This amendment does not decide them. *(Revised
2026-09-30. This paragraph originally listed questions 4, 5, 6 and 8 as open.)*

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

## Revision 1 — 2026-09-30 — Resolution order, landing root and config derivation

| Field | Value |
|---|---|
| Amends | A1.3 (config derivation, now A1.11); completes A1.5 (resolution order, A1.8); adds A1.9, A1.10 and A1.12 |
| Status | Proposed |
| Date | 2026-09-30 |
| Author | adr-author (ticket BO-4300b-1) |
| Driven by | [Ticket 04](../../../tickets/00_inbox/epics/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04_TICKET-20260928-BO-4300-project-resolution.md) ([BO-4300b-1](../../acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300b-1.yaml), [BO-4300b-2](../../acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300b-2.yaml), [BO-4300b-3](../../acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300b-3.yaml) and their children); user decision Q5 of 2026-09-28; pr-reviewer finding H-2 (2026-09-28 02:15) on BO-4300a-1 |
| Supersedes | The `worktrees/<slug>` landing folder of BO-4300 fixed decision 1; the memo's `<base>/worktrees/<slug>` (`ensure` step 3); and the `<consumer_root>/worktrees/<slug>` location in [ADR-001](ADR-001-self-hosting-boundary.md#installed-layout-path-resolution-ac-bo-1500e-2). ADR-018 itself is not superseded. |

### Context — why this had to change

- **The resolution order was open.** A1.5 left it to BO-4300b-1, and `workspace_root.py`
  implements only the explicit argument and `git rev-parse`, so the folder above the project
  or a sibling folder answers `NO_REPO`. The older resolvers disagree on ambiguity: one takes
  the first match, another refuses anything but exactly one (F3, F11, KI-ACD-004). The
  dev-layout workspace parent holds a hooks-only `.git/` folder and a `CLAUDE.md`, so an
  upward walk that accepts either picks a folder that is not a project
  (KI-CG-20260925-shared-root-resolver-accepts-non-repo-workspace-parent).
- **A1.3's config rule never fired.** As shipped by BO-4300a-1, `derive_config_path()` looks
  only inside the main checkout and tests `.claude`-style folder names against
  `top_level_packages`, which lists package folders, so it never strips anything. In the
  package's dev layout the config is `<workspace-folder>/.claude/skills_config.json`, one
  level above the package repository, with `top_level_packages: ["leafcutter-ai"]` and every
  path prefixed `leafcutter-ai/`. The package repository has no `skills_config.json`, so the
  rule answers `NO_CONFIG`; the old routes' builds ran on defaults (see the memo).
- **Q5 was open.** Workspaces landed at `<workspace-folder>/worktrees/<slug>` (dev) or
  `<consumer_root>/worktrees/<slug>` (consumer, ADR-001). The consumer rule put full clones
  inside the consumer's working tree, where tools and tests scan, and one shared `worktrees/`
  per parent folder lets two projects' `alpha` collide. On 2026-09-28 the user decided: one
  sibling folder per project, overridable only by an explicit, validated `--landing-root`.

### Decision

**A1.8 — Resolution order (completes A1.5).** `templates/scripts/workspace_root.py` MUST
resolve the project in exactly this order and MUST recompute every answer from its own
inputs:

1. `--repo-root P`, when given. P counts only when it passes step 3's test. Otherwise the
   answer is `NO_REPO`, naming P.
2. Otherwise, the parent of `git rev-parse --path-format=absolute --git-common-dir`, with git
   run in cwd. When that folder holds the maker's marker record, the project MUST be the
   marker's recorded `project_root`, never the clone itself. When the recorded `project_root`
   is missing or is not a repository, the answer MUST be `NO_REPO`, naming the marker.
3. Otherwise, a bounded search of cwd's immediate children. cwd's siblings are searched only
   when the children give no candidate. A folder is a candidate only when git, run in that
   folder, reports the folder itself as the top level (`git rev-parse --show-toplevel`). An
   empty `.git` folder and a bare repository are therefore never candidates. A maker-made
   workspace counts as its recorded project. Candidates MUST be de-duplicated by resolved
   project. If one remains, it is the project. If more than one remains, the answer MUST be
   `AMBIGUOUS_REPO`, listing every candidate. Taking the first match is not allowed.
4. Otherwise, `NO_REPO`, naming `searched_from` (the folder the request started from).

Resolution MUST NOT anchor on the file location of the maker, the resolver or any installed
copy (`__file__` or equivalent); read any installed copy's contents, stale or current
(BO-4300b-2-ii); walk upward accepting a folder because it holds `.git` or `CLAUDE.md`;
cache an answer (module global, file or environment); or infer a project from a folder's
position under a landing root. The marker's `project_root` is the only link from a
workspace to its project (A1.4). A refusal during resolution MUST write nothing: no landing
root, lock, branch or marker in any candidate.

**A1.9 — One landing root per project (Q5).** The landing root MUST be
`<parent-of-project>/<project-dir-name>-worktrees/`, where the project is the main checkout
that A1.8 resolved, and each workspace MUST land at `<landing-root>/<kind>/<slug>` for its
canonical identity (Q4, BO-4300a-2). It MUST be derived from the resolved project only,
never from cwd, the maker's or any install's location, an environment variable or a config
key (the legacy `worktree_base_path` included). The same rule MUST hold in the dev layout
(`leafcutter-ai` → `<parent>/leafcutter-ai-worktrees/`) and the consumer layout; `layout` is
still reported as `dev` or `consumer` but does not change the location. The maker MUST NOT
create anything inside the project's working tree and MUST NOT write an ignore entry.
`ensure`, `locate`, `list`, `verify` and `remove` MUST all compute the location through one
function.

`locate` and `list` MUST filter markers by `project_root`. When an `ensure` finds its
location already holding another project's workspace, it MUST be refused `OCCUPIED` with
occupant kind `other-project` (BO-4300d-3), and that workspace MUST be left untouched.

**A1.10 — The only override is `--landing-root`.** Only an explicit `--landing-root P` on
`ensure`, `locate`, `list`, `verify` or `remove` overrides A1.9. The maker MUST NOT take an
override from the environment or from a config setting, and MUST NOT remember one. Before
writing anything, the maker MUST check that P (1) is absolute, since resolving a relative P
against cwd would make the location depend on the starting folder; (2) lies outside the
project's working tree; (3) lies inside no existing workspace; (4) lies inside no other git
repository; and (5) can be created and written (its nearest existing ancestor is a writable
folder). A P that breaks any rule MUST be answered with status `error`, code `USAGE` and
exit 64, with a message naming the broken rule, and nothing MUST be written. Under an
override, workspaces land at `<P>/<kind>/<slug>` and are found only when the same override
is given.

**A1.11 — Config derivation (replaces A1.3's rule).** On every `ensure`, the explicit
`--config-path` MUST be derived from the resolved project, in this order:

1. **The project's own config.** This is the first `<project>/<d>/skills_config.json` found,
   trying `<d>` in build.py's own auto-detect order: `.claude`, `.gemini`, `.cursor`,
   `.github`, `.cline`. When the workspace's checkout has a file at the same relative path,
   that file MUST be passed unchanged. When it does not (the config is untracked), the maker
   MUST write a byte-identical copy to the derived-config file.
2. **The enclosing install's config (dev and self-hosted layouts).** Otherwise, this is the
   first `<parent-of-project>/<d>/skills_config.json` in the same order. It counts only when
   its `top_level_packages` holds an entry equal to the project's directory name (ignoring
   one trailing `/`). The maker MUST write the derived-config file as that JSON with two
   changes, applied at every depth:
   - the prefix `<project-dir-name>/` is removed wherever it starts a string value or a
     whitespace-separated token inside a string value;
   - the project's own entry is removed from `top_level_packages`.
3. Otherwise, the answer is `NO_CONFIG`, and its message names both folders searched.

The derived-config file MUST be `<workspace>/.leafcutter/derived_skills_config.json`. It sits
beside the marker record, outside version control. The maker MUST NOT pass a path outside
the workspace. It MUST NOT read any folder above the project's parent. It MUST NOT read
anything under an install output root (`.leafcutter/`) other than the workspace's own.

**A1.12 — Module ownership (extends A1.5 and A1.6).** `workspace_root.py` MUST own A1.8 and
nothing else. A new stdlib-only module, `templates/scripts/worktree_layout.py`, MUST own
A1.9, the A1.10 checks, A1.11 and the `dev`/`consumer` classification. `resolve_repo_root`,
`landing_place`, `layout_for`, `derive_config_path` and `_read_top_level_packages` MUST move
there from `worktree_git.py`, and `worktree_git.py` MUST NOT keep a copy. `worktree.py`
parses `--landing-root`. `worktree_admin.py` applies it for `list` and `remove`.

Per A1.6, `worktree_layout.py` MUST have its own named entry in `NAMED_STANDALONE_SCRIPTS`
(`scripts/build_phases_script_deploy_standalone.py`) and in the matching helper in
`scripts/build_deploy_manifest_helpers.py`. Git MUST run with its working directory set to
the target, or with `-C <path>` for any verb other than `commit`.

### Consequences

**Positive:**

- The same request gives the same workspace from any folder in or around the project. A
  request that cannot be answered reports what it saw (`searched_from`, `candidates`)
  instead of guessing.
- Two projects in one parent folder cannot share a landing root. Nothing the maker makes
  shows up in a project's own `git status`, scans or tests.
- A stale installed copy, like the one inside the package repository today, cannot change
  which project is found (BO-4300b-2-ii), whether or not BO-4300f-2 deletes it.
- The package's own workspaces build with a real, derived config instead of the build's
  defaults.

**Negative:**

- Workspaces under the old `<workspace-folder>/worktrees/<slug>`, including this epic's own,
  sit outside every landing root, so `locate` and `list` never report them. Retiring them is
  the cut-over's job (BO-4300f-3).
- In ADR-001's nested shape (`my-project/leafcutter-ai/`, with `leafcutter-ai` resolved), the
  default landing root `my-project/leafcutter-ai-worktrees/` lies inside the enclosing
  repository's working tree, which sees it as untracked unless its owner ignores it. A1.10
  refuses that location as an override: the default is the user's decided rule, and the
  checks guard caller-supplied paths.
- A folder holding several repositories refuses rather than picks, so a request started
  there, or a test fixture with a seed repository beside the project, needs `--repo-root`.
- Prefix stripping is textual. A value naming `<project-dir-name>/` anywhere other than the
  start of a value or token keeps it, and points at a path the workspace does not have.
- A workspace made under `--landing-root` is invisible to every verb called without the same
  override.

**Operational:**

- An override on a different volume from the project loses A1.1's hardlinks. Git falls back
  to copying objects, which is slower and uses more disk.
- `worktree_base_path` in existing `skills_config.json` files no longer has any effect on the
  maker.
- Tests that exercise resolution MUST bound git's discovery, for example by setting
  `GIT_CEILING_DIRECTORIES` to the temp root. Otherwise a developer's own repository above
  the temp folder can become a candidate.

### Alternatives

- **Keep `worktrees/<slug>` under the workspace folder or the consumer root.** Rejected. In
  the consumer layout, full clones sit inside the consumer's working tree, where every scan
  and test walks into them unless an ignore entry is written. One shared `worktrees/` per
  parent folder also sends two projects' `alpha` to the same path.
- **A landing root inside the project (`.worktrees/`, `.claude/worktrees/`).** Rejected. It
  needs an ignore entry in the project, and every tool that walks the project still descends
  into nested full clones.
- **Take the landing root from an environment variable or from `worktree_base_path`.**
  Rejected. Two callers with different environments or configs would get two workspaces for
  one request. That is the cwd-dependence problem (F3) moved into the environment. Q5 allows
  only an explicit argument.
- **Take the first match when several projects qualify** (`check_workspace_setup_permission.py`).
  Rejected. The folder listing order would then decide which project gets a workspace. That
  is the guess BO-4300b forbids.
- **Walk upward to the first folder holding `.git` or `CLAUDE.md`** (`_resolve_root.py`), **or
  to the first config.** Rejected. The dev-layout workspace parent holds both and is not a
  project, and an unbounded config search can pick up an unrelated project's config. One
  level up, only when `top_level_packages` names the project, covers the dev and
  self-hosted layouts and nothing else.
- **Infer a workspace's project from its position under a landing root.** Rejected.
  `--landing-root` can put a workspace anywhere, so its position can point to the wrong
  project or to none. The marker's `project_root` travels with the clone.
- **Pass the found config's own path to the build.** Rejected. build.py's config migration
  (`_migrate_skills_config`) rewrites the file it is given, so a workspace build could edit
  the main checkout's config or the enclosing install's config. In the dev layout, every
  path would also keep its `leafcutter-ai/` prefix and point at folders the workspace does
  not have.
- **Resolve a relative `--landing-root` against cwd.** Rejected. The same request started from
  two folders would then land in two places, which breaks BO-4300b-1.

