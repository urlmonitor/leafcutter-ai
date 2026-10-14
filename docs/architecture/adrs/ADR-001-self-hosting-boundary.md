---
title: 'ADR-001: Self-Hosting Boundary — Config-Driven Path Resolution'
description: Documents the self-hosting boundary for leafcutter-ai — config-driven
  path resolution, build output separation, and user-curated PROJECT_CONTEXT.md preservation
  across upgrades. Amendment 1 (2026-10-13) keeps install copies out of the package
  repository, with build.py refusing an implicit build into it, and retires the
  installed-layout resolver of setup_ticket_worktree.py.
created: '2026-08-13'
last_updated: '2026-10-13'
type: adr
status: active
components:
- build_pipeline
- worktree_manager
related_docs:
- docs/architecture/adrs/ADR-004-consolidated-output-root.md
- docs/architecture/adrs/ADR-018-agent-isolation-topology.md
- docs/architecture/adrs/ADR-031-worktree-quality-gate-guard.md
- docs/architecture/adrs/worktree-maker-amendment-1-2026-09-27.md
related_code:
- scripts/build.py
- build-self.sh
- .gitignore
- templates/scripts/workspace_root.py
- templates/scripts/worktree_layout.py
---
# ADR-001: Self-Hosting Boundary — Config-Driven Path Resolution

## Status

