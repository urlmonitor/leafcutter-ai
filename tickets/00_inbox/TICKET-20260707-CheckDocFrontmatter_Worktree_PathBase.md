---
title: "check-doc-frontmatter resolves project root to the workspace parent in worktrees (false read failure)"
status: todo
components:
  - commit-guardian
created: 2026-07-07
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/scripts/commit_guardian/hooks/check_doc_frontmatter.py
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
ac_coverage: 0/1
---

# check-doc-frontmatter resolves project root to the workspace parent in worktrees (false read failure)

## Goal
So that committing `docs/**` or `tickets/**` files from an epic/feature worktree does
not spuriously fail, make `check-doc-frontmatter` resolve staged file paths against
the git worktree root (`git rev-parse --show-toplevel`) rather than a `__file__`- or
cwd-derived path that points at the workspace parent through the `.leafcutter` symlink.

## Context
Recurred on every doc/ticket-touching commit during EPIC-PhantomDoneFilesTouched
(commits 08b225cf, fbf85327, 757f03e6, ee816385 — PR #209, 2026-07-07). The hook
errored with e.g.
`Could not read file: [Errno 2] No such file or directory:
/home/henzeh/projects/leafcutter/docs/architecture/agent_delivery_workflows.md`
— resolving the staged path against the WORKSPACE PARENT
(`/home/henzeh/projects/leafcutter/`) instead of the worktree root
(`/home/henzeh/projects/leafcutter/EPIC-PhantomDoneFilesTouched/`). The file exists
and is valid at the worktree path; the hook fails at the `open()` step, not on any
real frontmatter violation. Each commit had to use `SKIP=check-doc-frontmatter`.

Root cause: the hook derives its project root from `__file__` of the resolved
`.leafcutter` symlink target (under the workspace parent) or from cwd, not from the
git worktree top-level. Same class as the check-secrets scripts_dir worktree issue.
See user-memory project_worktree_docfrontmatter_pathbase and
project_worktree_checkdocfrontmatter_falsefail.

## Acceptance Criteria
- [ ] AC-1 (worktree-correct path base): when invoked as a pre-commit hook inside a
  linked git worktree with staged `docs/**`/`tickets/**` files, the hook reads each
  staged file from the worktree root (via `git rev-parse --show-toplevel`) and
  validates frontmatter without a false `Could not read file` error. A staged, valid
  doc/ticket in a worktree passes without needing `SKIP=`; a genuinely
  missing-frontmatter file still fails as before (no regression to the real check).

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |

## Comments

<!-- Append-only log — leave blank when authoring. -->

## Implementation Tasks
- [ ] Replace the `__file__`/cwd-derived project root in `check_doc_frontmatter.py`
  with `git rev-parse --show-toplevel` (fail open / clear message if git is absent).
- [ ] Audit sibling commit_guardian hooks for the same path-base assumption.
- [ ] Add a test that runs the hook from a linked-worktree fixture and asserts a valid
  staged doc passes and a frontmatter-less doc still fails.

## Risk & Safety
- Touches money? No.
- Touches data? No — read-only frontmatter validation.
- Reversibility? Fully reversible.
