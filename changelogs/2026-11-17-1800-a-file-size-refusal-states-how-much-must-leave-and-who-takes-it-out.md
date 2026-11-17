---
title: "A file-size refusal states how many measured lines must leave the file and whether the author or a restructuring specialist takes them out"
date: "2026-11-17"
time: "18:00"
type: manual
components:
  - commit_guardian
  - ac_store
summary: "GE-127f-3. Both check-file-size refusal printers now state the demand (measured lines that must leave) and its disposition: at most 5 lines the author may take out inside the change, more is handed to a restructuring specialist. GE-127f-3, GE-127f, GE-127 and INF-800f are marked done."
description: >-
  templates/scripts/commit_guardian/check_file_size.py gains AUTHOR_CLEARABLE_DEMAND
  (5) and _print_demand, called from _print_grown_file (demand = new length less
  max(limit, previous - added)) and _print_too_large_file (demand = length less the
  limit). The party named follows from the size of the demand alone. The comparison
  in _classify_file is unchanged, so any addition still engages the rule. The hook
  prints no refusal record and the check-file-size remedy declaration still names
  python-coder, so no run acts on the disposition yet. New tests run real git commits
  through a single-hook pre-commit fixture: unit_tests/commit_guardian/test_ge_127f_3.py
  (criterion, boundary on both refusal paths, discrimination, deployed copy from the
  shared reference layout) and test_ge_127f_3_mutations.py (THE LOOPHOLE and THE BAND
  injections). AC store: GE-127f-3 done with covered_by and implemented_by; its parent
  GE-127f and the root GE-127 done (every child done); INF-800f given work_status done
  (its only child INF-800f-1 is done). Readiness is
  left at draft on every record. The untagged-done count stays at 162.
breaking: false
---

## Entry
