---
title: "ADR-070: One Workspace Maker and One Project-Root Resolver, Each With a Single Tracked Source"
description: "Every route that needs an isolated workspace (long-running build, quick fix, requirements session, the workspace skill, a person at a terminal) obtains it from one stdlib-only maker, templates/scripts/worktree.py, which makes a hardlinked per-feature clone with real install files and answers in one result shape; project-root resolution lives in its own importable module beside it. Five routes with five hand-written creation paths produced five different kinds of workspace, and no caller could tell which properties it had actually been given."
type: "adr"
status: "active"
created: "2026-10-14"
last_updated: "2026-10-14"
deciders:
  - adr-author
  - architect-review
components:
  - worktree_manager
  - build_orchestration
  - build_pipeline
  - commit_guardian
affects_diagrams:
  - docs/architecture/components/worktree-manager.md
related_docs:
  - docs/architecture/adrs/ADR-018-agent-isolation-topology.md
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
  - docs/architecture/adrs/ADR-031-worktree-quality-gate-guard.md
  - docs/architecture/adrs/ADR-013-portable-skill-script-deployment-boundary.md
  - docs/architecture/adrs/ADR-069-durable-log-root-for-workspaces.md
  - docs/architecture/components/worktree-manager.md
  - docs/analysis/2026-09-25-worktree-isolation-decision-memo.md
  - docs/analysis/2026-09-25-worktree-creation-consolidation.md
  - docs/analysis/2026-09-25-worktree-component-proposal.md
  - docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300a-1.yaml
related_code:
  - templates/scripts/worktree.py
  - templates/scripts/workspace/workspace_root.py
  - scripts/build_phases_script_deploy.py
  - scripts/build_deploy_manifest_helpers.py
  - scripts/build.py
  - scripts/setup_ticket_worktree.py
  - templates/scripts/setup_ticket_worktree.py
  - templates/scripts/commit_guardian/_resolve_root.py
  - docs/components.json
---

# ADR-070: One Workspace Maker and One Project-Root Resolver, Each With a Single Tracked Source

## Status

