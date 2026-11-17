---
title: "ACs: no comment counts toward a file's length, in any style (GE-127d-3 to -5)"
date: "2026-10-20"
time: "15:00"
type: manual
components: 
  - commit_guardian
summary: "Authors the acceptance criteria for a lexically correct, comment-blind check-file-size measure, a backstop against restyle gaming on over-limit files, and the matching refusal advice and published rule. Criteria only; no code changes."
description: "New L2s GE-127d-3, GE-127d-4 and GE-127d-5 under GE-127d, with L3s GE-127d-3-i to -iv. They record BrainCandy's decisions of 2026-10-16 and 2026-10-20. No comment counts in any style (#, //, --, /* */). A Python string that stands alone as a statement (docstrings, bare strings, a trailing DECISION HISTORY block) is not counted either. A string that is assigned, passed, returned or part of a larger expression counts as code, and so does a standalone f-string. Blank lines outside comments still count. Each language is measured with a tokenizer, so a comment marker inside a string is code (GE-127d-3-i). A file that cannot be tokenized is INDETERMINATE (GE-127d-3-ii). The previous version is re-measured with the new rule, so no file is refused just because the rule changed (GE-127d-3-iii). Restyling comments adds 0 lines to the two-for-one repayment (GE-127d-3-iv). A change that shrinks the measured length while raising the raw line count is refused only for files already over their limit (GE-127d-4). The refusal advice and the published rule surfaces state the new rule, and the rule-parity gate compares the measurement rule (GE-127d-5). These ACs target KI-CG-20261013 (the measure can be gamed by comment style) and KI-CG-20261009 (/* inside strings). GE-127d lists the new children and is reopened to todo. GE-127d-2 records amendment notes."
breaking: false
---

## Entry
