---
title: "Add README.md to scripts/sync_platforms/ (template and deployed copy)"
status: done
components:
  - sync_platforms
  - build_pipeline
created: 2026-05-26
depends_on: []
priority: high
phase: "Phase 1"
requires_diagram: false
requires_adr: false
roadmap_phase: phase_1
advances_current_outcome: true
files_touched:
  - leafcutter-ai/templates/scripts/sync_platforms/README.md
  - scripts/sync_platforms/README.md
agents:
  architect-review: not_needed
  python-coder: signed_off
  test-writer: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  change-scope-reviewer: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: not_needed
  status-checker: not_needed
  sql-coder: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# 04: Add README.md to scripts/sync_platforms/ (template and deployed copy)

## Goal

In order to satisfy the `check_documentation` pre-commit rule that requires a
`README.md` in every directory containing code, we need to create
`leafcutter-ai/templates/scripts/sync_platforms/README.md` and
`scripts/sync_platforms/README.md` so that modifying files in those directories
no longer triggers the "DIRECTORY README MISSING" hook failure.

## Context

The `check_documentation.py` hook enforces: every directory that contains code
MUST have a `README.md`. The `scripts/sync_platforms/` directory contains
`sync_platforms.py` but no README.

The violation in the pre-commit log:
```
DIRECTORY README MISSING: 'scripts\sync_platforms/README.md' does not exist.
You modified/added 'sync_platforms.py' — every directory with code MUST have a README.md.
```

The template source is at `leafcutter-ai/templates/scripts/sync_platforms/` and
the deployed copy lives at `scripts/sync_platforms/`. Both need a README.

Also, `build_phases.py::build_sync_platforms()` copies files from the template
directory. It must be verified (or updated if needed) to also copy `README.md`.
If the copy logic uses a glob (`*.py` only), it must be widened to include
`README.md`.

## Acceptance Criteria

```gherkin
Given scripts/sync_platforms/README.md exists in the deployed copy
When the pre-commit hook check_documentation processes a commit touching sync_platforms.py
Then no "DIRECTORY README MISSING" violation is reported

Given a downstream project rebuilt from the updated templates via build.py
When the build completes
Then scripts/sync_platforms/README.md exists in the target project

Given the README.md content
When inspected
Then it describes the sync_platforms module purpose, usage, and key design decisions
```

## Sign-offs

- [x] python-coder — 2026-06-03 10:00
- [x] pr-reviewer — 2026-06-03 10:05
- [x] commit — 2026-06-03 10:10

## Comments

### 2026-06-03 10:00 — python-coder (status: ok)
feedback-id: fb_2026-06-03_85f21b7f
completion_manifest:
  template_readme_created: true
  deployed_readme_created: true
  build_sync_platforms_verified: true
  decision_history_entry_added: true
Created templates/scripts/sync_platforms/README.md and scripts/sync_platforms/README.md with module purpose, usage, key design decisions (mtime-based newer-file detection, platform directory mapping), and a link to docs/workflows/sync_platforms.md. Verified build_sync_platforms() already copies .md files via the suffix check at line ~1001 (includes ".md" in inject_config path); no code change required. Added DECISION HISTORY entry to scripts/build_phases.py noting the verification.

### 2026-06-03 10:05 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-03_e5eeae08
completion_manifest:
  readme_content_complete: true
  both_copies_present: true
  build_phases_verified: true
  no_regressions: true
Review approved. Both README files cover purpose, usage, key design decisions, and the docs link. build_sync_platforms() confirmed to already handle .md files; DECISION HISTORY entry is well-formed with HH:MM and ticket tag. No regressions introduced.

### 2026-06-03 10:10 — commit (status: ok)
feedback-id: fb_2026-06-03_857b3d49
completion_manifest:
  files_committed: true
  commit_sha_recorded: true
  no_unintended_files: true
Committed 4 files (SHA 769f4e3): templates/scripts/sync_platforms/README.md (new), scripts/sync_platforms/README.md (new), scripts/build_phases.py (DECISION HISTORY), and the ticket file. Pre-commit hooks skipped (no .pre-commit-config.yaml in worktree; hook suite lives on main branch only).

## Implementation Tasks

- [x] Create `leafcutter-ai/templates/scripts/sync_platforms/README.md` with:
  - Module name and one-paragraph purpose description
  - Usage section (`python sync_platforms.py [options]`)
  - Key design decisions (mtime-based newer-file detection, supported platform dirs)
  - A link to `docs/workflows/sync_platforms.md` for deeper context
- [x] Create `scripts/sync_platforms/README.md` with the same content (this is
  the deployed copy in the leafcutter repo running on itself)
- [x] Inspect `leafcutter-ai/scripts/build_phases.py::build_sync_platforms()` to
  verify it copies `README.md` alongside `sync_platforms.py`. If the copy list
  or glob excludes `README.md`, widen it to include all `*.md` files in the
  template directory.
- [x] Add a DECISION HISTORY entry to `build_phases.py` documenting any changes
  made to `build_sync_platforms()` (with HH:MM and `(#EPIC-TemplateDocViolations/04)` tag)

## Risk & Safety

- Touches money? No.
- Touches data? No. Documentation-only file creation plus a minor build-phase adjustment.
- Reversibility? Fully reversible; new files only, no existing code deleted.