| Field | Value |
|---|---|
| Status | Accepted (2026-05-19). [Amendment 1](#amendment-1--2026-10-13--no-install-inside-the-package-repository-resolver-retired) is Proposed. |
| Date | 2026-05-19 (amended 2026-10-13) |
| Author | leafcutter engineering team; Amendment 1 by adr-author (ticket 14, BO-4300f-2) |
| Supersedes | Nothing. The decision replaced the undocumented status quo (Option A below). |

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

> **Replaced on 2026-10-13 by [Amendment 1](#amendment-1--2026-10-13--no-install-inside-the-package-repository-resolver-retired)
> (AM1.1). No longer binding.** The text below records how `setup_ticket_worktree.py`
> resolved the layout until BO-4300f-2 retired that script. Project resolution now follows
> [ADR-018 Amendment 1, A1.8](worktree-maker-amendment-1-2026-09-27.md#revision-1--2026-09-30--resolution-order-landing-root-and-config-derivation)
> in `templates/scripts/workspace_root.py`. The landing place follows A1.9–A1.10 in
> `templates/scripts/worktree_layout.py`, which replaced the `<consumer_root>/worktrees/<slug>`
> location below on 2026-09-30.

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

## Alternatives

The `--self` flag approach was rejected because it adds a special code path that only leafcutter uses. Config-driven paths are more general and testable.

## Amendment 1 — 2026-10-13 — No install inside the package repository, resolver retired

| Field | Value |
|---|---|
| Amends | The Decision's build-output rule (adds AM1.2 and AM1.3). Replaces the "Installed-Layout Path Resolution (AC BO-1500e-2)" section (AM1.1). |
| Status | Proposed |
| Date | 2026-10-13 |
| Author | adr-author (ticket 14, BO-4300f-2) |
| Driven by | [Ticket 14](../../../tickets/00_inbox/epics/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/14_TICKET-20260928-BO-4300-retire-former-ways.md) ([BO-4300f-2](../../acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300f-2.yaml)) in epic `EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace`; user decision Q6 of 2026-09-28 |
| Supersedes this ADR? | No. Config-driven paths, the source/output boundary and user-owned `PROJECT_CONTEXT.md` files are unchanged. |

### Why this had to change

- **An install copy sat inside the package repository.** On the reference host,
  `leafcutter-ai/.leafcutter/` held a stale install, including a deployed
  `setup_ticket_worktree.py` with `_resolve_installed_layout()`. It got there because
  `scripts/build.py` installs into the current folder when no `--target-dir` is given
  (`main()`: `target_root = ... else Path.cwd()`). A build started at the package root
  therefore installs into the package. The `.leafcutter/` entry in `.gitignore` hides the
  copy at any depth, so nothing reported it. The copy breaks this ADR's boundary
  (everything in `leafcutter-ai/` is source). It is also a place where a former way of
  making a workspace could survive after BO-4300f-2 removes it from the tracked tree.
  [ADR-018 Amendment 1](worktree-maker-amendment-1-2026-09-27.md) A1.8 already stops project
  resolution from reading such a copy (BO-4300b-2-ii), but nothing stopped a build from
  making one.
- **The resolver this ADR named is retired.** The "Installed-Layout Path Resolution"
  section named `_resolve_installed_layout()` in `scripts/setup_ticket_worktree.py` as the
  authority. [ADR-018](ADR-018-agent-isolation-topology.md) Amendment 1 (A1.2) retires that
  script at BO-4300f-2. A1.8 now fixes project resolution, and A1.9 replaced the
  `<consumer_root>/worktrees/<slug>` location on 2026-09-30.
- **A ban on every install in a package checkout would break real callers.** CI runs
  `python scripts/build.py --target-dir .` at the package root. `build-self.sh` passes
  `--target-dir <workspace>`. The maker builds each workspace of the package with an
  explicit `--target-dir` inside the clone (A1.3), because workspaces carry their own
  install (user decision 2 of 2026-09-25). The rule therefore targets the implicit build.

### Decision

**AM1.1 — The installed-layout resolver is retired.** The "Installed-Layout Path
Resolution (AC BO-1500e-2)" section MUST be read as a record only. Project-root resolution
MUST follow ADR-018 Amendment 1 A1.8 in `templates/scripts/workspace_root.py`. The landing
place MUST follow A1.9–A1.10 in `templates/scripts/worktree_layout.py`. After BO-4300f-2,
tracked code in the package MUST NOT define or call `_resolve_installed_layout()`, and
`scripts/setup_ticket_worktree.py` MUST NOT exist. `templates/scripts/setup_ticket_worktree.py`
MUST be deleted or, for at most one release, be a shim that passes every request to the
maker and returns the maker's answer unchanged. The maker and its resolver modules MUST stay
tracked only under `templates/scripts/` (A1.6). This ADR's boundary applies to them
unchanged.

**AM1.2 — A developer's checkout of the package holds no install.** The package repository
a developer works in (`leafcutter-ai/` in the dev layout) MUST NOT hold an install output
root (`<package-root>/.leafcutter/`). A developer's install MUST go to the enclosing
workspace folder (`build-self.sh` passes `--target-dir <workspace>`). A package workspace's
install MUST go inside that workspace, built by the maker with an explicit `--target-dir`
(A1.3). Ticket 14 MUST delete the stale `leafcutter-ai/.leafcutter/` from the developer's
main checkout once, and record before and after listings in its Comments. The folder is
untracked and ignored, so no commit can delete it. That step MUST NOT touch the enclosing
workspace's install (`<workspace>/.leafcutter/`). The `.leafcutter/` entry in `.gitignore`
MUST stay, because package workspaces and CI checkouts hold installs on purpose.

**AM1.3 — `build.py` refuses an implicit build into the package repository.**
`scripts/build.py` MUST exit non-zero when `--target-dir` is absent and the current folder
is the build's own package root or lies inside it. The check MUST run straight after
argument parsing, before config is loaded and before any guard or phase runs, so a refused
run writes nothing. The package root MUST be the folder `main()` already derives from the
build's own location (`Path(__file__).resolve().parent.parent`), and both paths MUST be
resolved before they are compared. The package MUST NOT be recognised by its folder name
(`leafcutter-ai`). The refusal MUST apply in every mode, including `--dry-run` and
`--validate-only`. Its message MUST name this rule (ADR-001 AM1.3) and the `--target-dir`
remedy, and MUST say that a developer's install belongs in the enclosing workspace folder.
An explicit `--target-dir` MUST NOT be refused, whatever folder it names, including
`--target-dir .` at the package root. The check MUST be a small guard helper beside the
existing validation guards in `scripts/build.py`, so the file stays within its file-size
ratchet.

### Consequences

**Positive:**

- The route that made the stale copy is closed. A build started inside the package
  without a target stops before it writes anything, and says how to build correctly.
- After ticket 14, no former workspace script can survive inside the developer's package
  checkout, tracked or untracked.
- CI, `build-self.sh` and the maker keep working unchanged, because each already passes
  `--target-dir`.
- ADR-001 no longer names a retired function as the authority for resolving the project.

**Negative:**

- An explicit `--target-dir .` at the package root is still accepted, because CI needs it.
  A developer who answers the refusal that way recreates the copy. The refusal message is
  the only guard against this, since the user ruled out a check that fails whenever a
  package checkout holds an install.
- Instructions that run `python scripts/build.py` from the package root without a target
  now lead into the refusal. Examples are the how-to guides for hooks, skills, agent
  templates and removing artifacts, and the remedy line printed by
  `templates/scripts/commit_guardian/check_build_drift.py`. Each must name a target.
- The refusal also covers `--dry-run` and `--validate-only`, so a quick validation from the
  package root needs an explicit target. An in-process test that calls `build.main()`
  without `--target-dir` from the package root gets the refusal. Such a test passes without
  exercising the code it names unless it supplies a target.

**Operational:**

- Ticket 14 deletes the stale copy on the reference host only. Another developer host
  holding `<package-root>/.leafcutter/` must delete it by hand, because the refusal only
  prevents a new copy.
- An install inside a package workspace or a CI checkout is expected and does not break
  AM1.2.

### Alternatives

- **Recognise the package by its folder name (`leafcutter-ai`).** Rejected. A clone or a
  renamed checkout of the package has another name, so the guard would miss it. Any
  unrelated folder with that name would be refused. The root derived from `build.py`'s own
  location is right in every layout.
- **Refuse every build into a package checkout, explicit targets included.** Rejected. CI
  builds with `--target-dir .` at the package root, and the maker builds each package
  workspace with an explicit target inside the clone. Both would break.
- **A test or hook that fails whenever a package checkout holds `.leafcutter/`.** Rejected.
  Package workspaces and CI checkouts hold installs on purpose, so the check would fail on
  every legitimate one. The user decided that enforcement is the refusal plus the one-time
  deletion.
- **Drop `.leafcutter/` from `.gitignore` so a stray copy shows in `git status`.**
  Rejected. Every package workspace and CI checkout would then show its whole install as
  untracked, and one `git add -A` would commit an install into the package.
- **Exempt `--dry-run` and `--validate-only` from the refusal.** Rejected. The user's
  decision has no mode exception. An exemption would also rest on each mode's write
  behaviour staying correct, so a regression in one of them would reopen the route that
  made the stale copy. Naming a target costs one flag.
- **Keep `_resolve_installed_layout()` as a second resolver beside the maker.** Rejected.
  The older resolvers already disagreed on which project a folder belongs to (F3, F11).
  ADR-018 Amendment 1 A1.5 and A1.8 allow exactly one.

## See Also

- [ADR-031 — Worktree Quality Gate Guard](ADR-031-worktree-quality-gate-guard.md) — extends the template/deployed source parity principle established here (Decision §3, "Build outputs vs source") to the three guard scripts that enforce pre-commit hook execution in epic worktrees. Per ADR-031 Decision §5, each guard script's authoritative source lives in the tracked template tree and `build.py` deploys it to the consumer/worktree location — directly applying the ADR-001 boundary rule. This was motivated by the fresh-worktree silent-skip failure in EPIC-AcPipelineDeployGaps Finding #2, where a guard that only existed in a deployed (untracked) location would itself vanish in a fresh worktree, reproducing the exact class of bug it was designed to prevent.
