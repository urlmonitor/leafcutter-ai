---
title: "Fix compute_next_version.py: epic_completion bump + tag-commit visibility"
status: todo
components:
  - build_pipeline
created: 2026-05-28
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/release/compute_next_version.py
  - unit_tests/release/test_compute_next_version_bugs.py
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  change-scope-reviewer: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
user_facing_surface: null
---

# Fix compute_next_version.py: epic_completion bump + tag-commit visibility

## Actor / Goal

In order for every epic completion to produce a version bump automatically,
we need to fix two bugs in `_compute_bump()` and `_changelog_entries_since()`
so that `type: epic_completion` entries trigger a minor bump and changelog
entries committed at the same commit as a git tag are not silently dropped.

## Context

Discovered during EPIC-FrontendAgent finalization (2026-05-28).

The changelog entry `changelogs/2026-05-28-0900-epic-frontendagent-complete-pr-19.md`
has `type: epic_completion` and was committed in `31d135c`, which is the exact
commit tagged `v0.1.7`. The result was that `compute_next_version.py` saw zero
relevant entries and produced no `v0.1.8` bump despite a whole new agent being
shipped — a silent correctness failure that will recur with every future epic
completion.

**Bug 1 — `type: epic_completion` not recognized as minor.**
`_compute_bump()` only tests `fm.get("type") == "feature"`. The changelog-agent
writes `type: epic_completion` for completed epics, which semantically ships new
features. The fix: treat `type in {"feature", "epic_completion"}` as a minor bump.

**Bug 2 — Changelog entry in the same commit as the tag is invisible.**
`_changelog_entries_since(tag)` runs `git log {tag}..HEAD --name-only ...`, which
excludes the tag commit itself (three-dot-exclusive range). When the changelog
entry lands in the same commit that gets tagged (e.g. because CI tags immediately
after the changelog commit), the entry is never seen.

The fix: use `git log {tag}^..HEAD` (caret notation) which includes the tag commit
itself. This extends the range by one commit on the left and is safe because
`{tag}^` is the parent of the tag commit; entries from before the tag remain
excluded by the `..HEAD` right boundary.

**Why every future epic completion is affected:** The changelog-agent is
standardized to write `type: epic_completion`. Until this fix lands, no epic
completion will ever trigger a version bump.

## Acceptance Criteria

```gherkin
Given a changelog entry with type: epic_completion and no other entries since the last tag
When compute_next_version.py is run
Then the computed bump level is "minor"
 And the output version is <last_tag_minor + 1>.0

Given a changelog entry committed in the same commit as the last v* tag
When compute_next_version.py is run
Then that entry IS included in the entries list
 And the version is bumped accordingly (not stuck at the current tag)

Given the repo state at commit 31d135c tagged v0.1.7 with epic_completion entry present
When compute_next_version.py is run (after both fixes)
Then the output is v0.1.8

Given a changelog entry with type: feature (existing behavior)
When compute_next_version.py is run
Then the bump level is still "minor" (regression guard)

Given a changelog entry with breaking: true (existing behavior)
When compute_next_version.py is run
Then the bump level is still "major" (regression guard)
```

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### python-coder

- [ ] In `_compute_bump()` (line 172), change the type check from:
  ```python
  if fm.get("type") == "feature":
  ```
  to:
  ```python
  if fm.get("type") in {"feature", "epic_completion"}:
  ```
  This makes any epic completion count as a minor-level bump.

- [ ] In `_changelog_entries_since()` (line 104), change the git log range from:
  ```python
  ["git", "log", f"{tag}..HEAD", "--name-only", "--pretty=format:", "--", str(changelogs_dir)],
  ```
  to:
  ```python
  ["git", "log", f"{tag}^..HEAD", "--name-only", "--pretty=format:", "--", str(changelogs_dir)],
  ```
  The caret notation (`{tag}^..HEAD`) includes the tag commit itself, so a
  changelog entry committed in the same commit as the tag is no longer invisible.

- [ ] Update the `# DECISION HISTORY` block at the bottom of the module:
  - Add an entry dated 2026-05-28 explaining both fixes and their root cause
    (EPIC-FrontendAgent `31d135c` tagged `v0.1.7` with `epic_completion` entry
    in same commit).

### test-writer

- [ ] Create `unit_tests/release/test_compute_next_version_bugs.py` with:

  - `test_epic_completion_triggers_minor_bump`:
    Create a temp changelogs dir with one `.md` file containing
    `type: epic_completion` in frontmatter. Call `_compute_bump([path])`.
    Assert result is `"minor"`.

  - `test_feature_type_still_triggers_minor_bump` (regression guard):
    Same setup with `type: feature`. Assert `_compute_bump()` returns `"minor"`.

  - `test_breaking_still_triggers_major_bump` (regression guard):
    Same setup with `breaking: true`. Assert `_compute_bump()` returns `"major"`.

  - `test_patch_for_unknown_type`:
    Entry with `type: chore`, no `breaking`. Assert `_compute_bump()` returns
    `"patch"`.

  - `test_changelog_entry_at_tag_commit_is_visible`:
    Mock `subprocess.run` so that `git log {tag}^..HEAD` returns a file path
    (simulating the tag-commit-inclusive range), but `git log {tag}..HEAD`
    would return empty (exclusive range). Call `_changelog_entries_since("v0.1.7",
    changelogs_dir, repo_root)` with the patched subprocess. Assert the returned
    list is non-empty (the entry is found).

  - `test_git_log_range_uses_caret_notation`:
    Patch `subprocess.run` and capture the actual command list passed to it.
    Call `_changelog_entries_since("v0.1.7", changelogs_dir, repo_root)`.
    Assert the command contains `"v0.1.7^..HEAD"` not `"v0.1.7..HEAD"`.

## Risk & Safety

- Touches money? No.
- Touches data? No — `compute_next_version.py` is read-only unless `--tag` is
  passed. These fixes affect the scanning and bump logic only.
- Reversibility? Fully reversible. Both changes are one-line edits. If the
  caret-notation change has unexpected side effects on repos with shallow clones
  (where `{tag}^` may not be present), the fallback is to revert to the
  exclusive-range form and apply Bug 2's fix instead via a separate
  `{prev_tag}..{tag}` fallback query.
- Shared contracts? `_compute_bump()` is called by `main()` and by
  `build.py` (via TICKET-20260527-WireVersionIntoBuild). Callers receive a
  string `"major" | "minor" | "patch"` — the interface is unchanged. The set
  of inputs that now produce `"minor"` is strictly expanded (no previously
  `"minor"` case becomes `"patch"`).
- Shallow clone edge case: `{tag}^` requires at least one parent commit to be
  present in the local clone. Standard CI checkouts with `fetch-depth: 0` are
  unaffected. Shallow clones (`fetch-depth: 1`) may not have `{tag}^` and will
  cause `git log` to fail; the existing `except subprocess.CalledProcessError`
  fallback in `_changelog_entries_since()` already handles this by returning all
  entries, which is safe.
