---
title: "Spec only: a frontmatter path entry now has a declared shape, and two readers agree on it (GE-118d, KM-KGS-100d-3)"
date: "2026-09-21"
time: "12:40"
type: manual
components: 
  - commit_guardian
  - knowledge_management
summary: "Specified (but did not yet build) the fix for an open blocker where a document's cross-reference entry can crash the commit checker, and found that the same entry can also silently vanish from the knowledge graph instead of erroring — a second consumer the original bug report never mentioned."
description: "Seven acceptance criteria (GE-118d, GE-118d-1, GE-118d-2, GE-118e, GE-118f, KM-KGS-100d-3, KM-KGS-100d-3-i) specify the fix for KI-CG-008: both a bare path string and a single-key labelled mapping are accepted as related_docs/related_code/architecture_diagrams entries, an unaccepted shape is refused by name with no traceback, a multi-key mapping is refused rather than resolved by guesswork, and both the commit-guardian frontmatter guard and the knowledge-graph edge builder resolve an entry through one shared routine so a declined entry is named and counted rather than disappearing. No code changed in this commit — AC store only."
commits: 
  - cbdbfb99
breaking: false
---

## Entry

### What this is

Seven acceptance criteria for `KI-CG-008`, an open blocker reported by adopter DIAGraph.
**No code changed** — this is a specification-only commit, and the defect it describes is
still live in both places it occurs.

### The register named one defect; there are two

A document's frontmatter may carry `related_docs`, `related_code`, or
`architecture_diagrams` entries. The package has never declared what shape an entry takes,
and two are in the wild: a bare path string (this repo's convention) and a single-key
labelled mapping (the dominant convention in the reporting adopter — at least 33 of its 50
such documents).

The known-issue register reports that the mapping form crashes
`check-doc-frontmatter` with `TypeError: unsupported operand type(s) for /: 'PosixPath'
and 'dict'`, because `validate_paths()` guards that the *field* is a list and never that
its *elements* are strings.

Sizing the fix turned up a second consumer the register does not mention.
`config/paths.json` declares `related_docs` as an edge field for three surfaces, so the
knowledge graph reads the same field, and `scripts/knowledge_query.py`'s `extract_edges()`
silently skips any entry that is not a bare string. No crash, no message, no edge — the
relationship just never appears in the graph. Same input, same missing declaration,
opposite failure mode: one loud, one invisible.

### What is now specified

- **`GE-118d`** — both shapes resolve, across all three path fields.
- **`GE-118d-1`** — an unaccepted shape is refused *by name*, with no traceback, and the
  remaining entries and fields are still checked.
- **`GE-118d-2`** — a multi-key mapping is refused rather than resolved by guesswork
  (taking the first value or taking every value are both rejected outcomes).
- **`GE-118e`** — the accepted shapes are written down where an author actually reads them,
  replacing a hooks-guide sentence that describes the guard as checking only path
  existence.
- **`GE-118f`** — the commit-guardian guard and the knowledge-graph edge builder resolve an
  entry through **one shared routine**, so admitting a further shape later is a single edit
  both consumers inherit.
- **`KM-KGS-100d-3`** — a labelled entry produces the same edge the bare form would.
- **`KM-KGS-100d-3-i`** — a declined entry is named and counted beside the edge count,
  rather than just vanishing.

Both shapes are accepted deliberately: the package never declared a rule, so neither
corpus is in violation of one, and rejecting either shape breaks a large fraction of real
documents with no migration path. A multi-key mapping is refused rather than accepted,
because both plausible readings of "which value is the path?" fail invisibly — one
silently drops a relationship, the other makes the guard and the graph disagree about how
many relationships a document declared.

### Why it matters that this is spec-only

The crash is still live in `frontmatter_validators.py`, and the silent drop is still live
in `knowledge_query.py`. This commit makes both failure modes testable and gives an
implementer one place to build the fix, but nobody should read it as the bug being closed.
