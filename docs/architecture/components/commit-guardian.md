---
title: "Commit Guardian — Pre-Commit Hook System"
description: "Pre-commit hook orchestration system that enforces code quality, ADR coverage, component integrity, and structural rules before every commit lands."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-06-08
components:
  - commit_guardian
---

# Commit Guardian

## Overview

The Commit Guardian is the pre-commit enforcement layer for the leafcutter-ai package. It orchestrates a suite of independent hook scripts that run during `git commit`, blocking commits that violate structural, documentation, or code quality rules.

## Responsibilities

- Enforce component registry integrity (`check_components_integrity.py`)
- Verify ADR coverage for structural changes (`check_adr_coverage.py`)
- Validate documentation frontmatter and description fields
- Guard against contract shrinking in test suites (`check_contract_shrinking.py`)
- Enforce exception handling boundaries in Python code
- Check ticket sign-off parity between frontmatter and Sign-offs sections

## Entry Points

- `scripts/commit_guardian/run_hook.py` — dispatcher invoked by pre-commit
- `.pre-commit-config.yaml` — hook registration file
- `scripts/commit_guardian/commit_guardian.json` — configuration

## Design Principles

Each hook is an independent script that exits 0 (pass) or 1 (block). Hooks are fail-fast by default (`fail_fast: true` in `.pre-commit-config.yaml`). Advisory hooks always exit 0 regardless of findings.