| Field | Value |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-10-14 |
| **Author** | adr-author (dispatched for ticket BO-4300a-1 after architect-review) |
| **Supersedes** | None. Amends the creation-strategy ordering of [ADR-018 §1](ADR-018-agent-isolation-topology.md#1-per-feature-isolation--an-independent-clone-with-its-own-object-store) for this repository (see Decision §2); ADR-018's isolation principle is adopted unchanged. |

> Component IDs are drawn from `docs/components.json`. `worktree_manager` owns the
> workspace lifecycle this ADR binds; `build_orchestration` owns the routes that request
> workspaces; `build_pipeline` owns the deploy manifest that must ship the maker and
> resolver; `commit_guardian` owns the hooks whose firing the maker proves and the
> existing `_resolve_root.py` the new resolver must not reuse.

## Context

Leafcutter has five routes that ask for an isolated place to do one piece of work: a
long-running build (`/build-feature`, kind `epic`), a quick fix (kind `feature`), a
requirements-authoring session (`/plan-feature`, kind `ac`), an agent following the
workspace skill, and a person at a terminal. The
[worktree-consolidation analysis](../../analysis/2026-09-25-worktree-creation-consolidation.md)
found that these routes reach workspaces through several hand-written paths — the
subcommands of `setup_ticket_worktree.py`, free-form shell steps an LLM agent was asked to
run, and ad-hoc `git worktree add` calls in workflows — and that each path produced a
different kind of workspace. Some branched from local `main`, some from `origin/main`;
some had a real `.leafcutter/` install and some a symlink into the main checkout; some had
hooks that fired and some silently had none (ADR-031); `create-ac-worktree` and
`create-fastlane-worktree` lacked the repository-search fallback that `create-only` had
(KI-ACD-004). A caller could not tell, from the answer it received, which of those
properties it had actually been given. The analysis catalogues fourteen failure modes
(F1–F14) traced to this divergence.

Two further structural defects made the divergence self-perpetuating:

- **Two tracked copies of the creating script.** `scripts/setup_ticket_worktree.py` and
  `templates/scripts/setup_ticket_worktree.py` are both tracked and differ. Fixes and
  mutation probes landed in the wrong copy (KI-TQ-004,
  KI-TQ-20260831-mutation-probe-lands-in-the-wrong-copy), and CI's build overwrote one
  with the other.
- **Root resolution is re-implemented per caller.** About thirty hook resolvers walk up
  from `__file__` for `.git` or `CLAUDE.md`; `templates/scripts/commit_guardian/_resolve_root.py`
  additionally caches its answer in a module global. Under the [ADR-001](ADR-001-self-hosting-boundary.md)
  dev layout — the package repository as a child of a non-repository workspace parent —
  that walk can accept the workspace parent as the project
  (KI-CG-20260925-shared-root-resolver-accepts-non-repo-workspace-parent).

The user decided the isolation mechanism and the install form on 2026-09-25, accepting the
[decision memo](../../analysis/2026-09-25-worktree-isolation-decision-memo.md): per-feature
clones (accepting the direction of [ADR-018](ADR-018-agent-isolation-topology.md) §1),
real install files never a symlink, `origin/main` after a fetch as the base for every kind,
and one standalone script that always creates the workspace the same way. Those decisions
live in an analysis memo and an AC tree (BO-4300); none of them is yet recorded as a
binding architectural decision, and the originating ticket for AC
[BO-4300a-1](../../acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300a-1.yaml)
touches ADR-001 and ADR-018 directly. The cost of not recording it is that the next route
added — or the next fix to an existing one — re-creates a sixth path.

## Decision

### 1. Exactly one maker creates, locates, lists, verifies and removes workspaces

1. The package MUST deliver one workspace maker as a stdlib-only Python file whose
   tracked source is `templates/scripts/worktree.py` and whose deployed copy is
   `<install-root>/scripts/worktree.py`. The file name is provisional until BO-4300a-1 is
   built; once built, that deployed path is the contract every caller names.
2. The maker MUST expose exactly the verbs `ensure`, `locate`, `list`, `verify`, `remove`
   and `where`. `ensure` is the only creating verb and MUST be idempotent. `locate`,
   `list` and `verify` MUST be read-only. `where` MUST print the maker's own absolute path.
3. Every route — long-running build, quick fix, requirements session, workspace skill, and
   a person's terminal — MUST obtain its workspace by running
   `python <absolute path printed by where> ensure --kind <kind> --slug <identity> [...]`
   as a subprocess. A workflow step MUST NOT hand workspace creation to an agent as
   free-form shell work.
4. After BO-4300f-2 lands, any other code path in the package MUST NOT create, clone,
   locate or remove a workspace. `setup_ticket_worktree.py` (both copies) is retired by that AC.
5. Work identity and naming MUST live in one table inside the maker. Callers pass a kind
   and the raw identity they hold; the maker normalises it, so the same identity from any
   route yields the same landing location and the same line of work. The table MUST be
   able to carry an alias for legacy spellings (BO-4300a-2), because the naming scheme
   (consolidation analysis open question 4) is not yet decided.

### 2. Every workspace is the same kind of thing: a hardlinked per-feature clone with real install files

1. `ensure` MUST create a workspace as a hardlinked local-path clone of the main checkout
   (`git clone --no-checkout <main> <ws>`), then re-point `origin` at the hub. It MUST NOT
   use `git worktree`, `--shared`, or `--reference`. This amends ADR-018 §1's preference
   order (reflink copy, then `--reference --dissociate`, then plain clone) for this
   repository: the memo measured the hardlinked clone at about 11 s with packs shared by
   hardlink, and `--reference --dissociate` at 15 s plus 54 MB with no isolation benefit.
2. `ensure` MUST follow the decision memo's step order ("Consequences for the standalone
   script's contract", step 1): resolve the main checkout; read the hub from its `origin`
   (`NO_HUB` when absent); compute the landing place; verify-then-repair-or-refuse an
   existing location; clone; re-point `origin`; fetch `origin main` (`FETCH_FAILED` unless
   `--allow-stale-base`); check out the line of work from `origin/main` or resume
   `origin/<branch>`; set `gc.auto 0` and `maintenance.auto false`; copy `.env` and
   `.mcp.json`; run the install build inside the workspace with an explicit config path;
   install the shim for every hook stage the workspace's own hook declaration names;
   check the tree is clean; run one canary per declared stage; write the marker; emit the
   answer.
3. Every workspace MUST start from `origin/main` as read by the fetch at the time of its
   request, for every kind.
4. The install inside every workspace MUST be real files built from the workspace's own
   contents by `build.py --target-dir <ws> --config-path <explicit>`. The config path MUST
   be derived from the main checkout's own install config, stripping the
   `top_level_packages` prefix; when that is impossible the maker MUST fail with
   `NO_CONFIG` and MUST NOT fall back to the build's default config or to the maker's own
   location.
5. `os.symlink`, `ln -s`, `mklink` and junctions MUST NOT appear in the maker or in the
   install path it drives.
6. Every workspace's protections MUST be shown to fire before `ensure` answers ready: one
   canary commit per declared hook stage MUST be rejected by a real hook (ADR-031 §1).
   Any commit the maker makes MUST run with its working directory set to the workspace,
   never as `git -C <path> commit`, because the commit-delegation hook matches only the
   literal `git commit` (KI-CG-20260925-commit-delegation-hook-misses-git-dash-c).
7. Every workspace MUST land in the project's one landing place for workspaces
   (`<base>/worktrees/<slug>`). The word "worktree" is kept for that directory and for the
   result keys so existing references stay true.

### 3. The marker is the registry; every route gets the same answer shape

1. The maker MUST write a marker record in every workspace it makes. It MUST hold
   `schema_version`, `kind`, `slug`, `branch`, `hub`, `project_root` (absolute path of the
   main checkout the workspace was made from), `base_commit`, `maker_version`, `state`
   (`creating` | `ready`) and `created_at`.
2. The marker MUST be written atomically (temp file then replace), with `state: creating`
   immediately after the clone exists and `state: ready` as the last step of `ensure`. It
   MUST live outside version control and outside anything the install build rewrites or
   cleans.
3. `locate` and `list` MUST find workspaces by scanning the landing place's markers and
   MUST NOT call `git worktree list`; no git command lists clones.
4. `project_root` in the marker MUST be the only way a workspace identifies the project it
   belongs to (BO-4300b-1).
5. Every route MUST receive its answer in the same form — the BO-4300c-2 result contract —
   stating `status` and the workspace's location, with only identity-derived values (slug,
   branch, paths, commit) differing between routes. The marker MUST agree with the answer
   the route received.
