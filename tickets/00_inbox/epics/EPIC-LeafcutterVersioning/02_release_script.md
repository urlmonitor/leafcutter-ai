---
title: "New scripts/release/compute_next_version.py — automated SemVer from changelog entries"
status: todo
components:
  - infrastructure
  - documentation_system
created: 2026-05-19
last_updated: 2026-05-19
depends_on:
  - 01_frontmatter_schema_extension.md
priority: high
phase: "Phase 1"
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter/scripts/release/compute_next_version.py
agents:
  architect-review: needed
  python-coder: needed
  test-writer: needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
  sql-coder: not_needed
---

# 02: New scripts/release/compute_next_version.py — automated SemVer from changelog entries

## Goal

In order to tag releases without human judgement, we need a release script that scans per-file changelog entries since the last `v*` tag, computes the next SemVer bump level, and (optionally) stamps the resulting tag — so that version numbers are derived mechanically from what was actually merged.

## Context

No `scripts/release/` directory exists yet in `leafcutter/scripts/`. This ticket creates both the directory and the script.

The algorithm (locked design):

1. Run `git tag --sort=-version:refname` and find the most recent tag matching `v*` (e.g. `v1.2.3`). If no such tag exists, treat `v0.0.0` as the baseline.
2. Enumerate all files in the `changelogs/` directory (resolved via `_load_changelogs_dir()` from `emit_entry.py`'s config logic) whose YAML frontmatter `date` field is later than the tag's creation date — or equivalently, use `git log <last-v-tag>..HEAD -- changelogs/` to find new entries.
3. Parse the YAML frontmatter of each entry file (stdlib `re` or manual parse — no external yaml dep).
4. Bump logic:
   - Any entry with `breaking: true` → MAJOR bump (returns after first match; no need to scan further for bump level)
   - Any entry with `type: feature` (and no MAJOR trigger found) → MINOR bump
   - Otherwise → PATCH bump
5. Output: prints `vX.Y.Z` to stdout. With `--tag`: runs `git tag vX.Y.Z` and prints the tag.

**Extraction dependency**: this script introduces `git tag` stamping, which only makes practical sense in the upstream `leafcutter` repo. In `bybit-trader`'s embedded copy the script can be authored and tested, but the `--tag` flag should be a no-op (or warn) when the working directory is not the package's own repo. If extraction has not happened by the time this ticket is built, implement without the `--tag` flag and note it as a stub.

Cross-links:
- `leafcutter/scripts/changelog/emit_entry.py` — reuse `_load_changelogs_dir()` and `_resolve_repo_root()` via import or copy-under-test pattern.
- Sub-ticket 01 (`01_frontmatter_schema_extension.md`) — must be merged first so `breaking` field is present in entry files.
- Sub-ticket 03 (`03_ci_workflow.md`) — invokes this script from CI.

`architect-review` is requested because the script's YAML parsing strategy (stdlib only vs. lightweight yaml), the changelog-dir resolution coupling, and the decision around `--tag` in the embedded-vs-extracted context warrant an architectural pass before coding begins.

## Acceptance Criteria

```gherkin
Given a repo with last v-tag v1.2.3 and two new changelog entries (one with breaking=true)
When compute_next_version.py is run
Then it prints "v2.0.0" to stdout

Given a repo with last v-tag v1.2.3 and one new entry with type=feature (no breaking)
When compute_next_version.py is run
Then it prints "v1.3.0" to stdout

Given a repo with last v-tag v1.2.3 and one new entry with type=ticket_completion (no breaking, no feature)
When compute_next_version.py is run
Then it prints "v1.2.4" to stdout

Given a repo with no v-* tags at all
When compute_next_version.py is run
Then it treats the baseline as v0.0.0 and prints the appropriate bump

Given compute_next_version.py is run with --tag
When the computed version does not already exist as a git tag
Then it creates the git tag and prints "Tagged vX.Y.Z"
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

- [ ] Create `leafcutter/scripts/release/` directory with an `__init__.py` (or leave as flat scripts dir — match the pattern in `scripts/changelog/`)
- [ ] Author `compute_next_version.py`:
  - `_find_last_version_tag()` → most recent `v*` tag or `None`
  - `_changelog_entries_since(tag)` → list of Path objects for entries committed after tag
  - `_parse_frontmatter(path)` → dict (stdlib-only; reuse or inline `emit_entry.py`'s approach)
  - `_compute_bump(entries)` → `"major"` | `"minor"` | `"patch"`
  - `_bump_version(version_str, bump)` → next version string
  - `main()` → CLI with `--tag` flag, prints result
- [ ] Ensure stdlib-only (no external deps beyond what Python 3.13 stdlib provides)
- [ ] Unit tests: bump logic for each scenario; `_find_last_version_tag` with mocked git output; `_parse_frontmatter` with breaking/feature/plain entries
- [ ] Add DECISION HISTORY block to the new script

## Risk & Safety

- Touches money? No.
- Touches data? Creates a git tag with `--tag` flag — tags are permanent until explicitly deleted. The non-`--tag` invocation is read-only.
- Reversibility? Git tags can be deleted with `git tag -d vX.Y.Z` if a tag is stamped incorrectly.
