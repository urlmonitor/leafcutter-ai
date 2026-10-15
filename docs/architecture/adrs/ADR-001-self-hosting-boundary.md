---
title: "ADR-001: Self-Hosting Boundary — Config-Driven Path Resolution"
description: Documents the self-hosting boundary for leafcutter-ai — config-driven
  path resolution, build output separation, and user-curated PROJECT_CONTEXT.md preservation
  across upgrades. Amendment 1 binds that the dev-layout workspace parent is never a project
  and that the project is resolved from the request, never from a script's own location.
created: '2026-08-13'
last_updated: '2026-10-14'
type: adr
status: active
components:
  - build_pipeline
  - worktree_manager
  - build_orchestration
related_docs:
  - docs/architecture/adrs/ADR-004-consolidated-output-root.md
  - docs/architecture/adrs/ADR-031-worktree-quality-gate-guard.md
  - docs/architecture/adrs/ADR-070-single-workspace-maker-and-resolver.md
  - docs/architecture/components/worktree-manager.md
  - docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300b-1.yaml
related_code:
  - scripts/build.py
  - scripts/setup_ticket_worktree.py
  - templates/scripts/worktree.py
  - templates/scripts/workspace/workspace_root.py
  - templates/scripts/commit_guardian/_resolve_root.py
---
# ADR-001: Self-Hosting Boundary — Config-Driven Path Resolution

## Status

