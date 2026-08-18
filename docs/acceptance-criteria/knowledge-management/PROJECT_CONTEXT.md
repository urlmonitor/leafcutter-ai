---
title: "knowledge-management — AC store context"
description: Cross-agent conventions and standing notes for PO v3 / BA v3 / IT PO v3 authoring
  and decomposing ACs in the knowledge-management component (prefix KM).
created: '2026-08-18'
last_updated: '2026-08-18'
type: tutorial
status: active
components:
  - knowledge_management
---
# knowledge-management component — PROJECT_CONTEXT

Cross-agent context for PO v3 / BA v3 / IT PO v3 working in the knowledge-management
component. Read `docs/known-issues/knowledge-management.md` before adding capability
here — it lists six open defects, several of which are candidate children of the trees
below.

## Sub-namespaces are the local convention (KM-ADM, KM-DBF, KM-KQS, KM-VIS, KM-KGS)

This component does not use flat `KM-NNN` ids for everything. It carries compound
prefixes per subject area, and the schema explicitly supports them
(`^[A-Z]{2,6}(-[A-Z]{2,6})?-\d+...`). Existing families:

- `KM-ADM-*` — the artifact data map: what the map claims about how artifacts connect,
  and how truthfully it is drawn. Parented by `KM-ADM-100` since 2026-08-18.
- `KM-KGS-*` — knowledge-graph surface ingestion (`KM-KGS-100` L0 + large subtree).
- `KM-DBF-*`, `KM-KQS-*`, `KM-VIS-*` — dashboard/query/visualisation ACs, flat L2s.
- `KM-200` — artifact analytics (census over time), authored under the cheap-capture
  convention: L0 + L1 only, `covered_by` deliberately empty.

## LOAD-BEARING: compound-prefix ids are invisible to parent/child tooling

`derive_parent_id()` resolves `KM-ADM-005` **and** `KM-ADM-100a` to `KM-ADM`, which is
not an AC. Verified 2026-08-18. Consequences every authoring agent must know:

- Parent/child links in `KM-ADM-*` and `KM-KGS-*` are carried by the `parent` field
  (the schema's documented escape hatch), `depends_on` on the child, and `covered_by`
  on the parent. Set **all three**.
- `check-ac-parent-covered-by` never fires on these trees (it only enforces when the
  DERIVED parent appears in the child's `depends_on`). The back-links are a convention
  nothing defends — a missing one is silent.
- `check-ac-tree-limits` counts by derivation, so a compound-prefix L0 reads as
  childless and may emit its advisory "<3 children" line. Not a real thinness.
- `scan_ac_orphans.py` cannot see these trees at all: it reported 62 orphaned children
  store-wide on 2026-08-18 and zero of them were `KM-ADM` or `KM-KGS`. A health answer
  with a silent blind spot — the exact defect `ACS-1100` exists to end, occurring in
  the store's own health tooling.
- Do **not** propose re-IDing to fix this. Ids never change after creation, and
  `KM-ADM-005` is cited by `# covers:` tags in shipped tests.

## KM-ADM-100 — framing note for the BA/IT-PO (2026-08-18, PO)

`KM-ADM-100` ("rely on the map of how your project fits together, because it admits
what it cannot prove") is a RETROACTIVE L0: it was authored after all six of its
grandchildren shipped via `/quick-fix` (PR #425). Four L1s, no re-specification of the
children:

- **KM-ADM-100a** — a trust rating reflects what actually runs, and states how much it
  covered. Children `KM-ADM-001` (rated from a script's existence, not the registry)
  and `KM-ADM-005` (rated from "it blocks", with no statement of what it blocks over).
  The generalisation: an enforcement rating has two parts, *does it block* and *over
  what*; a rating carrying only the first is a partial answer in complete clothing.
- **KM-ADM-100b** — a connection the project does not have is visible as a gap.
  Children `KM-ADM-002`/`003`, a matched pair that must never ship apart: recording
  absent relations without the distinct visual treatment made the map WORSE.
- **KM-ADM-100c** — the links that tell you what a change breaks are followable.
  Child `KM-ADM-004`. One child deliberately; the user named AC↔AC dependency one of
  the two most load-bearing relations in the graph. Making a link visible must not
  make it trusted.
- **KM-ADM-100d** — every copy of the map agrees. Child `KM-ADM-006`. Standing
  constraint inherited from ACS-1100: the parity check MUST assert a minimum matched
  row count, or it degrades to a zero-denominator silent pass.

No `work_status` and no `roadmap_phase` on any of the five new records — both
deliberate, see the `KM-ADM-100` notes. **Do not add `work_status: done` to any AC
without a `# covers:`-tagged test**: the ratchet in
`unit_tests/docs/test_artifact_graph_covers_scope.py` (`HIGH_WATER_MARK = 244`) fails
the build the moment the untagged-done count rises to 245.

## ACS-1100 is INHERITED here, never re-homed

`ACS-1100` (ac-store, `scope: standing`) is the general contract that every figure this
component reports must obey: an answer states the total it was measured against and the
method behind it. Two trees already declare that inheritance in their notes — `KM-200`
("a STANDING principle every figure here must obey, not a home for it … Inherited, not
duplicated") and now `KM-ADM-100`. Follow the same pattern for any new counting or
rating capability: a `doc_links` entry with `relationship: context` and a `relevance`
line saying what is inherited. Do not copy ACS-1100's criteria into a KM record, and do
not move a KM record into ac-store because it happens to report a number.

## Ownership boundaries a BA must not blur

- **ACS-1100** — how an ANSWER describes its own coverage.
- **TQ-400** — whether the EVIDENCE for finished work still holds over time.
  `TQ-400d` owns retiring the 244 untagged-done ACs; `KM-ADM-005` only ratchets the
  floor. Do not author a third AC for that pile.
- **KM-200** — counting artifact populations over time.
- **KM-ADM-100** — what the artifact map claims and how truthfully it is drawn.

Live evidence that these boundaries need stating: `KM-ADM-005` reports 244 of 607
untagged-done ACs (2026-08-13, all levels) and `TQ-400` reports 240 of 641 (2026-08-17,
L2/L3 only). Same pile, two denominators, neither citing the other. Whichever builds
first must declare its inclusion rule.

## Validation gotcha — pass FILES, never a directory

`python3 scripts/ac_store/validate_ac_schema.py <directory>` prints
`No YAML files to validate.` and exits **0**. Verified 2026-08-18 against this very
folder. Always pass explicit file paths, or your green is meaningless. This is the
in-component grounding failure `ACS-1100` names.
