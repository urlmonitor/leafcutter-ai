---
title: "Portable project-root resolution — stop hardcoding pyproject.toml in hooks and worktree bootstrap"
status: todo
components:
  - guardrail-engine
  - build_pipeline
created: 2026-07-07
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/hooks/ticket_frontmatter_guard.py
  - templates/hooks/documentation_guard.py
  - scripts/setup_ticket_worktree.py
  - templates/scripts/setup_ticket_worktree.py
  - unit_tests/hooks/test_ticket_frontmatter_guard.py
  - unit_tests/hooks/test_documentation_guard.py
  - unit_tests/test_setup_ticket_worktree.py
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
  adr-author: not_needed
  architecture-diagram-author: not_needed
complexity: standard

---

# Portable project-root resolution — stop hardcoding pyproject.toml

## Actor / Goal

As a consumer project (which may use `requirements-dev.txt`, `setup.py`, or bare
`.git` with no `pyproject.toml`), we need every leafcutter hook and the worktree
bootstrap to resolve the project root and install dependencies **without assuming
`pyproject.toml` exists** — so guard hooks actually run and worktree creation
succeeds in any repo layout.

## Context

Discovered 2026-07-07 while driving EPIC-Phase1ReadyHardening: this very repo has
**no `pyproject.toml`** (it uses `requirements-dev.txt`), which silently disabled
enforcement and broke worktree bootstrap:

1. `ticket_frontmatter_guard.py` and `documentation_guard.py` resolve the project
   root with a private `find_project_root()` that checks **only `pyproject.toml`**.
   When absent, it returns `None` and the hook `sys.exit(0)`s silently — so ticket
   frontmatter validation and the documentation guard have been **dead** in this
   repo (and every consumer without a `pyproject.toml`).
2. By contrast, `check_ac_parent_covered_by.py` already resolves the root robustly
   via `.git` **or** `CLAUDE.md` — proof the correct pattern exists in-tree.
3. `setup_ticket_worktree.py._bootstrap()` unconditionally runs
   `poetry install --no-root`, which errors ("could not find a pyproject.toml")
   and aborts the bootstrap before `build.py` runs.

This is a Phase-1 portability defect ("installs into any project").

## Acceptance Criteria

### AC-1 — Hooks resolve root via portable markers
```gherkin
Given a repo whose root contains a .git directory and/or a CLAUDE.md but NO pyproject.toml,
When ticket_frontmatter_guard.py and documentation_guard.py resolve the project root
  for a file under tickets/ or docs/,
Then find_project_root returns that repo root (matching on .git OR CLAUDE.md OR
  pyproject.toml OR requirements-dev.txt, walking up to 15 levels),
And the hook proceeds to validate rather than silently no-opping.
```

### AC-2 — Frontmatter guard actually fires in a pyproject-less repo
```gherkin
Given a repo with no pyproject.toml,
When a ticket file is written under tickets/ with invalid frontmatter (e.g. missing
  the required 'status' field),
Then ticket_frontmatter_guard emits a {"decision":"block"} with the violation,
And a ticket with valid frontmatter passes silently.
```

### AC-3 — Documentation guard fires in a pyproject-less repo
```gherkin
Given a repo with no pyproject.toml,
When documentation_guard.py runs against a change it is meant to guard,
Then it resolves the root and applies its check rather than silently exiting 0.
```

### AC-4 — Worktree bootstrap detects the dependency manager
```gherkin
Given setup_ticket_worktree.py bootstraps a new worktree,
When the repo root has requirements-dev.txt but no pyproject.toml,
Then bootstrap installs via pip (e.g. pip install -r requirements-dev.txt) instead
  of poetry and does NOT abort,
And when the repo root has a pyproject.toml, poetry install --no-root is still used,
And build.py runs after the dependency install in both cases.
```

### AC-5 — Shared resolver, no duplication
```gherkin
Given the fix,
When resolving project root across ticket_frontmatter_guard.py, documentation_guard.py,
Then both use one shared marker set (not divergent private copies), so a future marker
  addition is a one-line change,
And the marker set is a superset of the existing check_ac_parent_covered_by.py markers
  (.git, CLAUDE.md) plus pyproject.toml and requirements-dev.txt.
```

### AC-6 — No regression for pyproject-based consumers
```gherkin
Given a repo that DOES have a pyproject.toml,
When the hooks resolve root and the worktree bootstraps,
Then behavior is unchanged (pyproject.toml still resolves the root; poetry install still runs).
```

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
