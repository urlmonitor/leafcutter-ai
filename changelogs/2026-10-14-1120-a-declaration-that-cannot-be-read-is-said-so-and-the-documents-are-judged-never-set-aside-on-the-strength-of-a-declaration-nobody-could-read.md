---
title: "A declaration that cannot be read is said so and the documents are judged, never set aside on the strength of a declaration nobody could read"
date: "2026-10-14"
time: "11:20"
type: manual
components:
  - commit_guardian
  - doc_compliance
summary: "When the list of generated documents the doc-length gate sets aside is broken or unreadable, the gate now prints a visible message and measures every document, instead of exempting anything on the strength of a declaration nobody could read."
description: "Closes GE-127g-2-i and with it GE-127g-2. The doc-length gate (templates/scripts/commit_guardian/check_doc_length.py) reads the set_aside_locations declaration once. If that read fails (file missing, invalid JSON, not a list, or an entry missing a required field) it prints a DECLARATION PROBLEM message to stderr naming what could not be read, sets nothing aside, and measures every staged document against the authored limits. A run over an unusable declaration never completes as a pass: it exits 1 even when no document is over a limit. If the commit_guardian.json config file itself cannot be loaded, the gate measures with built-in default limits (300 lines, 400 for ADRs, 25 sections) and no set-aside locations. This refusal path shipped earlier without test coverage and is now covered by unit_tests/commit_guardian/test_ge_127g_2_i.py. Restructuring only, no behaviour change: select_checked_paths and format_growth_note moved from templates/scripts/commit_guardian/check_doc_length.py into templates/scripts/commit_guardian/_doc_length_set_aside.py, and print_violation_reports and collect_violations were extracted, to keep check_doc_length.py within its size and complexity limits. A malformed declaration already blocked the commit before this change (exit 2, INDETERMINATE); it still blocks, now with a clearer message and with the documents judged."
breaking: false
---

## Entry

Fix for the case where the doc-length gate's set-aside declaration cannot be read.

- A broken declaration now produces a visible `DECLARATION PROBLEM` message, and every staged document is judged. No location is exempted on the strength of a declaration nobody could read.
- A run over an unusable declaration is never a pass. It exits 1 even when no document is over its limit.
- Nothing is newly refused by this change. A malformed declaration already blocked the commit, and a missing config file already failed the import. The difference is that the message now names the problem and the documents are measured.
- The refusal path is now covered by `unit_tests/commit_guardian/test_ge_127g_2_i.py`.
- Restructuring only: `select_checked_paths` and `format_growth_note` moved into `templates/scripts/commit_guardian/_doc_length_set_aside.py`, and `print_violation_reports` and `collect_violations` were extracted in `templates/scripts/commit_guardian/check_doc_length.py`. These changes alter no behaviour.