6. A condition the maker cannot classify MUST produce an error answer with code
   `INTERNAL_ERROR` whose message names it — never an `ok` answer and never a traceback on
   stdout. The maker MUST NOT read stdin or prompt; every decision arrives as an argument.

### 4. Project-root resolution lives in its own module, separate from the maker

1. Project-root resolution MUST be delivered as a separate, stdlib-only, top-level
   importable module (source `templates/scripts/workspace/workspace_root.py`, name provisional; the maker's helpers live in the same `workspace/` package so `templates/scripts/` stays under the folder-density cap),
   deployed beside the maker at `<install-root>/scripts/`, with no import-time side
   effects.
2. Its one public function MUST take `(cwd: absolute path, repo_root: absolute path | None)`
   and return a result with `status` (`ok` | `NO_REPO` | `AMBIGUOUS_REPO`), `project_root`
   (on `ok` only), `how` (`argument` | `workspace-marker` | `git-common-dir` |
   `child-search` | `sibling-search`), `candidates` (on `AMBIGUOUS_REPO` only) and
   `searched_from` (on `NO_REPO` only). Its resolution order and exclusions are fixed by
   AC BO-4300b-1.
3. Every call MUST recompute; the module MUST NOT cache its answer.
4. The maker MUST import this module and MUST NOT re-implement resolution inline.
5. The module MUST NOT reuse, import, wrap or copy
   `templates/scripts/commit_guardian/_resolve_root.py`, which walks up from `__file__`
   and caches in a module global — both forbidden here. The module is the intended shared
   resolver for the duplication-audit cluster C4 hook resolvers that follow.

### 5. One tracked source each, and named deploy-manifest entries

1. The only tracked source of the maker and of the resolver module MUST be under
   `templates/scripts/`. A tracked copy of either MUST NOT exist under `scripts/` or
   anywhere else in the package repository; the
   `scripts/setup_ticket_worktree.py` / `templates/scripts/setup_ticket_worktree.py`
   dual-copy shape MUST NOT recur.
2. The maker and the resolver module MUST each have their own NAMED entry in the
   standalone-scripts deploy — `build_template_standalone_scripts` in
   `scripts/build_phases_script_deploy.py` (including its docstring list) and the matching
   helper in `scripts/build_deploy_manifest_helpers.py` — not rely on the shallow glob
   alone. Because that phase is non-recursive, every further helper module the maker
   imports MUST get its own named entry too.
3. Proof of these properties MUST run the DEPLOYED maker (and import the DEPLOYED resolver
   in a separate process) from the shared deployed layout, against real temporary git
   repositories with a real bare hub. Tests MUST NOT import the maker from source, mock
   git, grep its source, or spawn the package's own `build.py`.
4. `docs/components.json` → `worktree_manager` MUST describe per-feature clone workspaces
   made, found, listed and cleared through one maker, and MUST list the maker and the
   resolver module in `primary_code`.

## Consequences

### Positive

- **No route can get a lesser workspace.** Because every route runs the same `ensure`, a
  property one route's workspace has (independent clone, fresh base, own install, firing
  hooks, one landing place) is a property every route's workspace has. BO-4300a-1's
  cross-route equality test becomes a statement of the architecture, not of luck.
