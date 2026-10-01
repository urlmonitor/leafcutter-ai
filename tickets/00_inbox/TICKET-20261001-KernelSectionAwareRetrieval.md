---
title: "Kernel: section-aware retrieval with multiple windows per file"
status: todo
components:
  - decision_kernel
created: 2026-10-01
depends_on: []
priority: medium
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - retrieval
  - later-stage
last_updated: 2026-10-01
agents:
  commit: needed
---

# Kernel: section-aware retrieval with multiple windows per file

## Actor / Goal
In order to get evidence from the part of a document that answers the question, we need the
native text retrieval to understand headings and to return more than one window per file, so that
long documents (ADRs, design parts) are read where they say the relevant thing, not only where
the query words are densest.

## Context
Dogfood runs showed two limits of the one-window-per-file lexical search:
- Only ADR-057 sections 1 and 2 were read. Section 9 and the Alternatives section, which carry
  the decision's consequences, were missed because the densest term window sat elsewhere.
- The lexical pre-filter missed `kernel/persistence/*`: only 20 of about 511 candidate files
  survived `max_candidates`, chosen by raw hit count, so a relevant package was never offered to
  the relevance judgement.

Governing text: Rev 3 spec sections 10.2 and 10.3 (sources bounded and inspectable; every result
carries source, location, revision, hash and truncation); Stage 2 retrieval strategies guided by
measurements rather than mandatory embeddings.

## Scope (no acceptance criteria by user decision; later stage)
- Heading- or section-aware chunking for Markdown (and a sensible fallback for other text):
  candidates are sections with their heading path in the locator, not one densest window per file.
- Several windows per file when more than one section matches, bounded per file and overall, with
  the existing excerpt caps, line-aware cuts and truncation marks.
- A pre-filter that does not drop whole packages: per-directory or per-source fairness before the
  `max_candidates` cut, with a limitation naming how many files were not offered.
- Measurements on this repository (files scanned, candidates, time) recorded with the change, so
  the choice stays guided by data.

## Out of Scope
- Embeddings and semantic search.
- Structured-store field queries (a separate ticket).

## Comments
