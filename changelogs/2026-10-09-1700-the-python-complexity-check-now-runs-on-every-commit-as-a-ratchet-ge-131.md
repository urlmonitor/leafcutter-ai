---
title: "The Python complexity check now runs on every commit, as a ratchet (GE-131)"
date: "2026-10-09"
time: "17:00"
type: manual
components: 
  - commit_guardian
  - precommit_hooks
  - ac_store
summary: "Commits that make a Python function more complex than allowed are now refused, while functions that are already too complex can be edited as long as they do not get worse."
description: "Behaviour change: check-complexity is now registered in hooks_manifest.hooks (commit_guardian.json) and runs on every commit; until now it was never registered, so it never ran even though the README listed it as Blocking. Rule: a changed function may stay at or below the greater of complexity.max_score (default 15) and its own previous committed score (highest across HEAD and any MERGE_HEAD parent); a new function, or one crossing the limit, is held to the limit. Functions already over the limit (109 in this repo when measured) do not block an unrelated or improving commit; they are refused only if their score rises. A refusal names the file, the function, its score, the ceiling applied and the reason (new, grew or crossed), and points to the complexity-reduction skill. Known limitation: a pure move or rename of an unchanged function is currently refused because functions are keyed by qualified name; commit it with SKIP=check-complexity (the refusal output says so). Keeping the score across renames is a deliberate follow-up, not part of this change. A file that cannot be read, decoded or parsed is now reported as could not check, naming the file, instead of silently passing. The README row and the complexity-reduction skill now describe the check as registered and state the rule. GE-131 is complete: GE-131a-1, -2, -3, GE-131a and GE-131 are all marked done, and every acceptance criterion has passing tests (test_ge_131a_1.py, test_ge_131a_2.py, test_ge_131a_3.py). Commits: 51c386618 ratchet (_complexity_ratchet.py, check_complexity.py); ab46caa02 registration; ced744792 and bcf3493f8 docs and docs wording test; 8f2f36ccc and bda6843a3 ticket lifecycle."
commits: 
  - 51c386618
  - 8f2f36ccc
  - ab46caa02
  - bda6843a3
  - ced744792
  - bcf3493f8
breaking: false
---

## Entry
