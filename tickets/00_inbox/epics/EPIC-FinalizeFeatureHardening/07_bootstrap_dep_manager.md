---
title: "Detect dependency manager and make worktree bootstrap non-fatal"
status: todo
components:
  - worktree_manager
created: 2026-06-24
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/setup_ticket_worktree.py
  - templates/scripts/setup_ticket_worktree.py
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
---

# 07: Detect dependency manager and make worktree bootstrap non-fatal

## Actor / Goal

In order to stop worktree creation from aborting on repos that don't use poetry,
we need `setup_ticket_worktree.py` to detect the dependency manager (poetry vs
pip) and to treat a dependency-install failure as a non-fatal warning rather than
crashing before `build.py` runs.

## Context

`_bootstrap()` (≈ lines 215-230) unconditionally runs
`poetry install --no-root` with `check=True`. This repo has **no `pyproject.toml`**
— it uses `requirements-dev.txt` with system Python. The call always fails here
(this session reproduced it:
`Poetry could not find a pyproject.toml file ... returned non-zero exit status 1`),
and because the call is placed AFTER the worktree is created and is `check=True`,
the script aborts before the critical `build.py` step that materialises
`.leafcutter/`, leaving a half-bootstrapped worktree. It is also a portability
defect: the same code ships in `templates/scripts/`, so any pip-based adopter hits
it too.

Other steps in the same file (`build.py`, pre-commit shim install) already use the
catch-warn-continue pattern; the dependency-install step should match.

## Acceptance Criteria

- [ ] AC-1: `_bootstrap()` selects the dependency command by detecting the repo's
  manifest: `pyproject.toml` → `poetry install --no-root`; else
  `requirements-dev.txt` (or `requirements.txt`) → `<python> -m pip install -r <file>`;
  else → no dependency step.
- [ ] AC-2: A dependency-install failure (missing tool, install error) is caught,
  logged as a WARNING to stderr, and does NOT abort bootstrap — the worktree
  remains created and `build.py` still runs.
- [ ] AC-3: On this repo (requirements-dev.txt, no pyproject.toml),
  `setup_ticket_worktree.py setup-ticket <ticket>` completes successfully and emits
  the worktree JSON, without the poetry crash.
- [ ] AC-4: The same fix is mirrored into `templates/scripts/setup_ticket_worktree.py`
  so consumer installs benefit.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |

## Comments

## Implementation Tasks
- [ ] Add manifest detection + branch the install command.
- [ ] Wrap the install in try/except → WARNING + continue (per Error Handling Policy).
- [ ] Mirror to the templates/ copy.
- [ ] Tests: poetry-repo path, pip-repo path, no-manifest path, install-failure-non-fatal path.

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? High.
