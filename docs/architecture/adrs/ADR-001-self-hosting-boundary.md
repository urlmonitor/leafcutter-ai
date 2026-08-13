---
description: Documents the self-hosting boundary for leafcutter-ai — config-driven
  path resolution, build output separation, and user-curated PROJECT_CONTEXT.md preservation
  across upgrades.
created: '2026-08-13'
last_updated: '2026-08-13'
type: tutorial
status: active
---
# ADR-001: Self-Hosting Boundary — Config-Driven Path Resolution

## Status

Accepted (2026-05-19)

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

## Alternatives

The `--self` flag approach was rejected because it adds a special code path that only leafcutter uses. Config-driven paths are more general and testable.

## See Also

- [ADR-031 — Worktree Quality Gate Guard](ADR-031-worktree-quality-gate-guard.md) — extends the template/deployed source parity principle established here (Decision §3, "Build outputs vs source") to the three guard scripts that enforce pre-commit hook execution in epic worktrees. Per ADR-031 Decision §5, each guard script's authoritative source lives in the tracked template tree and `build.py` deploys it to the consumer/worktree location — directly applying the ADR-001 boundary rule. This was motivated by the fresh-worktree silent-skip failure in EPIC-AcPipelineDeployGaps Finding #2, where a guard that only existed in a deployed (untracked) location would itself vanish in a fresh worktree, reproducing the exact class of bug it was designed to prevent.
