---
title: "Fix user-surface-smoker feedback submission failing silently in worktrees"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/agents/user-surface-smoker.md
  - scripts/feedback/submit_feedback.py
agents:
  architect-review: needed
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
---

# Fix user-surface-smoker Feedback Sink in Worktrees

## Actor / Goal

As the user-surface-smoker agent running inside an epic worktree, I need my
feedback submissions to actually reach the feedback.jsonl sink, so that
retrospective tooling can aggregate smoke-test results across tickets.

## Context

During EPIC-MoveOnMainOnly, tickets 04 and 05 both ran user-surface-smoker.
Both smoke tests PASSED (assertions matched), but both recorded
`feedback-id: (submit-failed)` in their comment blocks. The completion
manifests are present in ticket comments but invisible to aggregate.py.

Root cause hypothesis: the feedback sink path is resolved relative to the
repo root, but in a worktree the `debugging/logs/` directory may not exist
(worktrees share .git but not untracked directories). The sink probe in the
Pre-Drive Checklist only checks the main repo, not the worktree.

## Acceptance Criteria

```gherkin
Given the user-surface-smoker agent running inside an epic worktree
When it submits feedback after a successful smoke test
Then the feedback entry appears in the worktree's debugging/logs/feedback.jsonl
 Or the feedback entry appears in the main repo's debugging/logs/feedback.jsonl
 And the feedback-id in the comment block is a valid UUID (not "submit-failed")

Given a worktree that does not have debugging/logs/ directory
When submit_feedback.py attempts to write
Then it creates the directory (mkdir -p) before writing
 And it does not silently swallow the error
```

## Investigation Steps

1. Check how `submit_feedback.py` resolves the sink path (relative to CWD? git root?)
2. Reproduce in a worktree: does `debugging/logs/` exist there?
3. If not, either: (a) ensure worktree setup creates it, or (b) resolve path to main repo
4. Add a test that exercises feedback submission from a non-standard CWD
