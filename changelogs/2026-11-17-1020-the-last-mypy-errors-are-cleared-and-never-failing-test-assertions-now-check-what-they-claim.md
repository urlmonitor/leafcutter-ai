---
title: "The last mypy errors are cleared, and never-failing test assertions now check what they claim"
date: "2026-11-17"
time: "10:20"
type: manual
components: 
  - knowledge_management
  - testing_quality
summary: "Clears the last 5 mypy errors under CI's flags by narrowing only, with no type-ignore, cast or Any. Planning or writing Neo4j publication batches before begin_writes now fails with a RuntimeError that names begin_writes (new L3 KM-400b-5-vii), not a TypeError on None. Four tests whose assertions could never fail now assert the real exception, log or path, and one stale docstring is corrected."
description: "chore(types)/fix(knowledge), KM-400b-5-vii. mypy --ignore-missing-imports --explicit-package-bases reported 5 errors in 3 files; it now reports none. knowledge/adapters/neo4j_writes.py (3): a new _begun() raises RuntimeError naming begin_writes and the missing report when publication_writes or publication_progress is None. make_plan and write_batches check at the top, before settings are read or any batch is sent. with_retry checks only where it records a retried batch, so its failure classification (KM-400b-5-vi tests rely on it) and activation (no batch descriptor) still run without begin_writes. Before, these paths raised a TypeError on None or an AttributeError on _write_settings, or passed silently when no record was oversized. The production path (neo4j_domain_build.build) always calls begin_writes first. Red before the fix: 4 of the 5 first tests failed at neo4j_writes.py lines 161, 167, 220 and 256. scripts/build_orchestration/wrong_version_runner.py (1): a new _db_findings() returns ctx.db_seen or raises PutBackFailed, inside _drive's existing try, so a missing record stops the drive like any other put-back failure. scripts/ac_store/test_enforcement.py (1): extract_covers_tag returns None unless the target is callable or a module, traceback, frame or code object, the kinds inspect.getsource reads. Its only caller passes pytest items. New L3 KM-400b-5-vii under KM-400b-5, covered by tests/knowledge/test_km_400b_5_vii.py (6 tests). Tests: test_ge_120e_2_determination.py and test_ge_120e_2_i.py used assertRaises(Exception) followed by assertNotIsInstance(KeyboardInterrupt), which cannot fail because KeyboardInterrupt is not an Exception. They now assert FileNotFoundError on the given path, and CalledProcessError on the bogus build.py, each with its WARNING log. test_bo_2600a_5.py drops an assertIsNotNone on an imported module. test_bo_4300f_4.py stops storing an unread layout_root in one class, and in the other asserts that the resolved maker is under it. test_tq_600a_13_xvi_units.py docstrings now say that the masking plugin sets pytest's own xfail shape (outcome skipped plus wasxfail) since PR #1432."
adrs: []
commits: []
breaking: false
---

## Entry
