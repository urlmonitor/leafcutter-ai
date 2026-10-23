---
title: 'EPIC: Every screen says which requirement it is showing you'
type: epic
epic_name: EPIC-EveryScreenSaysWhichRequirementItIs
created: 2026-10-23
status: in_progress
components:
- ac_store
- build_pipeline
- commit_guardian
- documentation_system
- frontend_coding
- knowledge_management
- precommit_hooks
- testing_quality
- ux_prototyping
source_ac: GE-124
depends_on: []
change_target:
- code
risk_surface:
- contract_boundary
requires_diagram: false
requires_adr: false
---
# EPIC-EveryScreenSaysWhichRequirementItIs

## Goal

This epic implements AC GE-124: Every screen says which requirement it is showing you. It consists of 49 ticket(s) generated from the leaf ACs beneath GE-124, assembled in topological build order with all inter-ticket dependencies derived from the AC depends_on graph.

## Tickets

| # | File | Title | Source AC | Depends On |
|---|------|-------|-----------|------------|
| 01 | [01_TICKET-20261022-GE-124a-1.md](./01_TICKET-20261022-GE-124a-1.md) | A component-level declaration block names the criteria the file serves | GE-124a-1 | — |
| 02 | [02_TICKET-20261022-GE-124a-1-i.md](./02_TICKET-20261022-GE-124a-1-i.md) | A file with no declaration block declares nothing and is recorded as missing the floor | GE-124a-1-i | 01_TICKET-20261022-GE-124a-1.md |
| 03 | [03_TICKET-20261022-GE-124a-1-ii.md](./03_TICKET-20261022-GE-124a-1-ii.md) | An element attribute never populates the file's declared criteria | GE-124a-1-ii | 01_TICKET-20261022-GE-124a-1.md |
| 04 | [04_TICKET-20261022-GE-124a-2.md](./04_TICKET-20261022-GE-124a-2.md) | The same declaration is expressible in each supported front-end file shape | GE-124a-2 | 01_TICKET-20261022-GE-124a-1.md |
| 05 | [05_TICKET-20261022-GE-124a-2-i.md](./05_TICKET-20261022-GE-124a-2-i.md) | A declaration written below the leading comment region does not satisfy the floor | GE-124a-2-i | 04_TICKET-20261022-GE-124a-2.md |
| 06 | [06_TICKET-20261022-GE-124a-3.md](./06_TICKET-20261022-GE-124a-3.md) | Only a file that renders markup counts as a screen component | GE-124a-3 | 01_TICKET-20261022-GE-124a-1.md |
| 07 | [07_TICKET-20261022-GE-124a-3-i.md](./07_TICKET-20261022-GE-124a-3-i.md) | A barrel file that only re-exports other components is out of scope | GE-124a-3-i | 06_TICKET-20261022-GE-124a-3.md |
| 08 | [08_TICKET-20261022-GE-124a-3-ii.md](./08_TICKET-20261022-GE-124a-3-ii.md) | Stories, tests and generated files are excluded by a named rule, not by directory guesswork | GE-124a-3-ii | 06_TICKET-20261022-GE-124a-3.md |
| 09 | [09_TICKET-20261022-GE-124a-4.md](./09_TICKET-20261022-GE-124a-4.md) | A how-to shows where the declaration goes in each front-end file shape | GE-124a-4 | 01_TICKET-20261022-GE-124a-1.md, 04_TICKET-20261022-GE-124a-2.md, 06_TICKET-20261022-GE-124a-3.md |
| 10 | [10_TICKET-20261022-GE-124b-1.md](./10_TICKET-20261022-GE-124b-1.md) | An element pin is read from the data-ac attribute and is optional | GE-124b-1 | 01_TICKET-20261022-GE-124a-1.md |
| 11 | [11_TICKET-20261022-GE-124b-1-i.md](./11_TICKET-20261022-GE-124b-1-i.md) | A CSS class is never read as a pin | GE-124b-1-i | 10_TICKET-20261022-GE-124b-1.md |
| 12 | [12_TICKET-20261022-GE-124b-1-ii.md](./12_TICKET-20261022-GE-124b-1-ii.md) | An empty or whitespace-only data-ac value is malformed, not absent | GE-124b-1-ii | 10_TICKET-20261022-GE-124b-1.md |
| 13 | [13_TICKET-20261022-GE-124b-2.md](./13_TICKET-20261022-GE-124b-2.md) | A pin says a thing is on screen and can never stand in for the component declaration | GE-124b-2 | 01_TICKET-20261022-GE-124a-1.md, 17_TICKET-20261022-GE-124c-1.md |
| 14 | [14_TICKET-20261022-GE-124b-3.md](./14_TICKET-20261022-GE-124b-3.md) | The pin is stripped from production builds and retained in dev, test and the Atlas | GE-124b-3 | 10_TICKET-20261022-GE-124b-1.md |
| 15 | [15_TICKET-20261022-GE-124b-4.md](./15_TICKET-20261022-GE-124b-4.md) | A how-to shows an author how to pin one element to one criterion | GE-124b-4 | 10_TICKET-20261022-GE-124b-1.md, 13_TICKET-20261022-GE-124b-2.md |
| 16 | [16_TICKET-20261022-GE-124b-5.md](./16_TICKET-20261022-GE-124b-5.md) | One reference doc holds the data-ac contract for all of its consumers | GE-124b-5 | 10_TICKET-20261022-GE-124b-1.md, 14_TICKET-20261022-GE-124b-3.md |
| 17 | [17_TICKET-20261022-GE-124c-1.md](./17_TICKET-20261022-GE-124c-1.md) | A changed screen component with no declaration blocks the commit by default | GE-124c-1 | 01_TICKET-20261022-GE-124a-1.md, 06_TICKET-20261022-GE-124a-3.md |
| 18 | [18_TICKET-20261022-GE-124c-1-i.md](./18_TICKET-20261022-GE-124c-1-i.md) | A file that lacks the floor while carrying element pins yields exactly one finding | GE-124c-1-i | 17_TICKET-20261022-GE-124c-1.md |
| 19 | [19_TICKET-20261022-GE-124c-2.md](./19_TICKET-20261022-GE-124c-2.md) | An id that resolves to nothing is reported as its own verdict, not as a missing declaration | GE-124c-2 | 01_TICKET-20261022-GE-124a-1.md, 10_TICKET-20261022-GE-124b-1.md, 17_TICKET-20261022-GE-124c-1.md |
| 20 | [20_TICKET-20261022-GE-124c-2-i.md](./20_TICKET-20261022-GE-124c-2-i.md) | One shared resolver answers 'is this a real criterion id' for all three traceability checks | GE-124c-2-i | 19_TICKET-20261022-GE-124c-2.md |
| 21 | [21_TICKET-20261022-GE-124c-2-ii.md](./21_TICKET-20261022-GE-124c-2-ii.md) | A check that cannot read the criteria store says so instead of passing | GE-124c-2-ii | 19_TICKET-20261022-GE-124c-2.md |
| 22 | [22_TICKET-20261022-GE-124c-3.md](./22_TICKET-20261022-GE-124c-3.md) | An unstaged file is not examined at all, and a fully declared change passes | GE-124c-3 | 17_TICKET-20261022-GE-124c-1.md |
| 23 | [23_TICKET-20261022-GE-124c-3-i.md](./23_TICKET-20261022-GE-124c-3-i.md) | One unreadable file does not block the rest of the commit, and is named | GE-124c-3-i | 22_TICKET-20261022-GE-124c-3.md |
| 24 | [24_TICKET-20261022-GE-124c-4.md](./24_TICKET-20261022-GE-124c-4.md) | A how-to tells a blocked author which of the two mistakes they made and how to clear it | GE-124c-4 | 17_TICKET-20261022-GE-124c-1.md, 19_TICKET-20261022-GE-124c-2.md, 22_TICKET-20261022-GE-124c-3.md |
| 25 | [25_TICKET-20261023-GE-124c-5.md](./25_TICKET-20261023-GE-124c-5.md) | A sequence diagram shows the ordering that keeps the four verdicts distinguishable | GE-124c-5 | 17_TICKET-20261022-GE-124c-1.md, 19_TICKET-20261022-GE-124c-2.md, 22_TICKET-20261022-GE-124c-3.md |
| 26 | [26_TICKET-20261023-GE-124d-1.md](./26_TICKET-20261023-GE-124d-1.md) | A named path can be put on the warn tier, and every path that is not stays blocking | GE-124d-1 | 17_TICKET-20261022-GE-124c-1.md |
| 27 | [27_TICKET-20261023-GE-124d-1-i.md](./27_TICKET-20261023-GE-124d-1-i.md) | No setting can put every path on the warn tier at once | GE-124d-1-i | 26_TICKET-20261023-GE-124d-1.md |
| 28 | [28_TICKET-20261023-GE-124d-2.md](./28_TICKET-20261023-GE-124d-2.md) | One file is excused by a written reason that lives in the file and shows up in the diff | GE-124d-2 | 17_TICKET-20261022-GE-124c-1.md |
| 29 | [29_TICKET-20261023-GE-124d-2-i.md](./29_TICKET-20261023-GE-124d-2-i.md) | An empty reason is refused and the file stays blocked | GE-124d-2-i | 28_TICKET-20261023-GE-124d-2.md |
| 30 | [30_TICKET-20261023-GE-124d-3.md](./30_TICKET-20261023-GE-124d-3.md) | An escape replaces a file's verdict — it never sits beside it | GE-124d-3 | 26_TICKET-20261023-GE-124d-1.md, 28_TICKET-20261023-GE-124d-2.md |
| 31 | [31_TICKET-20261023-GE-124d-4.md](./31_TICKET-20261023-GE-124d-4.md) | A how-to shows how to record an opt-out and how an area gets onto the warn list | GE-124d-4 | 26_TICKET-20261023-GE-124d-1.md, 28_TICKET-20261023-GE-124d-2.md, 30_TICKET-20261023-GE-124d-3.md |
| 32 | [32_TICKET-20261023-GE-124e-1.md](./32_TICKET-20261023-GE-124e-1.md) | The reverse gate fires only on screen criteria that are already finished | GE-124e-1 | — |
| 33 | [33_TICKET-20261023-GE-124e-2.md](./33_TICKET-20261023-GE-124e-2.md) | Either declaration surface satisfies the reverse gate | GE-124e-2 | 32_TICKET-20261023-GE-124e-1.md |
| 34 | [34_TICKET-20261023-GE-124e-3.md](./34_TICKET-20261023-GE-124e-3.md) | A finished screen criterion that nothing claims is reported against the criterion, not a file | GE-124e-3 | 32_TICKET-20261023-GE-124e-1.md, 33_TICKET-20261023-GE-124e-2.md |
| 35 | [35_TICKET-20261023-GE-124e-3-i.md](./35_TICKET-20261023-GE-124e-3-i.md) | The declaration gate and the test-proof gate fail independently on the same criterion | GE-124e-3-i | 34_TICKET-20261023-GE-124e-3.md |
| 36 | [36_TICKET-20261023-GE-124e-4.md](./36_TICKET-20261023-GE-124e-4.md) | The gate evaluates only the criteria the change touched | GE-124e-4 | 32_TICKET-20261023-GE-124e-1.md, 34_TICKET-20261023-GE-124e-3.md |
| 37 | [37_TICKET-20261023-GE-124e-5.md](./37_TICKET-20261023-GE-124e-5.md) | A how-to separates 'nothing claims this' from 'nothing proves this' for the person who hit the gate | GE-124e-5 | 32_TICKET-20261023-GE-124e-1.md, 33_TICKET-20261023-GE-124e-2.md, 34_TICKET-20261023-GE-124e-3.md, 36_TICKET-20261023-GE-124e-4.md |
| 38 | [38_TICKET-20261023-GE-124f-1.md](./38_TICKET-20261023-GE-124f-1.md) | A page root names the design it realises and that name resolves | GE-124f-1 | 10_TICKET-20261022-GE-124b-1.md |
| 39 | [39_TICKET-20261023-GE-124f-1-i.md](./39_TICKET-20261023-GE-124f-1-i.md) | Only the page root names a design — a leaf that names one is a defect | GE-124f-1-i | 38_TICKET-20261023-GE-124f-1.md |
| 40 | [40_TICKET-20261023-GE-124f-1-ii.md](./40_TICKET-20261023-GE-124f-1-ii.md) | A page with no design modelled for it is outside the chain, not a finding | GE-124f-1-ii | 38_TICKET-20261023-GE-124f-1.md |
| 41 | [41_TICKET-20261023-GE-124f-2.md](./41_TICKET-20261023-GE-124f-2.md) | Built page against approved design becomes a mechanical comparison, not a self-declared label | GE-124f-2 | 38_TICKET-20261023-GE-124f-1.md, 10_TICKET-20261022-GE-124b-1.md |
| 42 | [42_TICKET-20261023-GE-124f-3.md](./42_TICKET-20261023-GE-124f-3.md) | A test's selector and the criterion it claims to cover are checked against each other | GE-124f-3 | 10_TICKET-20261022-GE-124b-1.md |
| 43 | [43_TICKET-20261023-GE-124f-4.md](./43_TICKET-20261023-GE-124f-4.md) | A component diagram shows the chain across the four stores it crosses | GE-124f-4 | 38_TICKET-20261023-GE-124f-1.md, 41_TICKET-20261023-GE-124f-2.md, 42_TICKET-20261023-GE-124f-3.md |
| 44 | [44_TICKET-20261023-GE-124g-1.md](./44_TICKET-20261023-GE-124g-1.md) | A declaration is never written into a criterion's covered_by | GE-124g-1 | — |
| 45 | [45_TICKET-20261023-GE-124g-1-i.md](./45_TICKET-20261023-GE-124g-1-i.md) | No configuration anywhere can turn a declaration into coverage | GE-124g-1-i | 44_TICKET-20261023-GE-124g-1.md, 32_TICKET-20261023-GE-124e-1.md, 47_TICKET-20261023-GE-124g-3.md |
| 46 | [46_TICKET-20261023-GE-124g-2.md](./46_TICKET-20261023-GE-124g-2.md) | Passing the declaration gate never finishes a criterion, and never says it did | GE-124g-2 | 34_TICKET-20261023-GE-124e-3.md |
| 47 | [47_TICKET-20261023-GE-124g-3.md](./47_TICKET-20261023-GE-124g-3.md) | Declarations are counted on their own axis and never added into a coverage figure | GE-124g-3 | 44_TICKET-20261023-GE-124g-1.md |
| 48 | [48_TICKET-20261023-GE-124g-4.md](./48_TICKET-20261023-GE-124g-4.md) | A test that only finds the element does not cover the criterion | GE-124g-4 | 42_TICKET-20261023-GE-124f-3.md |
| 49 | [49_TICKET-20261023-GE-124g-5.md](./49_TICKET-20261023-GE-124g-5.md) | A reference doc states what each kind of evidence is worth, for every future check | GE-124g-5 | 44_TICKET-20261023-GE-124g-1.md, 46_TICKET-20261023-GE-124g-2.md, 47_TICKET-20261023-GE-124g-3.md, 48_TICKET-20261023-GE-124g-4.md, 17_TICKET-20261022-GE-124c-1.md |

