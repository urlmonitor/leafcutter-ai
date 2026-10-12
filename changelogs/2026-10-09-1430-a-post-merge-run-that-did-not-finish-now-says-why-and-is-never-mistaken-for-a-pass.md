---
title: "A post-merge run that did not finish now says why, and is never mistaken for a pass"
date: "2026-10-09"
time: "14:30"
type: manual
components: 
  - testing_quality
summary: "When the post-merge suite fails to finish, its verdict now names where it stopped, keeps tests that failed to load apart from tests that failed, and still records a result when the run is cancelled."
description: "An incomplete post-merge run now gets one named reason: setup failed, tests failed to load, nothing was selected, the run was cancelled or timed out, the result file was unreadable, the retry broke, or the cause is unknown. Tests that fail to load are listed separately from tests that failed, so a broken import is not reported as a failing test. The verdict job and all its steps now run even when the workflow is cancelled, so a cancelled run still leaves a did-not-complete verdict. When no verdict file exists at all, the outcome is read from the run's own conclusion instead, and a notice for an incomplete run says 'not green since' and the reason, never 'red'. A green verdict file left beside a cancelled run is treated as did-not-complete rather than as a pass, and a missing job result is treated as unknown rather than as success."
---

## Entry
