---
title: "The build-orchestration tests type-check clean"
date: "2026-11-16"
time: "15:00"
type: manual
components:
  - build_orchestration
summary: "mypy, run with the CI flags over every tracked .py file under unit_tests/build_orchestration/, reported 126 errors in 25 files. It now reports none there. Only typing changed: no assertion was removed or loosened, no test was renamed or skipped, and no production code changed."
description: "test(build-orchestration), typing only. Batch d of the mypy ratchet clean-up. (1) attr-defined: class-level declarations for what setUpClass assigns in test_bo_4300b_1, test_bo_4300a_1_deployed, test_bo_4300a_1_route_shape and test_bo_4300f_4. (2) 'None' not callable / no-redef: test_bo2400f_lifecycle, test_bo2400f_7_cli_proof, test_fast_lane_connected and test_build_dataflow pre-declared each guarded import as None, so mypy typed the function as None. The pre-declarations are gone, and with them ten '# type: ignore[assignment]' and eight '# type: ignore[no-redef]' comments. A failed import now leaves the name unbound, and every use sits behind the existing _require_*_impl, skip or _OK guard. test_bo_2600a_5 drops its build_epic_from_ids = None and _gte = None pre-declarations and imports the function with from goal_to_epic import build_epic_from_ids inside the existing try. A missing function now raises ImportError, which the existing except turns into the red-state _FUNC_IMPORT_ERR, where it used to be a getattr default of None. The file is over its size limit, and the change shortens it from 427 to 421 counted lines. (3) Optional narrowing: an assert isinstance after each existing assertIsNotNone (test_bo_2600a_5, test_bo_4300_docs, test_bo_4300f_1, test_bo_4300f_3_iii, test_bo_4300f_3_iv, test_bo_4300f_3_cutover, _bo_4300f_3_keep_fixtures). test_bo_4300e_4 asserts that each maker command line it reads is a str, with a message, before using it. _bo4400f1_helpers asserts that the Popen pipes are not None. (4) Annotations: _bo_4300c_6_fixtures.run_canary returns a CanaryRun, a CompletedProcess subclass that declares the decoded out and err text instead of setting them on a plain CompletedProcess. Corrected or added annotations in test_tq500f3iii_red_baseline_identity (the helper returns a tuple), _tq500g2i_standin_pg, _tq500g2i_review_fixtures, _bo_4300f_2_fixtures, test_bo_4300b_3, test_bo_4300b_4 and test_bo_4300c_1. No new '# type: ignore', cast or Any. The two errors still reported in unit_tests/workflows/_bo4000_fixtures.py are outside this batch."
breaking: false
---

## Entry
