---
title: "The drift-exempt counting question is recorded as a decision instead of a comment"
date: "2026-10-09"
time: "10:10"
type: manual
components: 
  - commit_guardian
summary: "ADR-068 records how a drift-exempt output should be counted in the drift gates summary line, and the two known-issue entries it bears on are brought up to date."
description: "check-output-drift counts a drift-exempt recorded output in both verified and uncomparable. ADR-068 (status Proposed) records the decision and recommends giving it a separate drift_exempt field and a RESULT column appended last, rather than leaving the double count. The decision is not a cosmetic one: two existing tests already assert population identities the current counting violates, and they pass only because no live registry entry names a recorded output yet, so the first person to write one would see a failure message naming a different and far worse defect. KI-CG-20261008 previously said no such ADR existed and now links to it. KI-CG-022, open since August because the ADR number-collision hook is registered nowhere, records a second occurrence: the hook is still unregistered, its prescribed pre-flight reports a blocking verdict when run from outside the git work tree because its staged-file read inherits the process directory, and the required unclaimed-number audit scans whatever directory it starts in. No code or gate behaviour changed."
---

## Entry
