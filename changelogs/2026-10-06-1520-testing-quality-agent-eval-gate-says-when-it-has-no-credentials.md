---
title: "Testing quality: the agent-eval gate says when it has no model credentials, and runs only for the agents' own files"
date: "2026-10-06"
time: "15:20"
type: manual
components: 
  - testing_quality
summary: "The agent-eval check now fails with an explicit no-credentials message instead of a blank zero score, and stops firing on unrelated PRs."
description: "The repository has no model API secret, so every eval row exited with an empty error and scored zero, and since the triggers were widened on 2026-10-05 this happened on most PRs. By owner decision (2026-10-06) the gate stays informational with no model spend: a preflight now fails up front with an explicit no-model-credentials message and reports no score; a CLI failure with empty stderr now carries the CLI's own result text; and the flow-author and mock-data-author triggers are back to the agents' own files, so a PR that only edits acceptance criteria, analysis docs or kernel code no longer runs them. Known issues KI-TQ-002 (required-check list corrected), KI-TQ-20260907 and KI-TQ-20260908-0900 are updated. Ticket: AgentEvalGateHonestAboutCredentials (2026-10-06)."
commits: []
---

## Entry