- **The answer is trustworthy.** The marker is written last and agrees with the answer, so
  a caller (or a later `verify`) can confirm what it was given instead of inferring it.
- **Shared-`.git` failures disappear for workspaces.** Clones share no refs, no
  `packed-refs` lock, no hooks and no auto-gc with the main checkout (F5, F7, F14 in the
  memo), and embed no platform-specific absolute path, so a workspace works from both
  Windows and WSL.
- **Fixes land once.** A single tracked source under `templates/scripts/` ends the
  wrong-copy class of defect for this component.
- **A resolver hooks can import.** The C4 cluster of about thirty hand-written resolvers
  gains a tested, uncached, non-`__file__` target to converge on.

### Negative

- **Every `ensure` pays the install build** (about 62 s measured), including on a reused
  workspace. This was already paid by today's `_bootstrap`, but no route can now skip it:
  there is deliberately no `--no-bootstrap` flag.
- **Clones cost more disk than worktrees** for the checkout itself (about 84 MB each);
  packs are hardlinked, so the object store is not duplicated on the same volume.
- **Hardlinks require the landing place to be on the same volume** as the main checkout.
  An adopter with a ~1 GB object store on a different volume loses the economy; the memo
  names `--reference --dissociate` as that adopter's fallback, and this ADR does not yet
  provide it.
- **Large migration surface.** `git worktree` appears in 16 template scripts, 7 workflows,
  7 skills, 4 agents, 27 `scripts/` files, 56 unit tests and 125 docs. Only create, locate
  and remove change, but every caller must move to the maker (BO-4300f-*).
- **No git command lists workspaces.** The marker scan is the only registry; a workspace
  whose marker is lost is invisible to `list` and must be detected by `verify` on its path.

### Operational

- Callers MUST halt on any answer other than `status: ok`; the answer's `workspace_path`
  (with `worktree_path` kept as an alias) and, when `--ticket` was passed,
  `ticket_path_in_worktree` are the only sources of location.
- The cut-over chore applies once: `git worktree prune`, retire the registered worktrees
  and the WSL `background-worktrees` entries, and set `gc.auto=0` on the main checkout
  (ADR-018 migration step 2) in the meantime.
- Open questions 4 (naming scheme), 5 (where adopter workspaces live), 6 (whether
  `leafcutter-ai/.leafcutter/` should exist) and 8 (the discard authorisation for
  `remove`) remain open and are decided in their own ACs; this ADR binds only what the
  maker must do regardless of their answers.
- Performance budget: excluding the install build, `ensure` on a project of
  leafcutter-ai's size MUST complete within 30 s on the reference Windows host, and
  read-only verbs within 5 s.
