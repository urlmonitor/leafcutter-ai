---
title: "Commit-guardian locators find their sibling modules when scripts/commit_guardian is a copied shim"
status: todo
components:
  - commit_guardian
created: 2026-10-08
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: contract_boundary
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - commit-guardian
  - windows
  - copy-shims
  - deploy-layout
  - ge-118d
last_updated: 2026-10-08
files_touched:
  - templates/scripts/commit_guardian/_frontmatter_path_resolver_locator.py
  - templates/scripts/commit_guardian/_ac_store_locator.py
  - unit_tests/commit_guardian/test_locators_copy_mode_install.py  # new
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Commit-guardian locators find their sibling modules when scripts/commit_guardian is a copied shim

## Actor / Goal
In order that the commit guard works the same on a Windows install as on Linux, we need the
commit-guardian locator modules to find `frontmatter_path_resolver.py` and `ac_store/` when
`<project>/scripts/commit_guardian/` is a copy rather than a symlink. Then running a guard through
that shim path never crashes with `ModuleNotFoundError`.

## Context
- **Failing test (Windows only):**
  `unit_tests/commit_guardian/test_ge_118d_deployed.py::TestGe118dDeployedGuardAcceptsBareAndLabelledEntries::test_ge_118d_deployed_guard_accepts_bare_and_labelled_entries_in_all_three_fields`.
  It is masked as xfail in a normal run because GE-118d is `in_progress`, and it shows with
  `AC_ENFORCE_STRICT=1`.
- **Reproduced on main `6ccbd14ea`, 2026-10-08, Windows 11 (`AC_ENFORCE_STRICT=1`):** after a real
  `build.py --target-dir <tmp>`, running `<tmp>/scripts/commit_guardian/run_hook.py
  check_doc_frontmatter.py <doc>` fails with
  `ModuleNotFoundError: No module named 'frontmatter_path_resolver'`, raised from
  `frontmatter_validators.py` line 52.
- **Root cause (verified):**
  - On this host the build cannot create symlinks, so `install_shims` (`scripts/build_helpers.py:1394`)
    falls back to copies ("shim: ... (copy)" in the build log). `<tmp>/scripts/commit_guardian` is
    then a real directory.
  - `_frontmatter_path_resolver_locator.py` assumes the symlink layout. Candidate 1 is
    `Path(__file__).resolve().parent.parent / "frontmatter_path_resolver.py"`. Through a
    symlinked shim that resolves into `.leafcutter/scripts/`, where the resolver is deployed.
    Through a copy it is `<tmp>/scripts/frontmatter_path_resolver.py`, which does not exist:
    `shim_map` bridges only `scripts/commit_guardian`, `scripts/doc_compliance` and
    `scripts/feedback`.
  - Candidate 2 walks up to the `.git`/`CLAUDE.md` root and tries `<root>/scripts/...`, also
    absent. Neither candidate looks under the install's output root (`.leafcutter/scripts/`).
- **The sibling locator has the same gap (verified).** Probing the copy-mode install directly:
  - from `<tmp>/scripts/commit_guardian`, both `_ac_store_locator.resolve_ac_store_dir()` and
    `_frontmatter_path_resolver_locator.resolve_frontmatter_path_resolver_module()` return `None`;
  - from `<tmp>/.leafcutter/scripts/commit_guardian`, both find their targets.

  So `check_done_proof.py` run through the shim path cannot import `done_proof` either.
- **Who is affected.** The package's own pre-commit config calls the guards through
  `.leafcutter/scripts/commit_guardian/...`, which works. The `scripts/commit_guardian` shim exists
  so that "tests and hooks that reference scripts/commit_guardian/ ... still resolve"
  (`shim_map` comment, `scripts/build_helpers.py` about :87-95). Every adopter install without
  symlink rights (Windows without Developer Mode) breaks that promise.
- Related: TICKET-20260928-GE-118d (introduced the resolver locator, merged in #951; that
  ticket's AC GE-118d is still `in_progress`). This defect is in the layout handling, not in
  GE-118d's shape rule.

## Acceptance Criteria
- [ ] AC-1: In a `build.py --target-dir` install built with `shim_strategy` `copy`, running the
  guard through the shim path
  (`python <target>/scripts/commit_guardian/run_hook.py <target>/scripts/commit_guardian/check_doc_frontmatter.py <doc>`)
  imports `frontmatter_path_resolver` and exits 0 for a valid document, with no traceback on
  either stream. The test forces the copy strategy, so it runs on Linux CI too.
- [ ] AC-2: In the same install, `_ac_store_locator.resolve_ac_store_dir()` imported from
  `<target>/scripts/commit_guardian` returns the install's `ac_store` directory holding
  `done_proof.py`.
- [ ] AC-3: Both locators still resolve correctly in the three layouts they serve today: a
  symlinked shim, the `.leafcutter/scripts/commit_guardian` path, and the source tree
  `templates/scripts/commit_guardian`. Existing locator and GE-118d tests pass.
- [ ] AC-4: `test_ge_118d_deployed_guard_accepts_bare_and_labelled_entries_in_all_three_fields`
  passes on Windows with `AC_ENFORCE_STRICT=1`.
- [ ] AC-5: The locators find the output root without `Path.cwd()`. When the install declares
  an `output_root` other than `.leafcutter`, they use the declared one. When none is declared,
  they fall back to the default `.leafcutter`.

## Test Requirements

```yaml
tests:
  - name: test_guard_via_copied_shim_imports_the_path_resolver
    location: unit_tests/commit_guardian/test_locators_copy_mode_install.py
    type: integration
    covers: [AC-1]
    description: |
      Real build.py into a temp target with shim_strategy copy; run the deployed guard through
      scripts/commit_guardian/ and assert exit 0 and no ModuleNotFoundError. Red today on every
      platform once the copy strategy is forced.
  - name: test_ac_store_locator_via_copied_shim_finds_done_proof
    location: unit_tests/commit_guardian/test_locators_copy_mode_install.py
    type: integration
    covers: [AC-2]
    description: |
      Same install; import _ac_store_locator from the copied shim and assert it returns the
      install's ac_store directory.
  - name: test_locators_keep_resolving_in_existing_layouts
    location: unit_tests/commit_guardian/test_locators_copy_mode_install.py
    type: unit
    covers: [AC-3, AC-5]
    description: |
      Symlinked shim (skipped only where symlinks cannot be created), .leafcutter path and the
      source tree each resolve; a non-default output_root is honoured.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_guard_via_copied_shim_imports_the_path_resolver | | |
| AC-2 | test_ac_store_locator_via_copied_shim_finds_done_proof | | |
| AC-3 | test_locators_keep_resolving_in_existing_layouts; existing tests | | |
| AC-4 | test_ge_118d_deployed.py (Windows, strict) | | |
| AC-5 | test_locators_keep_resolving_in_existing_layouts | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks
- [ ] Add an output-root candidate to both locators (shared helper if it fits the
  `_resolve_root.py` pattern), between the sibling and the root-walk candidates.
- [ ] Edit the templates only; the deployed copies are regenerated by `build.py`.
- [ ] Tests above; rerun `unit_tests/commit_guardian/` on Windows with `AC_ENFORCE_STRICT=1`.

## Risk & Safety
- Touches money? No.
- Touches data? No. Import resolution of the commit guard; a wrong candidate fails loudly with
  `ModuleNotFoundError`, never silently.
- Reversibility: revert the commit and rebuild.

## Out of Scope
- Changing the shim map to bridge more of `scripts/`.
- Making the build create symlinks on Windows.
