---
title: "Drift gate refactored under its size limit, and its exemption behaviour now has acceptance criteria"
date: "2026-10-08"
time: "16:30"
type: manual
components: 
  - commit_guardian
  - build_pipeline
summary: "check_output_drift.py drops from 630 to 354 measured lines with no behaviour change, and the drift-exemption change from PR #1013 gets three acceptance criteria, tagged tests, a new regression test, docs, and two known-issue entries."
description: "Split the three oversized functions in check_output_drift.py along their own seams and moved body comments into docstrings; the largest function went from 123 to 27 lines and no function scores 8 or more on cyclomatic complexity. Exit codes and every stderr line are unchanged. Added BP-100k-3-iv (a drifted recorded output with a grounded registry entry is reported as DIRECT-DRIFT: EXEMPT and does not block), BP-100k-3-v (the exemption is per key and needs a non-blank ground) and BP-100k-3-vi (a missing or unreadable recorded output is never excused). All three are retrofits: they describe behaviour that already shipped. Tagged the five existing tests with covers tags, tightened the declared-key test so key and ground must share a line and the key must not also appear as UNCOMPARABLE: EXEMPT, and added a five-test regression guard for -vi. Documented the new verdict in the drift-gate docs, filed two known issues (the registry-widening and double-counting question, and an inaccurate staged-file claim in build-drift-hook.md), and recorded a second occurrence of KI-CG-20260831-manifest-shadowing."
---

## Entry
