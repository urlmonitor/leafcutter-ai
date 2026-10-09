---
title: "Feedback-sink ACs enriched for build: one declared log root for every workspace"
date: "2026-10-09"
time: "16:00"
type: manual
components: 
  - feedback_collector
  - infrastructure
summary: "IT PO enrichment of INF-500d-4 (reports outlive their workspace) and INF-500d-4-i (refuse loudly when the enduring location is unknown), plus six new child ACs. The adopted mechanism is the knowledge plane's build-time declared absolute path, extended to every log in debugging/logs, not the git-common-dir rule in the notes. AC store only; no code changes."
description: "One content commit (698d93ea9), AC store only. INF-500d-4 and INF-500d-4-i gain assigned_agent, estimated_complexity, it_requirements, test_spec, doc_links, contracts and an amended_by entry, and move from readiness draft to reviewed. Criteria and notes are unchanged. The it_requirements record that rule (c)'s git-common-dir anchor is superseded by the build-time declaration in config/knowledge_sink.json, extended with operational_log_root and feedback_sink, for the reasons INF-400c-4 rejected git-common-dir on 2026-09-07. Six child L3s (origin_agent BrainCandy, readiness reviewed) split the work by agent boundary: INF-500d-4-iii build declaration and worktree-bootstrap inheritance, -iv writers, -v readers, -vi prompt surfaces, -vii reference docs, -viii component diagram. Migration is explicitly none, with reports/feedback-snapshots/ as the accepted one-off rescue. The BO-100d probe criteria are flagged for their owner and not edited."
commits: 
  - 698d93ea9
breaking: false
---

## Entry

The feedback-sink ACs are enriched and ready for BrainCandy's readiness review.

- **Mechanism.** Every log in `debugging/logs/` resolves from one absolute root fixed at
  build time in `config/knowledge_sink.json`, the declaration the knowledge sink already
  uses, now extended with `operational_log_root` and `feedback_sink`. Nothing discovers
  the root at run time. The notes' `git rev-parse --git-common-dir` rule is recorded as
  superseded, for the reasons INF-400c-4 rejected it.
- **INF-500d-4** gets the three-rule constraint, the end-to-end tests and the sequencing.
  **INF-500d-4-i** maps "cannot be determined" to a missing, unreadable or stale
  declaration, and requires a loud refusal with no fallback.
- **Six new child ACs** (`INF-500d-4-iii` to `-viii`) split the work across build and
  worktree bootstrap, writers, readers, prompt surfaces, reference docs and the
  component diagram.
- **Migration: none.** `reports/feedback-snapshots/` is the one-off rescue.
- **BO-100d** pre-drive probe criteria name a relative path. They are flagged for their
  owner and were not edited.

No code changes.
