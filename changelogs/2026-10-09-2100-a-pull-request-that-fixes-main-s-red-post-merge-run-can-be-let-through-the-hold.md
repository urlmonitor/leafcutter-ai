---
title: "A pull request that fixes main's red post-merge run can be let through the hold"
date: "2026-10-09"
time: "21:00"
type: manual
components: 
  - testing_quality
summary: "The Post-merge suite status check now lets a pull request through while main is red when its description says it closes the open post-merge-red issue and a passing fix-proof run exists for its current commit."
description: "While main's post-merge suite is red, every pull request is held. A pull request that is itself the fix can now be let through: its description must say it closes the open post-merge-red issue (for example \"Fixes #12\", in this repository, outside comments, code and quotes), and a fix-proof run must have passed on its current commit after the red run finished. A label, title or commit message never counts, and a new push needs a new proof. When the exemption is granted the check says so and records it once on the notice issue; when it is not, the check says what was missing. The description is read only to find the issue number and is never shown or passed to a shell. The fix-proof run itself is added by a later change, so until then a declared fix is still held."
---

## Entry
