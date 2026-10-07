---
title: "Fix: file-size refusal message now states the two-for-one shrink obligation it enforces (GE-127f-4)"
date: "2026-10-07"
time: "14:18"
type: manual
components: 
  - commit_guardian
summary: "The commit guardian's oversized-file warning now tells you the real shrink requirement instead of a weaker one that still got your commit refused."
description: "check_file_size.py enforced max(limit, previous_length - added) all along, requiring roughly two lines removed per line added once a file is over its cap, but the refusal prose described a one-for-one rule (remove at least as many lines as you add), so an author who satisfied the printed advice was still refused. Replaced only the two misleading sentences in _print_grown_file; the arithmetic in both _print_grown_file and _classify_file is byte-for-byte unchanged, as are all printed figures. Adds unit_tests/commit_guardian/test_ge_127f_4.py (3 tests against the real installed hook, 2 of them a deliberate scope fence) and AC GE-127f-4."
commits: 
  - 61c8ed7b
---

## Entry
