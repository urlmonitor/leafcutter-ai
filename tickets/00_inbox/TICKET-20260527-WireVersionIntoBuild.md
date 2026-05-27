---
title: "Wire compute_next_version.py into build.py to auto-apply SemVer during builds"
status: todo
components:
  - build_pipeline
created: 2026-05-27
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/build.py
  - scripts/release/compute_next_version.py
agents:
  architect-review: needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
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

# Wire compute_next_version.py into build.py to auto-apply SemVer during builds

## Actor / Goal

In order to eliminate the manual version-computation step during releases, we
need `build.py` to automatically call `compute_next_version.py` and apply the
computed SemVer so that every build run surfaces the current version without
human intervention.

## Context

EPIC-LeafcutterVersioning (PR #10) introduced
`scripts/release/compute_next_version.py`, which scans `changelogs/` entries
since the last `v*` git tag and deterministically derives the next SemVer
version (currently outputs `v0.1.4`). It is fully standalone (stdlib-only) and
exposes a `main()` function suitable for programmatic import.

`scripts/build.py` (the leafcutter build orchestrator) runs all build phases
and writes a build manifest, but does NOT call `compute_next_version.py`. The
version computation is a separate manual step — an operator must run it
independently before or after a build.

The goal is to close this gap: `build.py` should call `compute_next_version.py`
at the start of each build run, apply the computed version, and surface it in
at least one durable output so that downstream tooling and consumers can
interrogate it without running the version script themselves.

### Acceptable application strategies (implementer's choice, document decision)

1. **Write a `VERSION` file** at `<target_root>/VERSION` containing the bare
   version string (e.g. `v0.1.4`).
2. **Embed in the build manifest** — add a `"version"` key to the JSON written
   by `write_build_manifest()` in `build_helpers.py`.
3. **Print in build output** — emit `Build version: v0.1.4` in the summary
   block at the end of `main()`.

Option 3 alone is insufficient (no durable artifact). Options 1 and 2 may be
combined. The implementer must pick and record the decision in a `# DECISION
HISTORY` comment in `build.py`.

### Import boundary

`compute_next_version` lives under `scripts/release/`. `build.py` lives under
`scripts/`. The cleanest approach is a direct `import` (both are in the same
package tree). Alternatively, the version can be obtained by calling
`compute_next_version.main()` and capturing its stdout via `subprocess` — but
that is heavier and unnecessary since a `_compute_version_str()` helper can
call the internal functions directly. The implementer should prefer direct
import over subprocess.

### Dry-run and validate-only behaviour

- `--dry-run`: compute the version and print it, but do NOT write `VERSION` or
  embed in the manifest.
- `--validate-only`: skip version computation entirely (the validate-only path
  exits before `_run_phases` is called).

## Acceptance Criteria

```gherkin
Given build.py is run against a repo with changelog entries and a v* tag
When python scripts/build.py --target-dir <target>
Then the computed version (e.g. v0.1.4) is printed in the build output
 And a VERSION file is written to <target> containing the bare version string
   OR the build manifest JSON contains a "version" key with the version string

Given build.py is run with --dry-run
When python scripts/build.py --dry-run --target-dir <target>
Then the computed version is printed
 And no VERSION file is written
 And the build manifest is not written

Given build.py is run with --validate-only
When python scripts/build.py --validate-only --target-dir <target>
Then version computation is skipped entirely
 And the process exits 0 after config validation
```

## Sign-offs

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### python-coder

- [ ] In `scripts/build.py`, import the internal helpers from
  `scripts/release/compute_next_version.py` (specifically
  `_resolve_repo_root`, `_resolve_changelogs_dir`, `_find_last_version_tag`,
  `_changelog_entries_since`, `_compute_bump`, `_bump_version`) or add a
  thin `_compute_version_str(repo_root, changelogs_dir)` wrapper that wires
  them together and returns the version string.
- [ ] Call the version helper near the top of `main()` — after config is
  loaded and validated, before `_run_phases()` is called. Assign result to
  `computed_version`.
- [ ] Apply the version: write `<target_root>/VERSION` with the bare version
  string (preferred), OR embed `"version": computed_version` in the manifest
  JSON passed to `write_build_manifest()` (document the chosen option in the
  `# DECISION HISTORY` block).
- [ ] Respect `--dry-run`: skip writing `VERSION` (or embedding in manifest)
  but still print `Build version: <computed_version>` in the summary.
- [ ] Respect `--validate-only`: skip version computation entirely (add an
  early return guard before the version call).
- [ ] Add a `# DECISION HISTORY` comment entry in `build.py` recording which
  application strategy was chosen and why.
- [ ] Ensure the import path resolves correctly regardless of whether
  `scripts/` is on `sys.path` (add `sys.path` manipulation if needed, or use
  `importlib`; match the pattern already used by `build.py` for its other
  imports).

### test-writer

- [ ] Add `unit_tests/test_build_version_wiring.py` (new file; use `tmp_path`
  fixture to isolate file writes):
  - `test_version_printed_in_build_output` — run `build.py` against a
    minimal fixture target with a synthetic changelog entry; assert the
    version string appears in stdout.
  - `test_version_file_written` — after a real (non-dry-run) build, assert
    `VERSION` exists in `target_root` and contains a `v\d+\.\d+\.\d+`
    string; OR assert the manifest JSON has a `"version"` key.
  - `test_dry_run_no_version_file` — run with `--dry-run`; assert `VERSION`
    is not written (or manifest key is absent).
  - `test_validate_only_skips_version` — run with `--validate-only`; assert
    version computation is not triggered (no `VERSION` file, no stdout
    version line).

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Fully reversible — removing the version call restores the
  prior build behaviour. The `VERSION` file (if added) is a new artifact;
  its absence does not break existing consumers.
- `compute_next_version.py` is stdlib-only and has no side effects unless
  `--tag` is passed; the integration does NOT pass `--tag`, so no git tags
  are created during a normal build run.
- If no `v*` tags exist and no changelog entries exist, `compute_next_version`
  returns `v0.0.0` (the baseline); this is safe and should be handled
  gracefully in `build.py` (just use the returned string, no special-casing
  needed).
