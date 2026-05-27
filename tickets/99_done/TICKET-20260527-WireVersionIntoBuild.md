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
  architect-review: signed_off
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  change-scope-reviewer: not_needed
  pr-reviewer: signed_off
  commit: signed_off
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

- [x] architect-review — 2026-05-27 10:00
- [x] test-writer — 2026-05-27 10:30
- [x] python-coder — 2026-05-27 10:15
- [x] test-runner — 2026-05-27 10:45
- [x] pr-reviewer — 2026-05-27 11:00
- [x] commit — 2026-05-27 11:15
- [ ] pull-request

## Comments

### 2026-05-27 10:00 — architect-review (status: ok)
feedback-id: fb_2026-05-27_c5c0152b
Impact classification: SMALL. Affected files: scripts/build.py + scripts/release/compute_next_version.py (2 files, 1 component: build_pipeline). No always-large triggers fired (no Alembic migration, no hypertable change, no public API change, no ADR contract change). Staying within one top-level package (scripts/). Design concern: direct import is cleaner than subprocess; the ticket already specifies this. The `_resolve_repo_root()` helper in compute_next_version.py handles the path resolution so no sys.path manipulation is needed beyond what the ticket describes. requires_adr: false. No diagram needed (pure refactor within one component). Acceptance criteria are well-formed — proceeding to python-coder.

### 2026-05-27 10:15 — python-coder (status: handoff)
feedback-id: fb_2026-05-27_35b682da
Implemented version wiring in scripts/build.py. Added `from release.compute_next_version import ...` (direct import; scripts/release/ is a proper package with __init__.py; scripts/ is on sys.path when build.py runs). Added `_compute_version_str(package_root)` helper (complexity 2, full docstring). Wired call in main() after config validation, before _run_phases(). Strategy chosen: write target_root/VERSION (Option 1) + print "Build version: vX.Y.Z" (Option 3). --validate-only exits before version call (no VERSION). --dry-run prints version and `[DRY-RUN] would write .../VERSION` but does not write. DECISION HISTORY entry added. All 7 python-coder tasks checked. Handing off to test-writer.

### 2026-05-27 10:30 — test-writer (status: ok)
feedback-id: fb_2026-05-27_2c8a6357
Created unit_tests/test_build_version_wiring.py with 4 tests covering all acceptance criteria. Tests use monkeypatching to stub expensive build phases (avoids WSL subprocess slowness). All 4 tests passed: test_version_printed_in_build_output, test_version_file_written, test_dry_run_no_version_file, test_validate_only_skips_version. Run: `python -m pytest unit_tests/test_build_version_wiring.py -v`. Result: 4 passed in 81.24s.

### 2026-05-27 10:45 — test-runner (status: ok)
feedback-id: fb_2026-05-27_87acca20
Ran unit_tests/test_build_version_wiring.py. Result: 4 passed in 81.24s (0:01:21). Tests are slow due to _compute_version_str calling git commands on the WSL filesystem, but all 4 pass and correctly verify the acceptance criteria.

### 2026-05-27 11:00 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-27_26ac3557
Reviewed 3-file diff (scripts/build.py +60, unit_tests/test_build_version_wiring.py +241, ticket). No high-confidence findings. 2 medium findings: (M-1) _compute_version_str ignores its package_root parameter and calls _cnv_resolve_repo_root() directly — benign but misleading signature; (M-2) computed_version is calculated before the --migrate early-return guard — minor efficiency concern. Medium count <= 3; no Opus escalation. Both medium findings are non-blocking. Approved.

## Review Report
Base: main
Diff size: +301 lines across 2 code files
High-Confidence Findings: None
Medium-Confidence Findings:
[M-1] scripts/build.py — _compute_version_str signature has unused package_root param
[M-2] scripts/build.py — computed_version computed before --migrate guard runs
Suppressed: 0 low, 0 Opus-dropped medium

### 2026-05-27 11:15 — commit (status: ok)
feedback-id: fb_2026-05-27_65db2f1a
Staged 3 files: scripts/build.py (implementation), unit_tests/test_build_version_wiring.py (tests), tickets/99_done/TICKET-20260527-WireVersionIntoBuild.md (ticket with all sign-offs). Commit will follow.

## Escalation

Branch: none
Reason: 2 files in one component (build_pipeline); no always-large trigger fired.

## Implementation Tasks

### python-coder

- [x] In `scripts/build.py`, import the internal helpers from
  `scripts/release/compute_next_version.py` (specifically
  `_resolve_repo_root`, `_resolve_changelogs_dir`, `_find_last_version_tag`,
  `_changelog_entries_since`, `_compute_bump`, `_bump_version`) or add a
  thin `_compute_version_str(repo_root, changelogs_dir)` wrapper that wires
  them together and returns the version string.
- [x] Call the version helper near the top of `main()` — after config is
  loaded and validated, before `_run_phases()` is called. Assign result to
  `computed_version`.
- [x] Apply the version: write `<target_root>/VERSION` with the bare version
  string (preferred), OR embed `"version": computed_version` in the manifest
  JSON passed to `write_build_manifest()` (document the chosen option in the
  `# DECISION HISTORY` block).
- [x] Respect `--dry-run`: skip writing `VERSION` (or embedding in manifest)
  but still print `Build version: <computed_version>` in the summary.
- [x] Respect `--validate-only`: skip version computation entirely (add an
  early return guard before the version call).
- [x] Add a `# DECISION HISTORY` comment entry in `build.py` recording which
  application strategy was chosen and why.
- [x] Ensure the import path resolves correctly regardless of whether
  `scripts/` is on `sys.path` (add `sys.path` manipulation if needed, or use
  `importlib`; match the pattern already used by `build.py` for its other
  imports).

### test-writer

- [x] Add `unit_tests/test_build_version_wiring.py` (new file; use `tmp_path`
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
