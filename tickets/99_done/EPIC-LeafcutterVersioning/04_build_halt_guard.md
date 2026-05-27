---
title: "build.py halt-guard: block on breaking changes since consumer's pinned SHA"
status: todo
components:
  - infrastructure
  - documentation_system
created: 2026-05-19
last_updated: 2026-05-19
depends_on:
  - 01_frontmatter_schema_extension.md
priority: medium
phase: "Phase 2"
requires_diagram: false
requires_adr: true
files_touched:
  - leafcutter/scripts/build.py
  - leafcutter/scripts/build_phases.py
agents:
  architect-review: needed
  python-coder: needed
  test-writer: needed
  test-runner: not_needed
  documentation-expert: not_needed
  adr-author: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
  sql-coder: not_needed
---

# 04: build.py halt-guard — block on breaking changes since consumer's pinned SHA

## Goal

In order to prevent consumers from silently pulling in breaking `leafcutter` changes, we need `build.py` to detect `breaking: true` changelog entries that arrived after the consumer's last successful build and halt with a structured migration notice — so that breaking upgrades are always explicit, never invisible.

## Context

This is a **Phase 2** ticket. It depends on sub-ticket 01 (`01_frontmatter_schema_extension.md`) because the halt-guard reads the `breaking` field from entries produced by the extended `emit_entry.py`.

The mechanism (locked design):
- `build.py` writes a `.leafcutter.lock` file to the consumer's project root after each successful build. The lock file records the package git SHA at build time.
- On the next `build.py` run, it reads the lock file, scans `changelogs/` for entries committed after the pinned SHA, and checks for `breaking: true`.
- If any breaking entry is found: print a structured migration notice (title, date, `migration_steps` list) and exit non-zero — **do not write any artifacts**.
- `--force` flag overrides the halt and proceeds with the build (with a visible warning logged). This is the escape hatch for operators who have read the migration steps and are ready to proceed.

Design concerns for architect-review:
1. **Lock file placement and format** — should `.leafcutter.lock` be JSON (version, sha, date) or plain text (sha only)? JSON is preferred for extensibility.
2. **SHA resolution in embedded mode** — when the package is embedded (not extracted), "package SHA" is a subdirectory path inside `bybit-trader`'s repo. Use `git log -1 --format=%H -- leafcutter/` to get the last commit that touched the package tree.
3. **`--force` UX** — the flag must not become the default path. Recommend requiring `--force-breaking` (longer flag) so it is never accidentally passed.
4. **Interaction with `--dry-run`** — when `--dry-run` is active, the halt-guard should print the migration notice but NOT halt (so CI can surface the warning without blocking).

Cross-links:
- `leafcutter/scripts/build.py` — where the halt-guard check is wired in (early in `main()`, before any phase dispatch).
- `leafcutter/scripts/build_phases.py` — may need a helper for lock-file read/write.
- Sub-ticket 01 (`01_frontmatter_schema_extension.md`) — source of `breaking` field in entries.
- Sub-ticket 05 (`05_schema_diff_ci_gate.md`) — complementary Phase 2 gate; the two work together to close the silent-omission gap.

An ADR is requested because the halt-guard introduces a new consumer-visible behaviour contract (lock file, `--force-breaking` escape hatch, dry-run semantics) that should be documented for adopters.

## Acceptance Criteria

```gherkin
Given a consumer project with a .leafcutter.lock at SHA-A
When build.py is run and there is a changelog entry with breaking=true committed after SHA-A
Then build.py prints the migration notice (title + migration_steps) and exits non-zero without writing artifacts

Given the same scenario with --force-breaking passed
When build.py runs
Then it prints a WARNING but proceeds and writes artifacts normally

Given a consumer project with no .leafcutter.lock
When build.py is run
Then it proceeds normally (first-run: no baseline to compare against) and writes the lock file on success

Given build.py is run with --dry-run and there is a breaking entry since the pinned SHA
When build.py runs
Then it prints the migration notice but exits 0 (dry-run never blocks)
```

## Sign-offs

- [ ] architect-review
- [ ] adr-author
- [ ] python-coder
- [ ] test-writer
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] Author an ADR (title TBD by adr-author) covering: lock file format, SHA resolution strategy, `--force-breaking` UX, dry-run interaction
- [ ] Add `_write_lock_file(repo_root, sha)` and `_read_lock_file(repo_root)` helpers (in `build_phases.py` or a new `build_lock.py`)
- [ ] Add `_find_breaking_entries_since(sha, changelogs_dir)` — scans entries, parses frontmatter, filters `breaking: true`
- [ ] Wire halt-guard into `build.py` `main()`: read lock → find breaking entries → halt or warn → proceed → write lock
- [ ] Add `--force-breaking` CLI flag to `build.py` argument parser
- [ ] Ensure `--dry-run` path: print notice but exit 0
- [ ] Unit tests: halt on breaking entry; `--force-breaking` proceeds; no lock file → first-run succeeds; `--dry-run` exits 0
- [ ] Update `build.py` DECISION HISTORY block

## Risk & Safety

- Touches money? No.
- Touches data? Writes `.leafcutter.lock` to consumer project root. This is a new file in consuming repos — may need to be `.gitignore`d or committed depending on team convention.
- Reversibility? Delete `.leafcutter.lock` to reset to first-run state. The `--force-breaking` flag is the runtime escape hatch.
