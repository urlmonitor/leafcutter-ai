---
title: "Kernel: structured-source adapter that queries YAML/JSON stores by field"
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
  - stage-2
last_updated: 2026-10-01
agents:
  commit: needed
---

# Kernel: structured-source adapter that queries YAML/JSON stores by field

## Actor / Goal
In order to get options and evidence that are representative of a project's stores rather than a
lexical sample, we need a generic structured-source adapter that can query YAML and JSON stores by
field (for example priority, readiness, work status or roadmap phase), configured per source in
project metadata, so that a decision such as "which acceptance criterion should be implemented
next" is grounded in the real distribution of the store.

## Context
Live round 3 of the Decision Kernel V0 (decision goal "Decide which acceptance criterion is most
critical to implement next", trace `bbea7cd71bae46bbdbf6d4f46780b691`) showed the limit of lexical
`repo_text` retrieval over a structured store:
- 20 of about 4,460 acceptance-criteria files were picked by wording overlap with the question;
  the candidate list says nothing about how the rest of the store looks.
- The excerpts carried no priority, readiness or `work_status` data, so options and their
  justification could not be ranked on what actually matters.
- The current roadmap phase was not surfaced, although `docs/roadmap.json` names it.

Governing text: Rev 3 spec section 17, Stage 2 ("the same kernel can supply a compact evidence
package before a reasoning/coding model is called, using both structural and semantic retrieval
where justified"), sections 10.2 and 10.3 (sources come from project metadata; every result carries
source, location, revision, hash and truncation), and ADR-053 (deterministic first).

## Scope (no acceptance criteria by user decision; later stage)
- A source kind for structured stores (YAML and JSON files, one record per file or per list entry)
  whose field mapping and queries are declared per source in the kernel configuration, never in
  code: which fields exist, which are filterable, how to order and how many records to take.
- Field queries (for example `work_status != done`, highest `priority`, a given roadmap phase),
  returning a bounded, ordered sample plus a summary of the store (counts per field value), with
  the usual evidence shape: locator, revision, content hash, truncation, and a limitation when the
  sample is partial.
- Domain-agnostic: no acceptance-criteria or roadmap logic in the kernel; the same adapter serves
  any project that describes its stores in configuration.
- Keeps the read-only, deny-glob and size-limit rules of the native retrieval adapter.

## Out of Scope
- Embeddings and semantic retrieval (a separate Stage 2 decision, guided by measurements).
- Write access to any store.

## Comments
