---
title: "KI-ACD-20260925-contract-target-is-parent-link — generated tickets name the parent AC as the documentation-expert's target document"
description: "medium — the ticket generator takes the first doc_links entry containing a slash as the documentation target, ignoring relationship; the BA writes the parent link first, so every generated child ticket's documentation contract targets an approved AC YAML with genre '(unspecified genre)', and documentation-verifier then blocks or the doc lands in the wrong place."
type: reference
category: reference
status: active
created: '2026-09-25'
last_updated: '2026-09-25'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/ac-driven-dev/open-high-ki-acd-002.md
---

# KI-ACD-20260925-contract-target-is-parent-link — generated tickets name the parent AC as the documentation target

- **Severity:** medium. `documentation-verifier` catches it (fail-closed), but every affected ticket
  needs a hand correction first.
- **Status:** open — no AC.
- **Occurrences:** 3 observed on 2026-09-25: GE-120f-1, GE-120f-1-i and GE-120f-1-ii. On
  GE-120f-1 it produced a `documentation-verifier` blocker. Structural: reachable for every AC whose
  first doc_link is its parent.
- **Where:** `scripts/ac_store/_gtfa_doc_genre.py:_extract_doc_path` (target selection) and
  `scripts/ac_store/_gtfa_contracts.py` (renders `- [ ] AC-N: <genre> | <doc_path> | ...`).

## Symptom

A generated ticket's `### documentation-expert` block reads, for example:

```
- [ ] AC-1: (unspecified genre) | docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120f-1.yaml | ...
```

The target is the parent acceptance criterion. That is an approved record in the store, not a
document the phase is meant to write.

## Mechanism

`_extract_doc_path` returns the first `doc_links` entry whose `path` is a local string containing a
`/`. It never reads `relationship`. BA-authored child ACs list `relationship: parent` first, so
the parent YAML always wins. The genre falls back to the `(unspecified genre)` marker, because
nothing in the record states one.

## Consequence

The documentation-expert is pointed at a file it must not edit. If it complies, it rewrites an
approved AC. If it doesn't, `documentation-verifier` finds no diff on the named target and blocks.
Either way the ticket needs a hand correction before the phase can pass.

## Fix direction

Exclude `relationship: parent`, and any path under `docs/acceptance-criteria/`, from target
selection. When no qualifying link remains, use the existing computed default under
`docs/<genre>/`. Add a regression test with a parent-first `doc_links` list.
