---
title: "Three over-length test files are split into small packages and now type-check cleanly"
date: "2026-11-16"
time: "16:31"
type: manual
components:
  - testing_quality
summary: "test_ge_120e_1.py, test_ge_120e_2.py and test_bp_100k_3.py each stood over the 400-line file-size limit, so the 83 mypy errors left in them could not be fixed in place. Each is now a package of its own (unit_tests/portability/ge_120e_1/, unit_tests/portability/ge_120e_2/, unit_tests/commit_guardian/bp_100k_3/) holding a shared _support.py and two or three test modules, the largest at 292 measured lines against the 400-line limit, and all of them mypy-clean. The same 25 tests are collected under the same class and method names, and all pass."
description: "Test-only restructure. Each original file was moved with git mv to its package's _support.py, which keeps the original module docstring and contract, the fixtures, the helpers and the path constants (repo-root depth adjusted for the extra directory level). The tests moved unchanged into test modules grouped by angle or behaviour: GE-120e-1 into criterion, boundary_and_seam and failure_and_reachability; GE-120e-2 into determination (tests 1-6) and consumers_and_reachability (tests 7-8); BP-100k-3 into build_drift_reporting (AC-1 to AC-4), exemption_registry (AC-5) and function_and_main. Repeated set-up became shared base classes: NoAuthorMergeTestCase replaces the setUpClass/tearDownClass four GE-120e-1 classes each carried, and WorkspaceTestCase, BuildDriftScenarioTestCase and SyntheticPackageTestCase replace the per-test workspace setUp every BP-100k-3 class repeated. Type fixes: setUpClass attributes are declared as ClassVar at class level, and the three RESULT-line matches in BP-100k-3 are narrowed with isinstance after their existing assertIsNotNone; no type: ignore, cast or Any. The guarded imports dropped their type: ignore comments; the import of scripts.commit_guardian.change_set_source also dropped its None fallback, because that dotted path resolves for mypy wherever the build has deployed scripts/commit_guardian/, and every use of the name already sits behind a self.fail guard. Two constants nothing read in the BP-100k-3 file were removed. The new files sit in new subfolders because unit_tests/portability/ and unit_tests/commit_guardian/ are already far over the folder-density cap. Follow-on edits: test_tq100a_2.py now reads _GIT_ENV_OVERRIDES from ge_120e_1/_support.py and runs its identity-write scan over all four files of the split GE-120e-1 suite; GE-120e-1 and GE-120e-2 implemented_by and BP-100k-3 covered_by name the new paths; the 25 pytest-split duration keys in .github/test_durations.json are renamed to the new node ids."
adrs: []
commits: []
breaking: false
---

## Entry