- The workspace inherits the main install's durable log root through its own build
  ([ADR-069](ADR-069-durable-log-root-for-workspaces.md)); that rule is unchanged.

## Alternatives

- **Keep `setup_ticket_worktree.py` and harden each subcommand.** Rejected. The
  subcommands are separate creation paths, and the evidence (KI-ACD-004: `create-only`
  got the search fallback, `create-ac-worktree` and `create-fastlane-worktree` did not)
  shows a fix to one path does not reach the others; the dual tracked copy also keeps the
  wrong-copy defect alive.
- **Keep `git worktree` as the mechanism behind the one maker.** Rejected. Worktrees share
  one `.git` (the 0-byte-object corruption class of ADR-018), have no per-worktree hooks
  directory so `pre-commit install` rewrites the shared hook, and embed a platform-specific
  `gitdir:` path that broke WSL-created worktrees on Windows — all measured in the memo.
- **`cp --reflink` or `git clone --reference --dissociate` (ADR-018 §1's preferred order).**
  Rejected for this repository. Reflink is unavailable on the NTFS reference host, and
  `--reference --dissociate` measured 15.4 s plus 54 MB against 10.8 s and hardlinked packs
  for a local-path clone, buying no additional isolation.
- **Symlink the main install's `.leafcutter` into each workspace.** Rejected. `os.symlink`
  fails with `WinError 1314` on the reference host; under clones a symlink points into a
  different repository; and `Path(__file__).resolve()` through the link sends 62 sites in
  41 template scripts into the main tree (KI-CG-009, KI-FC-001, KI-BP-017).
- **Let each route create its workspace and share only a verification step.** Rejected.
  Verification after the fact detects a lesser workspace but cannot stop a route from
  producing one, and leaves N creation paths to keep in sync; the five-route equality the
  AC demands is only guaranteed if creation itself is shared.
- **Put root resolution inside the maker, or reuse `commit_guardian/_resolve_root.py`.**
  Rejected. Inline resolution cannot be imported by hooks without pulling in the maker's
  CLI, so the C4 resolvers would keep their own copies; `_resolve_root.py` walks up from
  `__file__` and caches in a module global, which is exactly the behaviour that accepts the
  non-repository workspace parent under the ADR-001 dev layout.
- **Let an LLM agent run workspace creation as free-form shell (broaden worktree-agent).**
  Rejected by the user (consolidation analysis question 7): it puts a model in the create
  path, which is how the 2026-09-25 `/plan-feature` incident produced a wrong workspace.

## References

- Originating ticket: `tickets/00_inbox/epics/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01_TICKET-20260927-BO-4300a-1.md`
  (AC [BO-4300a-1](../../acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300a-1.yaml)).
- Related ACs: BO-4300a-2 (legacy aliases), BO-4300b-1 (resolution order), BO-4300c-1-ii
  (per-stage shims), BO-4300c-2 (result contract), BO-4300d-4 (resume), BO-4300f-2
  (retire `setup_ticket_worktree.py`), BO-4300f-4 (shared test locator).
- [ADR-018 — Agent Isolation Topology](ADR-018-agent-isolation-topology.md) — the
  per-feature-clone principle this ADR implements; §1's creation order is amended here.
- [ADR-001 — Self-Hosting Boundary](ADR-001-self-hosting-boundary.md) — the template-source
  / deployed-output boundary and the dev layout the resolver must not misread.
- [ADR-031 — Worktree Quality Gate Guard](ADR-031-worktree-quality-gate-guard.md) — the
  canary-proven gate-readiness invariant the maker satisfies per stage.
- [ADR-013 — Portable Skill Script Deployment Boundary](ADR-013-portable-skill-script-deployment-boundary.md)
  — deployed scripts are the runtime contract.
- [ADR-069 — Durable Log Root for Workspaces](ADR-069-durable-log-root-for-workspaces.md).
- [Decision memo](../../analysis/2026-09-25-worktree-isolation-decision-memo.md),
  [consolidation analysis](../../analysis/2026-09-25-worktree-creation-consolidation.md),
  [component proposal](../../analysis/2026-09-25-worktree-component-proposal.md).
- [Worktree Manager component](../components/worktree-manager.md).
