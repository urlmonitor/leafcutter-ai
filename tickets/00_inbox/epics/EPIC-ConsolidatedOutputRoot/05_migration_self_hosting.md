---
title: "Migrate self-hosted repo and add migration path for existing installs"
status: todo
components:
  - build_pipeline
created: 2026-05-26
depends_on:
  - 03_redirect_build_phases.md
  - 04_update_config_schema.md
priority: high
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/build-self.sh
  - .claude/skills_config.json
  - leafcutter-ai/scripts/build.py
  - leafcutter-ai/scripts/build_helpers.py
agents:
  architect-review: needed
  python-coder: needed
  test-writer: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  documentation-expert: not_needed
  adr-author: not_needed
---

# 05: Migrate Self-Hosted Repo and Existing Installs

## Goal
In order for the self-hosted leafcutter repo (which dogfoods its own build) to
adopt the new layout, and for existing consumer installs to have a clean
migration path, we need to: (a) update `build-self.sh` and the repo's own
`.claude/skills_config.json`, (b) implement a `--migrate` flag in `build.py`
that detects and reports stale pre-consolidation files, and (c) ensure the
self-hosted repo itself passes a full build after the change.

## Context
The leafcutter repo is self-hosting (see ADR-001). Its current `.claude/`
directory contains compiled agents and skills that are build outputs from
`build.py`. After tickets 03 and 04 land, a fresh `build.py` run will write
to `.leafcutter/` instead. The old files at `.claude/agents/`,
`scripts/commit_guardian/`, etc. are now stale and should be cleaned up.

For consumer projects already using the pre-consolidation layout, we need:
- Detection: `build.py --migrate` scans for files that match the old output
  paths and are no longer written by the new build.
- Report: prints a list of stale files with instructions to delete them.
- No automatic deletion: too risky — user must confirm.

The `build-self.sh` script calls `build.py` to regenerate the self-hosted
repo's agents/skills. It must be updated to pass the new `output_root` (or
rely on the default) and to update `.claude/skills_config.json` with
`output_root: ".leafcutter"`.

## Acceptance Criteria

```gherkin
Given the leafcutter repo's .claude/skills_config.json is updated with
  output_root = ".leafcutter"
When build-self.sh runs
Then build.py succeeds and agents appear at .leafcutter/agents/
And shims exist at .claude/agents/ pointing into .leafcutter/agents/

Given a consumer project that ran the old build.py (stale files at .claude/)
When build.py --migrate runs
Then it prints a report listing each stale file and the suggested rm command
And it exits 0 (report only, no deletion)

Given the migration report has been acted on (stale files deleted)
When build.py runs normally (without --migrate)
Then it succeeds with 0 warnings about stale files
```

## Sign-offs

- [ ] architect-review
- [ ] python-coder
- [ ] test-writer
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### architect-review
- [ ] Review the stale-file detection algorithm — confirm it uses the build
  manifest (written by write_build_manifest) to know which old paths were
  previously written, rather than hard-coding path lists
- [ ] Confirm `build-self.sh` change does not break the CI/CD or any
  developer workflow documented in `leafcutter-ai/CLAUDE.md`

### python-coder
- [ ] Add `--migrate` flag to `build.py` argparse:
  - Reads the previous build manifest (if it exists)
  - Compares old output paths against the new `output_root`-relative paths
  - Prints a migration report: `STALE: <path> — safe to delete`
  - Exits 0; does not delete anything
- [ ] Update `.claude/skills_config.json` to add:
  ```json
  "output_root": ".leafcutter",
  "shim_strategy": "auto"
  ```
- [ ] Update `leafcutter-ai/build-self.sh` if it hard-codes any output paths
  that must now be `.leafcutter/`-relative
- [ ] Ensure `write_build_manifest()` writes the manifest to
  `<output_root>/.leafcutter-build-manifest.json` (not project root)
  so subsequent `--migrate` runs can find it

### test-writer
- [ ] `leafcutter-ai/tests/test_migration.py`:
  - `test_migrate_flag_detects_stale_claude_agents` — given a build manifest
    recording `.claude/agents/` paths, `--migrate` reports them as stale
  - `test_migrate_flag_no_manifest_no_error` — when no prior manifest exists,
    `--migrate` exits 0 with "No prior build manifest found; nothing to migrate"
  - `test_migrate_flag_no_deletions` — after `--migrate` runs, no files are
    deleted from disk

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? The `--migrate` flag is additive and report-only (no deletes).
  Updating `build-self.sh` and `skills_config.json` is reversible by reverting
  those files.
- Self-hosting risk: if `build-self.sh` breaks, the dev team loses the ability
  to regenerate `.claude/agents/` and `.claude/skills/` in this repo. Must be
  tested end-to-end in a local environment before merging.
