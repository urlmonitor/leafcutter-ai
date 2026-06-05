---
title: "Fix emit_entry _resolve_repo_root() to support git worktrees"
status: inbox
date: 2026-06-05
complexity: simple
components:
  - infrastructure
agents:
  python-coder:
    role: implement
    phase: build
  reviewer:
    role: review
    phase: review
files_touched:
  - scripts/changelog/emit_entry.py
depends_on: []
ac_coverage: 0/3
ac_traceability:
  L0: INF-100
  L1: INF-100b
  l2:
    - INF-100b-1
    - INF-100b-2
    - INF-100b-3
  l3:
    - INF-100b-1-i
    - INF-100b-2-i
  ac_path: docs/acceptance-criteria/infrastructure/INF-100-agent-reliability/INF-100b.yaml
  routing: direct_to_ba
---

## Context

`_resolve_repo_root()` in `scripts/changelog/emit_entry.py` uses `.is_dir()` to
detect whether `parents[2] / ".git"` is the repository root. In a standard git
checkout `.git` is a directory, so `.is_dir()` returns `True` and the function
correctly returns `parents[2]`.

In a git worktree, `.git` is a **file** (containing `gitdir: <path>`), not a
directory. `.is_dir()` returns `False`, so the function falls through to
`parents[3]` — the `worktrees/` parent — which is the wrong root. This caused 8
test failures observed during the finalize-feature run of
`TICKET-20260605-ACFulfillmentGate` in the worktree at
`/home/henzeh/projects/leafcutter/worktrees/acfulfillmentgate`. The same tests
pass cleanly on main.

## Root Cause

```python
# Line 82 — BEFORE (broken in worktrees)
if (p2 / ".git").is_dir():
```

In a worktree, `(p2 / ".git")` is a file. `.is_dir()` → `False` → wrong fallback.

## Fix

Change `.is_dir()` to `.exists()`:

```python
# Line 82 — AFTER (correct for both standard checkout and worktree)
if (p2 / ".git").exists():
```

`.exists()` returns `True` whether `.git` is a file or a directory.

## Acceptance Criteria

- [ ] AC-1: `_resolve_repo_root()` returns `parents[2]` when invoked from a git worktree where `parents[2]/.git` is a file. (INF-100b-1)
- [ ] AC-2: `_resolve_repo_root()` returns `parents[2]` when invoked from a standard checkout where `parents[2]/.git` is a directory. (INF-100b-2)
- [ ] AC-3: All 8 previously-failing worktree emit_entry tests pass after the fix, and no previously-passing test is newly broken. (INF-100b-3)

## AC Coverage

| AC   | Test | Implementation | Validated |
|------|------|----------------|-----------|
| AC-1 |      |                |           |
| AC-2 |      |                |           |
| AC-3 |      |                |           |

## Implementation Notes

- Edit `scripts/changelog/emit_entry.py` line 82 only: `is_dir()` → `exists()`.
- The docstring on `_resolve_repo_root()` should be updated to mention worktree
  support (`.git` may be a file in a worktree).
- Append a DECISION HISTORY entry at the bottom of the file documenting the fix.
- No other files need editing. The template copy (`templates/scripts/changelog/emit_entry.py`)
  does not exist in this repo.

## Sign-offs

- [ ] python-coder
- [ ] reviewer
