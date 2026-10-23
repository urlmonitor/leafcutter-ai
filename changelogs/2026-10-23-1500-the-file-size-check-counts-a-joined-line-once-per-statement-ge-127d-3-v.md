---
title: "The file-size check counts a line once per statement, so joining statements cannot shrink a file (GE-127d-3-v)"
date: "2026-10-23"
time: "15:00"
type: manual
components: 
  - commit_guardian
summary: "check-file-size now counts a line holding several statements once per statement, in Python and in JavaScript/TypeScript. Writing `a(); b();` or `x = 1; y = 2` or `if ready: start()` on one line measures the same as one statement per line, so joining statements lowers nothing. A join-only change adds 0 lines to the two-for-one repayment, and code written onto a joined line still counts as added. SQL and shell lines are counted as before."
description: "GE-127d-3-v closes the statement-joining route GE-127d-3 recorded as out of scope. The Python lexer reads statement breaks from the same token stream (after a top-level `;` and after a compound header's `:` when the body is on the same row; a lambda's `:` is skipped; `match`/`case` are left out), and the JavaScript-family scanner records a `;` outside any parenthesis opened since the innermost brace that has another statement after it on its line, so a callback body written on one line splits while a `for (;;)` header and separators in strings, template literals and comments do not split. spans.counted_keys splits a line at those breaks and keys each piece as if it stood on its own line, so the measured length and the added-lines diff still come from one pass; in Python the `;` itself is uncounted punctuation. The generated MEASUREMENT RULE gains a per-statement clause, probed from the measure, and README.md, commit_guardian.json and docs/reference/source-file-length-measurement.md carry it. Measured over every tracked covered file: 36 of 3400 measure higher, none crosses its limit. The GE-127f fixture builder now writes one statement per line (it relied on `def f(): return 1` measuring 1). Tests: unit_tests/commit_guardian/test_ge_127d_3_v.py."
breaking: false
---

## Entry
