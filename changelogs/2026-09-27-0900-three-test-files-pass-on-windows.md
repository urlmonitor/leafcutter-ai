---
title: "Three test files no longer fail on Windows for reasons unrelated to what they test"
date: "2026-09-27"
time: "09:00"
type: manual
components:
  - build_pipeline
  - commit_guardian
  - knowledge_management
summary: "Test-only fixes. test_bp_1500d_1 (and its harness) compared Windows backslash paths against the build record's forward-slash paths, so two BP-1500d-1 tests failed on every Windows run. test_doc_length_blocking_ratchet read the checker's UTF-8 output with the locale codec (cp1252), crashed the reader thread, and got stdout=None. Both now pass on Windows, and each fails again if its fix is reverted. The KM-300a-1 test also no longer trips the informational mypy check. No product code changed."
description: "WHY. These failures appeared only on Windows, so /finalize-feature's local post-merge test run flagged them as regressions, although nothing in the product was wrong. That blocked the merge of PR #892 on this machine. BP-1500d-1 (unit_tests/portability/test_bp_1500d_1.py, _bp1500d1_harness.py): both listings of the receiving project's files used str(Path.relative_to(...)), which gives backslashes on Windows. They were compared against '.claude/skills_config.json' and against the build record's forward-slash entries, so 'target held more than a minimal skills_config.json' and '59 of 59 deployed agent files are not named in the record' fired on every Windows run. Both listings now use .as_posix(). check-doc-length refusal tests (unit_tests/commit_guardian/test_doc_length_blocking_ratchet.py): _run_check ran the checker with text=True and no encoding. The checker writes UTF-8, the cp1252 decode raised in subprocess's reader thread, and result.stdout came back None, so the assertion message itself raised TypeError. It now passes encoding='utf-8'. KM-300a-1 (unit_tests/commit_guardian/test_km_300a_1_doc_index_posix_links.py): the link-lookup helper returned Optional and the callers indexed it after assertIsNotNone, which mypy cannot narrow. The helper now raises when no link matches. EVIDENCE. On Windows: 19 passed with the fixes; with the three test fixes reverted, 5 failed (2 BP-1500d-1, 3 doc-length). The restored files are byte-identical and 19 pass again. ruff and mypy are clean. NOT CHANGED. No AC was authored: the tests already cover BP-1500d-1 and the check-doc-length refusal (#801), and the fix restores their ability to prove those ACs on Windows."
commits:
breaking: false
---

## Entry

Three test files failed on Windows for reasons that had nothing to do with the
behaviour they check. That made `/finalize-feature`'s local test run report
regressions that were not real.

- **`test_bp_1500d_1.py` and its harness** listed files with `str(Path)`, which
  gives backslashes on Windows, and compared them with forward-slash paths. They
  now use `.as_posix()`.
- **`test_doc_length_blocking_ratchet.py`** decoded the checker's UTF-8 output as
  cp1252, crashed the reader and got `stdout=None`. It now reads UTF-8.
- **`test_km_300a_1_doc_index_posix_links.py`** no longer trips the informational
  mypy check.

No product code changed. Each fix was checked by reverting it: the affected tests
fail again without it.

### Known issues filed from the same session

Five new KIs are filed, and six existing ones gain a dated occurrence:

- finalize-feature's triage baseline predates the merged `main`
  (KI-BO-20260927-finalize-triage-baseline-predates-merged-main).
- quick-fix accepts a gitignored build copy as its target, and cannot target an
  existing leaf AC (two KI-BO-20260927 entries).
- `subprocess.run(text=True)` decodes with the locale codec across the repo:
  212 calls (KI-CG-20260927 sweep).
- A bare full `pytest` run has 114 collection errors (KI-TQ-20260927).
- New occurrences:
  - KI-BO-20260901-1620 (status-checker handed shell work)
  - KI-BO-20260907 (resume replays cached git-state steps)
  - KI-BP-008 (deployed workflows have no freshness signal)
  - KI-BP-20260910-1240 (Windows CRLF writers dirty every fresh worktree)
  - KI-BO-20260826-1332 (concurrent duplicate work goes undetected)
  - resolved KI-ACD-004 (a recurrence on a stale build)
