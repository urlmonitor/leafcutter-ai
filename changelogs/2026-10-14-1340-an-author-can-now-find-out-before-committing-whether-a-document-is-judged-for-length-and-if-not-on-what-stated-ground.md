---
title: "An author can now find out before committing whether a document is judged for length and, if not, on what stated ground"
date: "2026-10-14"
time: "13:40"
type: manual
components: 
  - commit_guardian
  - doc_compliance
  - documentation_system
summary: "Added a reference page that tells authors whether a document is length-checked and, where it is not, the stated reason, with no change to how the doc-length gate behaves."
description: "Delivers GE-127g-4 with documentation only; no gate code changes and no behaviour change ships. New docs/reference/document-length-standard.md (type: reference), a one-line pointer in docs/pre-commit-hooks.md, and an index row in docs/reference/README.md. GE-127g-4 and its parent GE-127g are marked done."
breaking: false
---

## Entry

Delivers GE-127g-4: an author can find out before committing whether a document is judged for length and, if not, on what stated ground. Documentation only. No gate behaviour changes.

- `docs/reference/document-length-standard.md` (type: reference) is new. It states:
  - the configured limits: 300 lines, 400 for a decision record under `docs/architecture/adrs/`, and 25 top-level sections;
  - that a document in no declared location is judged;
  - the three declared set-aside locations (`docs/agents/cards/`, `docs/roadmap.md`, `docs/INDEX.md`), each with its ground, phrased as the property that earns it (regenerated whole, no human author decides its length) rather than as the generator's name;
  - that adding a document to a declared directory needs no declaration change;
  - each location's own report size (1500, 1500, 2000), and that a document above it is reported while the commit still completes;
  - that declaring a location requires both a ground and a report size;
  - what each kind of run prints;
  - what happens when the declaration cannot be read.
- `docs/pre-commit-hooks.md` gains a one-line pointer to the new page, and its `last_updated` date is updated.
- `docs/reference/README.md` gains an index row for the new page.
- Every factual claim in the new page was checked by an independent reviewer that ran the gate against throwaway repositories. The corrections it found were applied before commit:
  - the above-bound report shows only on a completing run;
  - configured limits, not hard-coded ones, apply when the declaration is unusable;
  - the printed headroom is a signed number.
- GE-127g-4 is marked done. With every child of GE-127g now done, GE-127g is marked done too.
