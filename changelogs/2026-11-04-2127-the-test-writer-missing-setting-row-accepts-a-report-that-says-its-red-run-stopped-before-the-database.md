---
title: "The test-writer missing-setting row accepts a report that says its red run stopped before the database"
date: "2026-11-04"
time: "21:27"
type: manual
components: 
  - testing_quality
summary: "New assertion kind report_says_stopped_before_database for the test-writer missing-setting-database-work row; resolves KI-TQ-20261102-test-writer-rows-check-unrequested-report-wording."
description: "TQ-200d-4-vi. The test-writer row missing-setting-database-work now checks report_says_stopped_before_database instead of report_says_not_run. The new kind accepts a report that quotes the required red verification run and says the database tests stopped before any connection (or were not run), and fails a report claiming the database tests ran or connected. report_says_not_run and the test-runner set are unchanged. Reference entry and evals README bullet added; the shared known issue KI-TQ-20261102-test-writer-rows-check-unrequested-report-wording is resolved (with TQ-200d-1-vi). Tests in unit_tests/evals/tq200d4vi/."
breaking: false
---

## Entry
