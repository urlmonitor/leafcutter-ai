---
title: "KM-400 and KM-400e closed through their children; two live KM-400a-3-i checks repaired after a month of hidden failure"
date: "2026-11-17"
time: "12:00"
type: manual
components:
  - knowledge_management
summary: "KM-400e and KM-400 are done, proved through their children under KM-ADM-005-3. Closing them made Proof-of-done run every live check below KM-400, which exposed two live Neo4j checks for KM-400a-3-i that had been failing on main since 2026-10-20. Both checks are repaired; no product code changes."
description: >-
  KM-400e (L1) and KM-400 (L0) are set to done with dated amended_by entries.
  All their children are done and covered by tests, and neither record gets a
  test or waiver of its own.
  Proof-of-done then ran every linked live check under KM-400, and two
  KM-400a-3-i checks in tests/knowledge_live/ failed. They only run when a
  covering AC changes, so they had been red on main unnoticed since
  1c8278905 (KM-400f-3). That commit gave Neo4jBackend._run a database=
  keyword, and the checks' _run stand-ins kept the old signature, so every
  publish through them raised TypeError. Both stand-ins now accept and
  forward keyword arguments.
  The recovery check in native_refresh_recovery_checks.py is renamed to
  test_interrupted_publication_removes_its_partial_generation_and_retry_keeps_history
  and realigned with KM-400b-5-i. An interrupted publication now removes its own
  partial generation: 0 nodes and 0 relationships remain, its record reads
  failed, and the previous active generation and its payloads are unchanged.
  The operator retry still runs through native_refresh.run, which must publish
  and verify the one retained generation. The check's patched snapshot loader
  now returns a fresh snapshot, as the real loader does. Reusing the object the
  failed publish had collapsed in place changed its raw digest, and native
  refresh refused to resume.
  KM-400a-3-i's covered_by and test_spec point at the renamed check.
breaking: false
---

## Entry

KM-400 (trustworthy project knowledge) is closed through its children. The two live
recovery checks that this closure exposed are repaired and realigned with KM-400b-5-i.
