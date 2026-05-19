---
title: "GitHub Actions CI workflow — invoke release script on push-to-main"
status: todo
components:
  - infrastructure
created: 2026-05-19
last_updated: 2026-05-19
depends_on:
  - 02_release_script.md
priority: high
phase: "Phase 1"
requires_diagram: false
requires_adr: false
files_touched:
  - .github/workflows/release.yml
agents:
  architect-review: not_needed
  python-coder: needed
  test-writer: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
  sql-coder: not_needed
---

# 03: GitHub Actions CI workflow — invoke release script on push-to-main

## Goal

In order to release `leafcutter` without manual tagging, we need a GitHub Actions workflow that triggers on push-to-main, runs `compute_next_version.py`, and stamps the computed `vX.Y.Z` tag — so that every merge to main produces a versioned release automatically.

## Context

No CI currently exists for `leafcutter` because the package has not been extracted to its own repo yet. This ticket is a **stub** that becomes active when extraction completes:

- The `.github/workflows/release.yml` file path is relative to the **upstream extracted repo root** (`github.com/urlmonitor/leafcutter` or equivalent), not `bybit-trader`.
- The file may be authored in `bybit-trader`'s embedded copy as `leafcutter/.github/workflows/release.yml` to track it under version control during the pre-extraction period, and then moved to the repo root at extraction time.

**Extraction dependency**: if extraction has not happened when this ticket is scheduled, the implementer should note the stub state in the PR description and leave the file at the embedded path. The CI gate will go live automatically when the extracted repo is created and the workflow file is at the correct repo root.

Cross-links:
- Sub-ticket 02 (`02_release_script.md`) — the workflow invokes `compute_next_version.py --tag`.
- Sub-ticket 05 (`05_schema_diff_ci_gate.md`, Phase 2) — a second CI workflow that may be added to the same repo later.

## Acceptance Criteria

```gherkin
Given a push to main in the leafcutter upstream repo
When there are new changelog entries since the last v* tag
Then the GitHub Actions workflow runs compute_next_version.py --tag and a new vX.Y.Z tag appears in the repo

Given the computed version already exists as a git tag
When the workflow runs
Then it exits 0 with a "version unchanged" or "already tagged" message (no duplicate tag error)

Given the workflow runs and compute_next_version.py exits non-zero
When the workflow finishes
Then the GitHub Actions job is marked failed (no silent swallow of errors)
```

## Sign-offs

- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] Author `.github/workflows/release.yml` (or `leafcutter/.github/workflows/release.yml` for the pre-extraction period):
  - Trigger: `on: push: branches: [main]`
  - Steps:
    1. `actions/checkout@v4` with `fetch-depth: 0` (full history required for `git tag` scanning)
    2. `actions/setup-python@v5` with Python 3.13
    3. Run `python leafcutter/scripts/release/compute_next_version.py` (read-only pass) and capture output
    4. Check if the tag already exists (`git rev-parse <tag> >/dev/null 2>&1`); skip tagging if so
    5. Run with `--tag` only when the tag does not already exist
    6. Optionally: push the tag to origin (`git push origin <tag>`)
- [ ] Add idempotency guard: if the tag already exists, print a message and exit 0 (do not fail the workflow)
- [ ] Document the extraction-stub state in a comment at the top of the workflow file
- [ ] No unit tests required for the YAML workflow itself; the release script tests (sub-ticket 02) cover the logic

## Risk & Safety

- Touches money? No.
- Touches data? Pushes a git tag to the upstream repo. Tags are permanent until deleted. An incorrect tag would require `git push origin :refs/tags/vX.Y.Z` to delete.
- Reversibility? Tags can be deleted; a follow-up tag can be pushed. The idempotency guard prevents double-tagging on re-runs.
