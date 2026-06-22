---
title: "deploy missing commit_guardian scripts from templates/ to scripts/"
status: todo
priority: high
source_epic: EPIC-CodeQualityHooks (post-merge triage, 2026-06-22)
affected_tests:
  - unit_tests/commit_guardian/test_transform_hooks_and_autofix_emission.py::TestTransformDocFrontmatterFillsMissingFields (x2)
  - unit_tests/commit_guardian/test_transform_hooks_and_autofix_emission.py::TestTransformDocFrontmatterFailOpen (x2)
  - unit_tests/commit_guardian/test_transform_hooks_and_autofix_emission.py::TestTransformDescriptionFieldStubsFromTitle (x2)
  - unit_tests/commit_guardian/test_transform_hooks_and_autofix_emission.py::TestTransformDescriptionFieldFailOpen (x2)
  - unit_tests/commit_guardian/test_transform_hooks_and_autofix_emission.py::TestHooksManifestTierField
  - unit_tests/commit_guardian/test_transform_hooks_and_autofix_emission.py::TestCheckExceptionHandlingEmitsAutofixAgent
  - unit_tests/commit_guardian/test_transform_hooks_and_autofix_emission.py::TestCheckExceptionHandlingNoEmissionClean
  - unit_tests/test_build_guard_real_package.py::test_guard_exits_0_on_clean_package
---

# deploy missing commit_guardian scripts from templates/ to scripts/

## Problem

Three scripts exist in `templates/scripts/commit_guardian/` but have NOT been deployed to `scripts/commit_guardian/`. This causes 11 test failures (TDD red stubs from EPIC-PrecommitSafetyNet) and also causes `_check_script_reference_guard()` to fail on the clean package.

Missing scripts:
- `scripts/commit_guardian/transform_doc_frontmatter.py`
- `scripts/commit_guardian/transform_description_field.py`
- `scripts/commit_guardian/check_exception_handling.py` (exists in templates/, missing from scripts/)

Additional issue: hook `check-ac-pattern-refs` is missing the `tier` field in `commit_guardian.json`.

## Acceptance Criteria

- [ ] `scripts/commit_guardian/transform_doc_frontmatter.py` exists and implements the fill-missing-fields contract
- [ ] `scripts/commit_guardian/transform_description_field.py` exists and stubs description from title
- [ ] `scripts/commit_guardian/check_exception_handling.py` deployed from templates/ to scripts/
- [ ] `check-ac-pattern-refs` hook entry in `commit_guardian.json` has a valid `tier` field
- [ ] `test_guard_exits_0_on_clean_package` passes
- [ ] All 11 TDD stubs in `test_transform_hooks_and_autofix_emission.py` pass

## Classification

Pre-existing failures; TDD red stubs written by EPIC-PrecommitSafetyNet before implementation. Not caused by EPIC-CodeQualityHooks. First surfaced during finalization triage 2026-06-22.
