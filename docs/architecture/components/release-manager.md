---
title: "Release Manager — Semantic Version Lifecycle"
description: "Semantic version computation and schema diff checking system for managing structured releases of the leafcutter-ai package."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-06-08
components:
  - release_manager
---

# Release Manager

## Overview

The Release Manager handles semantic versioning and schema diff analysis for leafcutter-ai package releases. It computes the next version based on conventional commit messages and checks for breaking schema changes.

## Responsibilities

- Compute the next semantic version from commit history
- Detect breaking schema changes via `check_schema_diff.py`
- Support release tagging and changelog generation

## Entry Points

- `scripts/release/compute_next_version.py` — semantic version computation
- `scripts/release/check_schema_diff.py` — schema diff analysis

## Integration

The release manager is invoked during the `finalize-feature` workflow to produce release artifacts. It runs after all epic tickets are complete and the PR is merged.
