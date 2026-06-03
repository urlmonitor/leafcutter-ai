---
description: >
  Analyse accumulated agent feedback and return a prioritized, actionable
  summary. Dispatches the feedback-analyst agent against feedback.jsonl.
---

Invoke the `feedback-analyst` agent with the user's arguments: $ARGUMENTS

<!-- Usage:
  /feedback-report
    Run a full report across all feedback data with no filters.

  /feedback-report --since 2026-05-01
    Only include feedback entries from 2026-05-01 onward.

  /feedback-report --until 2026-05-31
    Only include feedback entries up to 2026-05-31.

  /feedback-report --since 2026-05-01 --until 2026-05-31
    Restrict to a specific date window.

  /feedback-report --category tooling-issue
    Limit the report to the tooling-issue category only.

  /feedback-report --trend week
    Include week-over-week trend indicators (rising/stable/falling) per category.

  /feedback-report --format json
    Return the report as a JSON object (useful for scripting or downstream tools).

  /feedback-report --since 2026-05-01 --trend week --format json
    Combine multiple flags freely.

Pass-through flags (forwarded to trend_report.py):
  --since YYYY-MM-DD     lower date bound (inclusive)
  --until YYYY-MM-DD     upper date bound (inclusive)
  --category <id>        restrict to one feedback category
  --trend week|month|none  emit trend indicators (default: none)
  --format text|json     output format (default: text)
-->
