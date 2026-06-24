---
title: "Detect dependency manager and make worktree bootstrap non-fatal"
status: in_progress
components:
  - worktree_manager
created: 2026-06-24
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/setup_ticket_worktree.py
  - templates/scripts/setup_ticket_worktree.py
agents:
  architect-review: not_needed
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 07: Detect dependency manager and make worktree bootstrap non-fatal

## Actor / Goal

In order to stop worktree creation from aborting on repos that don't use poetry,
we need `setup_ticket_worktree.py` to detect the dependency manager (poetry vs
pip) and to treat a dependency-install failure as a non-fatal warning rather than
crashing before `build.py` runs.

## Context

`_bootstrap()` (≈ lines 215-230) unconditionally runs
`poetry install --no-root` with `check=True`. This repo has **no `pyproject.toml`**
— it uses `requirements-dev.txt` with system Python. The call always fails here
(this session reproduced it:
`Poetry could not find a pyproject.toml file ... returned non-zero exit status 1`),
and because the call is placed AFTER the worktree is created and is `check=True`,
the script aborts before the critical `build.py` step that materialises
`.leafcutter/`, leaving a half-bootstrapped worktree. It is also a portability
defect: the same code ships in `templates/scripts/`, so any pip-based adopter hits
it too.

Other steps in the same file (`build.py`, pre-commit shim install) already use the
catch-warn-continue pattern; the dependency-install step should match.

## Acceptance Criteria

- [ ] AC-1: `_bootstrap()` selects the dependency command by detecting the repo's
  manifest: `pyproject.toml` → `poetry install --no-root`; else
  `requirements-dev.txt` (or `requirements.txt`) → `<python> -m pip install -r <file>`;
  else → no dependency step.
- [ ] AC-2: A dependency-install failure (missing tool, install error) is caught,
  logged as a WARNING to stderr, and does NOT abort bootstrap — the worktree
  remains created and `build.py` still runs.
- [ ] AC-3: On this repo (requirements-dev.txt, no pyproject.toml),
  `setup_ticket_worktree.py setup-ticket <ticket>` completes successfully and emits
  the worktree JSON, without the poetry crash.
- [ ] AC-4: The same fix is mirrored into `templates/scripts/setup_ticket_worktree.py`
  so consumer installs benefit.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |

## Sign-offs
- [x] test-writer — 2026-06-24 14:00
- [x] python-coder — 2026-06-24 00:00
- [x] test-runner — 2026-06-24 15:00
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-24 00:00 — python-coder (status: ok)
feedback-id: fb_2026-06-24_435bfb01
completion_manifest:
  manifest_detection_added: true
  non_fatal_install_wrapped: true
  templates_copy_mirrored: true
  all_15_tests_green: true
  ruff_clean: true
Replaced the unconditional `poetry install --no-root` in both `scripts/setup_ticket_worktree.py` and `templates/scripts/setup_ticket_worktree.py` with manifest-detection logic (pyproject.toml → poetry; requirements-dev.txt → pip; requirements.txt → pip; no manifest → skip). Install failures are now caught as `(subprocess.SubprocessError, OSError)`, a WARNING is printed to stderr, and bootstrap continues — matching the existing catch-warn-continue pattern used by the `build.py` step. All 15 tests pass; ruff reports no issues on both files.

### 2026-06-24 14:00 — test-writer (status: ok)
feedback-id: fb_2026-06-24_71e9cb61
completion_manifest:
  test_stubs_written: true
  tests_red_confirmed: true
  scripts_copy_covered: true
  templates_copy_covered: true
Added 6 new test stubs to `tests/test_setup_ticket_worktree.py` covering all 4 AC scenarios: poetry-repo path (AC-1), pip-repo path (AC-1), no-manifest path (AC-1), install-failure-non-fatal path (AC-2), plus template mirror variants (AC-4). Red baseline: 4 tests FAILED (pip-repo, no-manifest, install-failure-non-fatal in scripts/ copy; install-failure-non-fatal in templates/ copy). 2 stubs (poetry-repo path in both copies) are incidentally green because the current code unconditionally runs poetry, which correctly satisfies the poetry-detection assertion — they will remain green after implementation.

red_baseline:
  - TestBootstrapPipRepo::test_bootstrap_uses_pip_when_requirements_dev_txt_present
  - TestBootstrapNoManifestRepo::test_bootstrap_skips_dep_install_when_no_manifest
  - TestBootstrapInstallFailureNonFatal::test_bootstrap_install_failure_is_non_fatal
  - TestTemplateBootstrapInstallFailureNonFatal::test_template_bootstrap_install_failure_is_non_fatal

### 2026-06-24 15:00 — test-runner (status: ok)
feedback-id: fb_2026-06-24_43fc6a3a
completion_manifest:
  red_baseline_tests_now_green: true
  all_15_tests_passed: true
  scripts_copy_covered: true
  templates_copy_covered: true
All 15 tests passed (15/15). All 4 red-baseline tests are now green: TestBootstrapPipRepo::test_bootstrap_uses_pip_when_requirements_dev_txt_present, TestBootstrapNoManifestRepo::test_bootstrap_skips_dep_install_when_no_manifest, TestBootstrapInstallFailureNonFatal::test_bootstrap_install_failure_is_non_fatal, TestTemplateBootstrapInstallFailureNonFatal::test_template_bootstrap_install_failure_is_non_fatal. The manifest-detection logic and non-fatal install-failure wrapping are correctly implemented in both scripts/ and templates/scripts/ copies.

## Implementation Tasks
- [x] Add manifest detection + branch the install command.
- [x] Wrap the install in try/except → WARNING + continue (per Error Handling Policy).
- [x] Mirror to the templates/ copy.
- [ ] Tests: poetry-repo path, pip-repo path, no-manifest path, install-failure-non-fatal path.

## Risk & Safety
- Touches money? No.
- Touches data? No.
- Reversibility? High.
