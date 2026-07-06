#!/usr/bin/env python3
"""
MODULE: precommit_canary
GOAL: Pre-commit canary hook — emits PRECOMMIT_CANARY_OK and exits 0.
BUSINESS CONTEXT: Part of the WorktreeQualityGateGuard system. This script is
    registered as a manual-stage-only pre-commit hook (stages: [manual]). When
    invoked by verify_precommit_active.py check D, its stdout is inspected for
    the PRECOMMIT_CANARY_OK sentinel to confirm pre-commit hooks can fire in
    the current worktree environment.
ARCHITECTURE: Self-contained one-liner; no imports required. The sentinel
    token PRECOMMIT_CANARY_OK is the sole observable output. Registered in
    commit_guardian.json hooks_manifest with always_run: true, pass_filenames:
    false, stages: [manual] so it only runs on explicit --hook-stage manual
    invocations and never fires automatically on git commit.

====================================================================
DECISION HISTORY
====================================================================
- 2026-07-06 [EPIC-WorktreeQualityGateGuard/02]: Initial implementation.
  Canary is intentionally minimal — any logic here would mask worktree
  environment failures, defeating the probe's purpose.
====================================================================
"""

print("PRECOMMIT_CANARY_OK")
