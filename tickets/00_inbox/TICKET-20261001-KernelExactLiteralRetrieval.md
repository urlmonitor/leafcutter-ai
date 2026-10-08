---
title: "Kernel: a quoted literal in the goal is searched exactly, not only ranked"
status: todo
components:
  - decision_kernel
created: 2026-10-01
depends_on: []
priority: normal
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
last_updated: 2026-10-01
agents:
  python-coder: needed
  commit: needed
---

# Kernel: a quoted literal in the goal is searched exactly, not only ranked

## Actor / Goal
In order to answer "where is X applied" questions, we need retrieval to find files that contain an exact quoted string, identifier or message from the goal, alongside the ranked search.

## Context
- **Evidence:** run `run-fc88b0ad3e0a4fe8` asked where the check with the quoted message 'named_options is set by the kernel only' is applied. Retrieval never surfaced `kernel/contracts/schema_catalog.py`, which contains that exact string, nor the validators that call it. The answer judgements were 0.33 and 0.34, coverage partial.
- Ranked (lexical plus rerank) search treats the literal as a bag of words, so a long quoted message is out-weighed by common terms.

## Scope (no acceptance criteria by user decision)
- A quoted literal (or an exact identifier or message) in the goal becomes an exact-match search or a pinned locator alongside the ranked search; its hits are kept in the candidate pool and cited as evidence.
- Hits are reported as exact matches, never silently merged into ranked scores.

## Out of Scope
- Re-recording the retrieval benchmark: it scores a pinned corpus (`TICKET-20261001-KernelBenchmarkPinnedCorpus`), so ranking changes show up in its ratchets.

## Comments

### 2026-10-01 12:00 — python-coder (status: ok)
feedback-id: fb_2026-10-01_a0dc6e48
Ticket written only; no code changed.