## Dependencies

```
GE-124a-1 (no dependencies)
GE-124a-1-i -> GE-124a-1
GE-124a-1-ii -> GE-124a-1
GE-124a-2 -> GE-124a-1
GE-124a-2-i -> GE-124a-2
GE-124a-3 -> GE-124a-1  [build order: extends _frontend_declaration_reader.py, created by GE-124a-1]
GE-124a-3-i -> GE-124a-3
GE-124a-3-ii -> GE-124a-3
GE-124a-4 -> GE-124a-1, GE-124a-2, GE-124a-3
GE-124b-1 -> GE-124a-1  [build order: extends _frontend_declaration_reader.py, created by GE-124a-1]
GE-124b-1-i -> GE-124b-1
GE-124b-1-ii -> GE-124b-1
GE-124b-2 -> GE-124a-1, GE-124c-1  [build order: GE-124c-1 creates check_frontend_ac_declaration.py]
GE-124b-3 -> GE-124b-1
GE-124b-4 -> GE-124b-1, GE-124b-2
GE-124b-5 -> GE-124b-1, GE-124b-3
GE-124c-1 -> GE-124a-1, GE-124a-3
GE-124c-1-i -> GE-124c-1
GE-124c-2 -> GE-124a-1, GE-124b-1, GE-124c-1  [build order: GE-124c-1 creates check_frontend_ac_declaration.py]
GE-124c-2-i -> GE-124c-2
GE-124c-2-ii -> GE-124c-2
GE-124c-3 -> GE-124c-1
GE-124c-3-i -> GE-124c-3
GE-124c-4 -> GE-124c-1, GE-124c-2, GE-124c-3
GE-124c-5 -> GE-124c-1, GE-124c-2, GE-124c-3
GE-124d-1 -> GE-124c-1
GE-124d-1-i -> GE-124d-1
GE-124d-2 -> GE-124c-1
GE-124d-2-i -> GE-124d-2
GE-124d-3 -> GE-124d-1, GE-124d-2
GE-124d-4 -> GE-124d-1, GE-124d-2, GE-124d-3
GE-124e-1 (no dependencies)
GE-124e-2 -> GE-124e-1
GE-124e-3 -> GE-124e-1, GE-124e-2
GE-124e-3-i -> GE-124e-3
GE-124e-4 -> GE-124e-1, GE-124e-3
GE-124e-5 -> GE-124e-1, GE-124e-2, GE-124e-3, GE-124e-4
GE-124f-1 -> GE-124b-1
GE-124f-1-i -> GE-124f-1
GE-124f-1-ii -> GE-124f-1
GE-124f-2 -> GE-124f-1, GE-124b-1
GE-124f-3 -> GE-124b-1
GE-124f-4 -> GE-124f-1, GE-124f-2, GE-124f-3
GE-124g-1 (no dependencies)
GE-124g-1-i -> GE-124g-1, GE-124e-1, GE-124g-3  [build order: GE-124e-1 creates check_ui_ac_declared.py; GE-124g-3 creates scripts/ac_store/evidence_axes.py]
GE-124g-2 -> GE-124e-3
GE-124g-3 -> GE-124g-1
GE-124g-4 -> GE-124f-3
GE-124g-5 -> GE-124g-1, GE-124g-2, GE-124g-3, GE-124g-4, GE-124c-1  [build order: GE-124c-1 creates check_frontend_ac_declaration.py]
```