Accepted (2026-05-19). Amended by [Amendment 1](#amendment-1--2026-10-14--the-workspace-parent-is-never-the-project)
(2026-10-14, Accepted 2026-10-15) — project-root resolution in the dev layout.

## Context

The leafcutter repository is simultaneously:
1. The package source (templates, scripts, config)
2. A target project that `build.py` writes into
3. The development environment for working on leafcutter itself

This creates confusion: `docs/vision.md` at root is a template placeholder, `tickets/` holds scaffold output, and `.claude/agents/` contains compiled agents that are also the dev tools. A newcomer cannot tell what is source vs output.

The brainstorm at `leafcutter-ai/docs/brainstorm-self-hosting.md` evaluated four options:
- **Option A:** Single repo, leafcutter eats itself (status quo — confusing)
- **Option B:** Two separate repos (overhead, submodule pain)
- **Option C:** Single repo, separate config targets (chosen)
- **Option D:** Templates as source of truth, no compilation (breaks `{{config.*}}` injection)

## Decision

We chose a variant of Option C: **all project content lives under `leafcutter-ai/`**, and `build.py` reads all scaffold target paths from `skills_config.json` rather than hardcoding them.

Specifically:
- **Tickets** live at `leafcutter-ai/tickets/` (config: `tickets_inbox_path`)
- **Docs** live at `leafcutter-ai/docs/` (config: `docs_root`)
- **Changelog** lives at `leafcutter-ai/docs/changelog/` (config: `changelog_folder`)
- **Build outputs** (`.claude/agents/`, `.claude/skills/`, `scripts/commit_guardian/`, etc.) go to the project root since that's where Claude Code expects them
- **`build.py` requires onboarding** — it refuses to run without `.claude/skills_config.json`, directing the user to run `/onboard` first
- **`.agents/agents/*/PROJECT_CONTEXT.md`** files are **user-curated context files** that live outside the build output tree. `build.py` never writes to `.agents/agents/` — these files are preserved across every upgrade. A project's `frontend-coder/PROJECT_CONTEXT.md` containing a custom `design_system` block (e.g. `primary_colour`, `font_heading`) will survive a `build.py` upgrade run untouched. The unified `frontend-coder` agent reads this file at runtime and applies the custom brand values, overriding the embedded design defaults (see `project_context_discovery.py` and ADR-025).

We did NOT implement a `--self` flag (as originally proposed). Instead, the config-driven approach is more general: any project can point paths wherever it wants, and leafcutter's own config simply points them into `leafcutter-ai/`.

## Consequences

**Positive:**
- Clear boundary: everything in `leafcutter-ai/` is source, everything at root is build output
- `build.py` works the same way for leafcutter itself and for consumer projects — no special modes
- Onboarding is required, which prevents unconfigured builds from polluting the tree

**Negative:**
- Root-level `scripts/commit_guardian/` and `scripts/doc_compliance/` are still build outputs at root (can't move them without breaking hook paths in `.pre-commit-config.yaml`) — resolved by [ADR-004](ADR-004-consolidated-output-root.md), which consolidates all outputs under `.leafcutter/` with a shim layer
- The glossary CLAUDE.md section uses marker-based idempotency, so changing `docs_root` doesn't auto-update existing markers — requires a one-time manual fix

**User-Owned Context Files (preserved across upgrades):**
- `.agents/agents/*/PROJECT_CONTEXT.md` files are user-owned and are never written by `build.py`. Projects that customise a `design_system` key in `frontend-coder/PROJECT_CONTEXT.md` (e.g. `primary_colour: "#E11D48"`, `font_heading: "Montserrat"`) will see those values preserved on every upgrade run. The unified `frontend-coder` agent reads the file at runtime and applies the custom brand values above the embedded design defaults.
- The legacy `frontend-design` skill has been deprecated (marked `deprecated: true` in its `SKILL.md` frontmatter). Its design principles are now embedded directly in the `frontend-coder` agent template. `build.py` skips deprecated skills entirely and will not deploy `.claude/skills/frontend-design/` on fresh installs or upgrades.

## Installed-Layout Path Resolution (AC BO-1500e-2)

When leafcutter-ai is cloned into a consumer project as a subdirectory
(`my-project/leafcutter-ai/`), `setup_ticket_worktree.py` must resolve the
repository root and the AC store location from the actual installed layout rather
than assuming the dev workspace layout.

The resolution is performed by `_resolve_installed_layout()` in
`scripts/setup_ticket_worktree.py`. It probes the parent of the leafcutter-ai git
root with `git rev-parse --show-toplevel`:

- If the parent is **not** a git repository (dev layout): `worktrees_base` is the
  workspace parent, preserving the existing sibling-worktrees convention.
- If the parent **is** a git repository with a different toplevel (consumer layout):
  `repo_root` and `worktrees_base` are both set to the consumer project root.
  Worktrees are then created at `<consumer_root>/worktrees/<slug>` and the AC store
  at `<consumer_root>/worktrees/<session>/docs/acceptance-criteria/`.

This means `/create-ac` and `/plan-feature` function correctly in both layouts
without any user configuration. See
[Agent Delivery Workflows §9](../agent_delivery_workflows.md#9-installed-copy-path-resolution-bo-1500e-2)
for the full detection flowchart and directory tree examples.

> **Amended.** `_resolve_installed_layout()` derives the layout from the position of the
> leafcutter-ai checkout, which is a location-of-the-script anchor. For workspace creation
> that anchor is replaced by [Amendment 1](#amendment-1--2026-10-14--the-workspace-parent-is-never-the-project):
> the project is resolved from the request's own inputs, and the landing place is derived
> from the resolved project. This section stays true for `setup_ticket_worktree.py` until
> BO-4300f-2 retires it.

## Alternatives

The `--self` flag approach was rejected because it adds a special code path that only leafcutter uses. Config-driven paths are more general and testable.

## Amendment 1 — 2026-10-14 — The workspace parent is never the project

| Field | Value |
|---|---|
| Amends | Context (the dev layout) and "Installed-Layout Path Resolution" |
| Status | Accepted (2026-10-15) |
| Date | 2026-10-14 |
| Author | adr-author (ticket BO-4300b-1, after architect-review) |
| Driven by | AC [BO-4300b-1](../../acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300b-1.yaml), epic `EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace` |
| Supersedes this ADR? | No. The source/output boundary and config-driven paths are unchanged. The resolution rule itself is [ADR-070 §4](ADR-070-single-workspace-maker-and-resolver.md#4-project-root-resolution-lives-in-its-own-module-separate-from-the-maker). This amendment states what that rule means for the layout ADR-001 defines. |

### Context

ADR-001 puts the package repository (`leafcutter-ai/`) inside a workspace parent
(`leafcutter/`) that is **not** a repository but holds build outputs: `.claude/`, `scripts/`,
`.leafcutter/` and a `CLAUDE.md`. Two consequences of that layout were never written down:

1. **The workspace parent looks like a project and is not one.** It has a `CLAUDE.md`, and in
   some setups a `.git` entry that git does not accept as a repository. Any resolver that
   walks up and stops at the first folder where "`.git` exists" or "`CLAUDE.md` exists" can
   return the workspace parent. `templates/scripts/commit_guardian/_resolve_root.py` does
   exactly that, and it also caches its answer in a module global
   (KI-CG-20260925-shared-root-resolver-accepts-non-repo-workspace-parent).
2. **The deployed copy of a script lives outside every repository.** In the dev layout,
   `leafcutter/scripts/` and `leafcutter/.leafcutter/` are under the workspace parent. In
   the consumer layout they are inside the consumer project. So a script that finds "the
   project" from its own `__file__` gets an answer that does not depend on where the request
   was made. In the dev layout that answer is wrong.

The 2026-09-25 run (failure mode F3 in the
[failure-modes analysis](../../analysis/2026-09-25-worktree-failure-modes.md)) started from
the workspace parent and got nulls. The same request from inside the project got the right
answer. Results depended on the working directory.

### Decision

1. **The ADR-001 workspace parent MUST NOT be resolved as a project.** A folder counts as a
   project only when git itself confirms it is a repository. An empty `.git/` folder does not
   count, and neither does a `CLAUDE.md`, `.claude/` or `.leafcutter/`.
2. **Workspace creation MUST resolve the project from the request, never from a script's own
   location.** The maker (`templates/scripts/worktree.py`, ADR-070 §1) MUST get the project
   from the resolver module (`templates/scripts/workspace/workspace_root.py`, ADR-070 §4).
   The resolver MUST apply this order and nothing else:
   1. `--repo-root`, when given.
   2. Otherwise, the parent of `git rev-parse --path-format=absolute --git-common-dir` run
      from the request's cwd. If that folder holds the maker's marker record, the project is
      the marker's recorded `project_root`, never the workspace clone itself.
   3. Otherwise, a bounded search of cwd's immediate children, then of cwd's siblings. A
      candidate counts only when git confirms it is a repository. A maker-made workspace
      counts as its recorded project. Candidates MUST be de-duplicated by resolved project,
      and exactly one MUST remain. More than one gives `AMBIGUOUS_REPO` listing the
      candidates.
   4. Otherwise, `NO_REPO`, naming `searched_from`.

   This is how a request from the workspace parent finds the single package repository below
   it (step 3) and does not return the parent.
3. **Resolution MUST NOT anchor on, walk up for, or cache anything.** The resolver and the
   maker MUST NOT use `__file__` (or anything equivalent) to locate the project. They MUST
   NOT walk upward and accept a folder because it has `.git` or `CLAUDE.md`. They MUST NOT
   cache an answer in a module global, a file or the environment. Every call MUST recompute
   from its own inputs.
4. **A workspace MUST identify its project only through the maker's marker record.** A
   folder's position under `worktrees/` (or any other landing place) MUST NOT be used to
   infer its project. If the marker's `project_root` is missing or is not a repository, the
   answer MUST be `NO_REPO` naming the marker. It MUST NOT fall back to the clone itself or
   to a folder guessed from the path.
5. **The landing place MUST be derived from the resolved project only, never from cwd.** For
   the dev layout, that means the same request for the same work gets the same workspace
   location whether it was started from the project's top folder, a folder deep inside it,
   the workspace parent, a sibling folder, another workspace, or the target workspace itself.
6. **`templates/scripts/commit_guardian/_resolve_root.py` MUST NOT be the workspace
   resolver.** The resolver MUST NOT reuse, import, wrap or copy it (ADR-070 §4.5). Its
   behaviour for its roughly forty existing hook callers stays as it is under this
   amendment. Any change to that file under BO-4300b-1 MUST be limited to marking it as not
   the project resolver (for example, a docstring pointing to the resolver module). Moving
   those callers to the resolver module is the separate duplication-audit cluster C4 work.
7. **`scripts/build.py` MUST deploy the resolver module as a named entry,** as ADR-070 §5.2
   requires, so that the deployed maker in both layouts imports the resolver from its own
   install and never from the source tree.

### Consequences

#### Positive

- **The answer no longer depends on where the request starts.** All six starting points in
  BO-4300b-1 give the same project and the same workspace location, so F3 is fixed for
  workspace creation.
- **The dev layout and the consumer layout behave the same.** Neither one's answer depends
  on where the deployed script happens to sit, which is the ADR-001 principle of "no special
  modes" applied to resolution.
- **Failures are named, not guessed.** An empty `.git`, a second candidate repository or a
  stale marker gives `NO_REPO` or `AMBIGUOUS_REPO` with the evidence, instead of a confident
  wrong root.

#### Negative

- **Two resolvers exist for a while.** Hooks keep using `_resolve_root.py`, with its upward
  walk and cache, until the C4 migration. Under the dev layout a hook can still misread the
  workspace parent, but the workspace maker cannot.
- **A request from a folder that has two candidate repositories below or beside it now
  fails** with `AMBIGUOUS_REPO` instead of picking one. The caller has to pass `--repo-root`
  or start from inside the project.
- **A workspace whose marker is lost or stale can no longer find its project.** Its path is
  deliberately not used as a fallback.

#### Operational

- Proof MUST run the deployed maker and the deployed resolver as separate processes,
  against real temporary repositories. Git discovery in those tests is bounded with
  `GIT_CEILING_DIRECTORIES`, so the developer's own repository can never be picked up.
- The "Installed-Layout Path Resolution" section above stays true for
  `setup_ticket_worktree.py` until BO-4300f-2 retires both copies. A new caller MUST NOT adopt
  `_resolve_installed_layout()`.

### Alternatives

- **Keep `_resolve_installed_layout()` (derive the layout from the leafcutter-ai checkout's
  position).** Rejected. It anchors on where the script lives, so its answer does not change
  with the request. In the consumer layout the deployed copy sits inside the consumer
  project, and in the dev layout it sits outside every repository. Both give a wrong answer
  for some starting points.
- **Reuse or harden `commit_guardian/_resolve_root.py`.** Rejected. It walks up from
  `__file__`, accepts `.git` or `CLAUDE.md` as proof of a project, and caches in a module
  global, which is all three forbidden behaviours. Changing its behaviour in place would also
  shift the answer for about forty hook callers that this ticket does not own.
- **Use `git rev-parse --show-toplevel` from cwd alone.** Rejected. From the workspace parent
  it fails, because the parent is not a repository, so the request gets no project (the F3
  null). Inside a workspace clone it returns the clone, not the project the clone was made
  from.
- **Infer a workspace's project from its position under `worktrees/`.** Rejected. A workspace
  can be moved, and a landing place can be shared or configured. A path guess turns a
  missing marker into a confident wrong project instead of a named `NO_REPO`.

## See Also

- [ADR-031 — Worktree Quality Gate Guard](ADR-031-worktree-quality-gate-guard.md) — extends the template/deployed source parity principle established here (Decision §3, "Build outputs vs source") to the three guard scripts that enforce pre-commit hook execution in epic worktrees. Per ADR-031 Decision §5, each guard script's authoritative source lives in the tracked template tree and `build.py` deploys it to the consumer/worktree location — directly applying the ADR-001 boundary rule. This was motivated by the fresh-worktree silent-skip failure in EPIC-AcPipelineDeployGaps Finding #2, where a guard that only existed in a deployed (untracked) location would itself vanish in a fresh worktree, reproducing the exact class of bug it was designed to prevent.
