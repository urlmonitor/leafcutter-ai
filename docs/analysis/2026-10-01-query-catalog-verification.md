---
title: Query catalog implementation verification
description: Measured neutral query compiler, admission and persistence outcomes for KM-500.
type: explanation
status: active
created: '2026-10-01'
last_updated: '2026-10-01'
components: [knowledge_management, decision_kernel]
---
# Query catalog verification

The PO reviewed a separate KM-500 outcome with three benefits and nine implementation leaves. BA wrote behavior and independently reviewed the component-test expectations from immutable Git. IT PO supplied boundary and test contracts. Canonical generated KM-500b-2 and b-3 tickets preceded neutral production implementation. This report covers neutral query work; kernel completion evidence is recorded separately.

## Test-first and independent review

Initial `tests/knowledge/test_query_admission.py`: **9 failed, 1 passed**, with individual missing-module failures before production. The passing case preserved existing rejection of an unknown ordinary retrieval operation. Four later regressions first failed for stale same-query re-verification receipts and malformed catalog object shapes; corrected behavior passed. BA independently exposed a memory-relationship mapping bypass with a failing test; it was corrected before acceptance.

Focused catalog/core/BA-boundary command at the first integrated pass: **36 passed in 1.48 seconds** using the workspace Python 3.14 environment and explicit `-o addopts= -p no:cacheprovider`. This does not claim the default AC-plugin injection ran. Subsequent new atomic-publication assertions and final integrated counts are recorded by the delivery review.

## Real database evidence

`tests/knowledge_live/query_catalog_checks.py` ran against an isolated local Neo4j Community 5.26 container using the repository's pinned image. **2 passed in 2.12 seconds**. These checks executed newly compiled two-hop Cypher, independent admission cases, catalog restart, actual public retrieval, an eleven-AC fanout exceeding the ten-neighbor bound, and a genuinely completed empty query. High fanout returned `partial` with truncation; completed empty returned `ok` with no evidence. No fake Cypher interpreter was used for this proof. Neo4j/Python driver deprecation warnings were nonblocking.

Unit fixtures inject a small database double for service and persistence boundaries and do not claim Cypher correctness. Declared-case proof records actual IDs, expected IDs, scope, source SHA, generated-query digest and measured expansion truncation. Reviewer names are attribution, not bypassable proof. Safety and declared-case success do not establish general semantic usefulness.

## Repository gates and limits

Actual neutral staged-file gates passed after corrections: complexity on fifteen Python files with maximum fifteen, size on fifteen files, documentation on thirteen source files, docstrings on thirteen, and strict Ruff error-policy checks. No check was disabled. Final commit enforcement remains separate from these early targeted checks.

The implementation deliberately supports a restricted authored recipe grammar rather than unrestricted model Cypher. Unsupported grammar remains a code-build gap. Persistent catalog paths are application configuration. Admission is separate from read-only retrieval and requires caller authorization; the kernel owns that permission gate. Published entries retain historical digests. A stale writer lock fails closed and requires operator recovery after verifying no writer remains.

Final collision recovery restored both exact local live tests to the dedicated query_catalog_checks.py file; rerun: **2 passed in 1.20 seconds**. Aura kernel proof remains separately owned in query_growth_checks.py.
