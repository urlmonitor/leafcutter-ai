---
title: "Known Issues: Feedback Collector"
description: "Agents absent from a category's allowed_writers list cannot submit feedback at all; the failure is silent and the agent's whole feedback history is missing from the corpus."
type: reference
status: active
created: 2026-08-19
last_updated: 2026-08-19
components:
  - feedback_collector
related_docs:
  - templates/skills/signoff/SKILL.md
  - docs/architecture/agent_knowledge_system.md
---

# Known Issues: Feedback Collector

## KI-FC-1 — `ac-validator` cannot submit feedback in any category

**Severity: medium.** Silent, and it invalidates the corpus rather than just
losing one record.

`ac-validator` is absent from `allowed_writers` in
`config/feedback_categories.yaml`. `submit_feedback.py` therefore rejects it for
**every** category, and the agent falls back — correctly, per the `signoff`
skill — to recording `feedback-id: (submit-failed)` and continuing, because a
failed submit is explicitly not a phase failure.

Found on 2026-08-19 when `ac-validator` signed off `GE-122e-2` and reported that
every category had been refused.

**Why this is worse than a lost record.** It is not intermittent. Every
`ac-validator` run since the allowlist was written has contributed **nothing**,
so any analysis of the feedback corpus silently under-represents AC-coverage
findings — and reads as "ac-validator rarely has anything to report" rather than
"ac-validator has never been able to report".

This is the same shape as the other silent-gate defects in this register: exit
0, a fallback that keeps the pipeline moving, and no signal that a capability is
entirely absent.

**Detection.** Grep the corpus for the agent name; an agent with zero entries
across many runs is the tell. Or check membership directly:

```bash
grep -n "allowed_writers" -A 20 config/feedback_categories.yaml
```

**Suggested fix.** Add `ac-validator` to the appropriate categories. More
usefully, add a startup or build-time consistency check that every agent with
`signoff: true` in the registry appears in at least one category's
`allowed_writers` — the general defect is that the two lists can disagree with
nothing noticing.
