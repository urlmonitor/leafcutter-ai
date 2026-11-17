---
title: "A failed feedback submission records why it failed"
date: "2026-11-16"
time: "19:00"
type: manual
components:
  - feedback_collector
  - supervisor_system
summary: "submit_feedback.py now prints one machine-readable line naming the reason on every failure, and the agent instructions record that reason in the sign-off instead of a bare (submit-failed)."
description: "A new vocabulary file, templates/scripts/feedback/submit_failure_reasons.json, names five failure reasons: writer-not-allowed, malformed-submission, facility-unavailable, destination-unwritable and written-uncited. On every failure exit, submit_feedback.py prints one stderr line, submit-failed:<reason>:<category>, keeping stdout empty and the exit non-zero. No failure path ends in a traceback any more, including an empty or unparseable categories file, a categories entry without an id, an unwritable --jsonl parent and a full device. The signoff skill, the shared sign-off block and the python-coder, documentation-verifier, user-surface-smoker, ticket-supervisor, epic-supervisor and live-surface-tester instructions read that line back from the run's own error file. They record feedback-id: (submit-failed:<reason>:<category>) by one fixed precedence, and never take a recovery file their own error file does not name. epic-supervisor no longer discards its error stream, and ticket-supervisor no longer describes a submission it gives no command for. INF-500d-4-i's tests count only human-readable refusal lines, so the new line does not loosen them (INF-500d-3, -iv, -v, -vi)."
breaking: false
---

## Entry
