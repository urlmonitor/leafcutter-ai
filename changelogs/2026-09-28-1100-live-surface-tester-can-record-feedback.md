---
title: "live-surface-tester can record feedback"
date: "2026-09-28"
time: "11:00"
type: manual
components:
  - knowledge_system
  - ac_store
summary: "live-surface-tester is now an allowed writer for the six general feedback categories, the same fix #927 made for the two AC gate agents. Also records KI-ACS-20260928: the done-proof pytest rootdir walk has no upper bound."
description: "config/feedback_categories.yaml and its template did not list live-surface-tester in any allowed_writers list, so submit_feedback.py rejected every category it tried. It is added to complete, knowledge-gap, tooling-issue, convention-ambiguity, blocker and success-pattern, matching documentation-verifier. New KI-ACS-20260928: _resolve_pytest_run_cwd walks up to the filesystem root, not the project root, so a pytest config above the project could become the done-proof test run's cwd (not reproduced; found in the PR #925 review)."
commits:
breaking: false
---

## Entry

The live-surface test agent can now record feedback when it signs off. Before this, every attempt
was rejected, so its findings never reached the feedback trend reports.
