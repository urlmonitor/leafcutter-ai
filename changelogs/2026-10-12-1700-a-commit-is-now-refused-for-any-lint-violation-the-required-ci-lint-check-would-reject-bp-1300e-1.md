---
title: "A commit is now refused for any lint violation the required CI lint check would reject (BP-1300e-1)"
date: "2026-10-12"
time: "17:00"
type: manual
components: 
  - commit_guardian
  - precommit_hooks
summary: "A commit that CI's required Lint (ruff) job would reject is now refused on your machine first, naming the file, line and rule, instead of failing only after the push."
description: "Adds the check-lint-gate commit-time hook (check_lint_gate.py with _lint_*.py helpers and _ruff_locator.py, registered in commit_guardian.json). What is linted and by which rules is declared once in leafcutter-lint.json at the repo root; CI's lint job (name unchanged) and scripts/run_ci_local.py now run the same runner (--mode full), so the local and CI verdicts cannot diverge. Staged files are judged as committed (index content). If ruff is missing, will not start, or its version differs from the requirements-dev.txt pin, the commit is refused with a could-not-check reason and fix, never reported as passed. Adopters use their own ruff config plus a declared scope. Addresses KI-CG-20261009 (required CI ruff had no local pre-commit counterpart); the register entry is not closed here. ACs: BP-1300e-1, BP-1300e-1-i, -ii, -iii, -iv, -v."
commits: []
---

## Entry
