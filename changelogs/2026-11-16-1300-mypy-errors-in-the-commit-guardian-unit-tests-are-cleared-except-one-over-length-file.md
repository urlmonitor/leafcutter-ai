---
title: "mypy errors in the commit-guardian unit tests are cleared, except in one over-length file"
date: "2026-11-16"
time: "13:00"
type: manual
components: 
  - commit_guardian
summary: "mypy now reports 4 errors in unit_tests/commit_guardian/, down from 186, all in test_bp_100k_3.py. Only type declarations and narrowing were changed: no assertion was removed or loosened, no test was renamed and no type-ignore was added."
description: "Typing-only change to 13 test files under unit_tests/commit_guardian/, measured with the CI flags (mypy --ignore-missing-imports --explicit-package-bases). Attributes that setUpClass assigns are declared at class level in test_inf_700b_2.py, test_inf_700b_2_followup.py, test_inf_700b_2_ci.py, test_bp_100k_3_i.py and test_bp_100k_5_ii.py. Each RESULT-line regex match that a test already requires with assertIsNotNone is narrowed with assert isinstance(match, re.Match) before its groups are read (test_bp_100k_3_i.py, test_bp_100k_5_ii.py, test_bp_100k_3_hardening_b1.py, test_bp_100k_3_hardening_b2.py, test_bp_100k_3_vii.py, test_bp_100n_1.py). test_check_secrets.py stores the parsed prefixes only after the skip check, so the attribute is never None. test_ge_122e_2.py's module loader raises ImportError when no spec or loader is found. test_check_workflow_meta.py runs its two git calls as two statements instead of one tuple expression. test_build_precommit.py declares the fallback-imported module as ModuleType | None. test_bp_100k_3.py keeps its 4 errors: it measures 459 lines against a 400 limit, so the 3 narrowing lines would have to be paid back with 6 removed lines, and it holds only 4 lines of dead code. The no-redef error in scripts/commit_guardian/run_hook.py is outside this directory and unchanged."
adrs: []
commits: []
breaking: false
---

## Entry
