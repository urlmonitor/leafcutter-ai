---
title: "Bootstrap .pre-commit-config.yaml in epic/feature worktrees so package hooks run"
status: todo
components:
  - build_pipeline
created: 2026-06-17
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
origin_agent: BrainCandy
files_touched:
  - templates/skills/feature/SKILL.md
  - templates/agents/worktree-agent.md
agents:
  architect-review: needed
  llm-expert: needed
  python-coder: needed
  test-writer: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Bootstrap .pre-commit-config.yaml in Worktrees

## Goal

In order for the package's pre-commit hooks (complexity, glossary coverage,
decision-history, doc frontmatter, AC schema, ticket sign-off parity, secrets,
exception-handling, feedback-id, description-field, etc.) to actually run on
commits made inside an epic or feature worktree, the worktree bootstrap step
must establish a working `.pre-commit-config.yaml` (and the `.leafcutter/`
artifacts it points at) so commits are NOT made with the hooks silently
disabled.

## Context

Discovered during the EPIC-AcPipelineDeployGaps drive (2026-06-17). Every
commit on the epic branch had to be made with `PRE_COMMIT_ALLOW_NO_CONFIG=1`
because the worktree had no `.pre-commit-config.yaml` at its root. This meant
**none** of the package pre-commit hooks ran on any commit for the entire
drive.

**Root cause:**
- `.pre-commit-config.yaml` at the repo root is NOT a normal tracked file — it
  is a **symlink** created by the build's `install_shims()`
  (`scripts/build_helpers.py`), pointing at `.leafcutter/pre-commit-config.yaml`
  (a build output). The hook `entry:` lines reference scripts via
  `.leafcutter/scripts/commit_guardian/...`.
- `worktree-agent` (via the `feature` skill "Epic Workflow"/"Feature Workflow")
  creates worktrees from `origin/main`. The bootstrap step copies `.env` and
  `.mcp.json` and runs `poetry install --no-root`, but never runs the build's
  shim-install, so the worktree has neither the `.pre-commit-config.yaml`
  symlink nor a populated `.leafcutter/` to point at.
- Result: `git commit` inside the worktree finds no config and either errors
  ("No .pre-commit-config.yaml file was found") or is bypassed with
  `PRE_COMMIT_ALLOW_NO_CONFIG=1` — silently disabling all hooks.

**Impact:** a post-epic diagnostic run of the 28 wired hooks against the
EPIC-AcPipelineDeployGaps changes found 14 findings (7 `check-feedback-id`,
7 `check-description-field`) that **would have blocked commits** had the hooks
run. They were instead caught only by a manual diagnostic pass and fixed after
the fact (commit `25adec3`). No secrets/correctness violations slipped through
this time, but the gap means any future worktree drive ships unguarded.

**Source locations:**
- Bootstrap recipe: `templates/skills/feature/SKILL.md` (Epic + Feature
  workflow bootstrap, ~lines 81-90 — `.env` copy, `.mcp.json` copy,
  `poetry install`, settings verify).
- `templates/agents/worktree-agent.md` — the agent that runs the bootstrap.
- `install_shims()` / pre-commit install: `scripts/build_helpers.py`,
  `scripts/build_precommit.py` (how the main repo's config + `.leafcutter/`
  are produced).

## Acceptance Criteria

### AC-1: Worktree bootstrap establishes a working pre-commit config
- **Given** `worktree-agent` creates a new epic or feature worktree from `origin/main`
- **When** the bootstrap step completes
- **Then** the worktree root has a resolvable `.pre-commit-config.yaml` whose
  hook `entry:` script paths resolve to existing files reachable from the
  worktree (e.g. a populated `.leafcutter/scripts/commit_guardian/`), such that
  `pre-commit run` executes the package hooks rather than reporting
  "No .pre-commit-config.yaml file was found".

### AC-2: A real commit inside the worktree runs the hooks (no silent bypass)
- **Given** a bootstrapped worktree with a staged change that violates a wired
  hook (e.g. a doc missing `description:`)
- **When** a commit is attempted WITHOUT `PRE_COMMIT_ALLOW_NO_CONFIG=1`
- **Then** the offending hook fires and blocks the commit, proving the hooks are
  active in the worktree.

### AC-3: Bootstrap is idempotent and does not corrupt the main repo
- **Given** the worktree bootstrap runs (or re-runs on an existing worktree)
- **When** it establishes the pre-commit config
- **Then** it does not modify or break the main repo's `.pre-commit-config.yaml`
  / `.leafcutter/`, and re-running is safe (no duplicate or dangling symlinks).

### AC-4: The PRE_COMMIT_ALLOW_NO_CONFIG=1 workaround is no longer required
- **Given** a bootstrapped worktree
- **When** the `commit` phase agent commits
- **Then** it succeeds without needing `PRE_COMMIT_ALLOW_NO_CONFIG=1`; the
  commit-agent template / bootstrap docs are updated to drop the workaround as
  the default path (it may remain a documented fallback).

### AC-5: Bootstrap failure is surfaced, not silently skipped
- **Given** the bootstrap cannot establish a working pre-commit config (e.g.
  `.leafcutter/` not buildable in the worktree)
- **When** the worktree is created
- **Then** `worktree-agent` reports the failure clearly so the drive does not
  proceed believing hooks are active when they are not.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks
- [ ] architect-review: decide the mechanism — does the worktree bootstrap run
  the build's shim-install (`build.py`/`install_shims`) against the worktree, or
  symlink/copy the main repo's `.pre-commit-config.yaml` + `.leafcutter/` into
  the worktree, or run `build_precommit.py` directly? Account for ADR-001
  self-hosting and ADR-004 consolidated output root. Record the decision.
- [ ] Update `templates/skills/feature/SKILL.md` bootstrap recipe to establish
  the pre-commit config as part of worktree setup.
- [ ] Update `templates/agents/worktree-agent.md` to reflect the new bootstrap
  contract and the failure-surfacing behavior (AC-5).
- [ ] If a script change is needed (e.g. a `--worktree` mode or a bootstrap
  helper), implement it in the relevant build script.
- [ ] test-writer: a test that a freshly-bootstrapped worktree has working hooks
  (AC-1/AC-2) and that bootstrap is idempotent (AC-3).
- [ ] Drop the `PRE_COMMIT_ALLOW_NO_CONFIG=1` default from the commit path docs
  (AC-4).

## Risk & Safety

- **Touches money?** No.
- **Touches data?** No — build/worktree tooling and prompt templates only.
- **Reversibility?** High — bootstrap-recipe and template changes; revert
  restores current behavior.
- **Blast radius?** Affects every future worktree drive. Must be careful NOT to
  let the worktree's pre-commit setup mutate or point back into the main repo in
  a way that causes cross-worktree interference (AC-3).
