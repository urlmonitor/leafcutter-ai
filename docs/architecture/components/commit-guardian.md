---
title: "Commit Guardian — Pre-Commit Hook System"
description: "Pre-commit hook orchestration system that enforces code quality, ADR coverage, component integrity, and structural rules before every commit lands."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-08-18
components:
  - commit_guardian
related_docs:
  - docs/architecture/adrs/ADR-034-whole-collection-uniqueness-pass.md
  - docs/architecture/adrs/ADR-029-adr-number-collision-prevention.md
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
  - docs/architecture/diagrams/c3-006-whole-collection-uniqueness-pass.md
related_code:
  - templates/scripts/commit_guardian/check_identifier_uniqueness.py
  - templates/scripts/commit_guardian/check_adr_collision.py
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

## Whole-Collection Uniqueness Pass (goal `GE-122`)

Most hooks above are **per-file**: they read the staged diff and judge each record in
isolation, so they cannot see that a sibling file — never itself staged — already claims
the same number. `check_identifier_uniqueness.py` (`run_uniqueness_pass`) is a different
unit of inspection: a single importable module that walks the **whole on-disk collection**
(never diff-scoped) across four numbered namespaces — acceptance-criterion identifiers,
decision-record integers, architecture-diagram level-and-sequence ids, and work-item
identifiers — and returns one fixed `UniquenessVerdict` object: one finding per contested
number (never one per claimant file), every claimant path, and a mandatory per-namespace
`inspected_count` that distinguishes a real pass from a pass over nothing. Six sibling
ACs under goal `GE-122` consume that verdict object directly rather than a CLI's printed
text. See the [data-flow diagram](../diagrams/c3-006-whole-collection-uniqueness-pass.md)
and the governing [ADR-034](../adrs/ADR-034-whole-collection-uniqueness-pass.md).

The decision-record namespace of that pass adopts `check_adr_collision.py`'s existing
staged-vs-`origin/main`-vs-in-flight-branch comparison rather than reimplementing it. That
script is now registered as the `check-decision-number-uniqueness` hook in
`hooks_manifest.hooks` — as of 2026-08-18 it is the first time it has ever executed; see
[ADR-029 Amendment 1](../adrs/ADR-029-adr-number-collision-prevention.md#amendment-1--2026-08-18--fail-open-is-narrowed-to-the-guards-own-defects)
for the fail-open narrowing this registration depended on. `check_identifier_uniqueness.py`
itself is not yet registered in any hook manifest — wiring it into the three
commit-lifecycle stages is `GE-122d-1`'s scope, not this pass's.