Edges marked `[build order: ...]` are not in the AC depends_on graph. They were added on 2026-10-23 so that every ticket editing a shared new file is ordered after the ticket that creates it. They were added only where no ordering, direct or transitive, existed already, and the graph is acyclic. The creators:

| New file | Created by | Other tickets that edit it |
|----------|------------|----------------------------|
| `templates/scripts/commit_guardian/_frontend_declaration_reader.py` | 01 (GE-124a-1) | 02-08, 10-12, 28, 29, 38-42 |
| `templates/scripts/commit_guardian/check_frontend_ac_declaration.py` | 17 (GE-124c-1) | 13, 18, 19, 21-23, 26-30, 49 |
| `templates/scripts/commit_guardian/check_ui_ac_declared.py` | 32 (GE-124e-1) | 33, 34, 36, 37, 45, 46, 49 |
| `scripts/ac_store/evidence_axes.py` | 47 (GE-124g-3) | 45 |

Source paths only. `scripts/commit_guardian/` is gitignored build output (ADR-001), regenerated by build.py from `templates/scripts/commit_guardian/`, and the whole directory is deployed by `build_commit_guardian` (`scripts/build_phases_lifecycle.py`). So no ticket lists a `scripts/commit_guardian/` twin or a `scripts/build_phases.py` deploy-map edit for these files. `evidence_axes.py` is the exception: `scripts/ac_store/` modules deploy through `AC_STORE_DEPLOY_MAP` in `scripts/build_phases_ac_store.py`, which ticket 47 extends.

## Agent Assignments

| Agent | Tickets |
|-------|---------|
| ac-fulfillment-gate | 01, 02, 03, 04, 05, 06, 07, 08, 10, 11, 12, 13, 14, 17, 18, 19, 20, 21, 22, 23, 25, 26, 27, 28, 29, 30, 32, 33, 34, 35, 36, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48 |
| ac-validator | 01, 02, 03, 04, 05, 06, 07, 08, 10, 11, 12, 13, 14, 17, 18, 19, 20, 21, 22, 23, 25, 26, 27, 28, 29, 30, 32, 33, 34, 35, 36, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48 |
| architect-review | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49 |
| architecture-diagram-author | 25, 43 |
| commit | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49 |
| documentation-expert | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49 |
| documentation-verifier | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49 |
| frontend-coder | 14, 47 |
| pr-reviewer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49 |
| python-coder | 01, 02, 03, 04, 05, 06, 07, 08, 10, 11, 12, 13, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49 |
| test-runner | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49 |
| test-writer | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49 |

