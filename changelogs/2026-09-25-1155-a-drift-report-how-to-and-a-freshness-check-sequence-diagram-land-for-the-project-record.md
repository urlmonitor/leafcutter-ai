---
title: "A drift-report how-to and a freshness-check sequence diagram land for the project record"
date: "2026-09-25"
time: "11:55"
type: manual
components:
  - ux_prototyping
  - documentation_system
summary: "Two more EPIC-TruthfulProjectRecord tickets land: a how-to walking a reader from an automatic drift finding to a reconciled record (UXP-700c-4), and an L3 sequence diagram showing the ordered exchange from a changed file to a written behind mark (UXP-700c-5). Both were built and committed together in 89a27640, but ticket 27's (UXP-700c-4) own record was never closed — the drive's phase agent died on a schema retry cap after the commit landed. This recovery pass closed the record by hand."
description: "Covers UXP-700c-4 and UXP-700c-5. UXP-700c-4 adds docs/how-to/reading-a-drift-report-and-reconciling-the-record.md: a lookup table of the four finding kinds the product-truth checker reports ([pointer], [pointer-unresolvable], [freshness], [freshness-never-confirmed], plus the related vanished-AC-id case), a full walkthrough of reconciling one behind journey end to end including re-confirming it, the code-right-vs-record-right split, and why a separator-only difference between platforms is never drift. UXP-700c-5 adds docs/architecture/diagrams/c3-009-record-freshness-check-sequence.md, an L3-Component sequence diagram tracing the exchange from git commit through ADR-049 trigger-scope resolution, pointer and freshness checking, and the ADR-043 behind-mark write, with five distinct terminations so checked-and-sound, nothing-examined, and not-checked can never be read as one. Both tickets' documentation-expert phases cross-linked the new artifacts into docs/how-to/authoring-product-truth-artifacts.md, docs/product-truth/README.md, docs/reference/product-truth-checker-outcomes.md, and docs/architecture/components/ux-prototyping.md, and regenerated docs/INDEX.md. The whole batch was committed together in 89a27640 by the original /build-feature drive. Ticket 28 (UXP-700c-5) reached status: done and was fully signed off in a follow-up commit (026181ad). Ticket 27 (UXP-700c-4) did not: its own documentation-verifier and commit phases never ran, leaving status: todo on an already-shipped ticket. This recovery pass verified UXP-700c-4's Agent Contracts against the committed diff and the how-to's actual content, closed out documentation-verifier and commit by hand, set files_touched/out_of_scope to reconcile against the whole branch diff (crediting sibling ticket 28's diagram and cross-link target, and an already-separately-committed sibling ticket's source files, to out_of_scope with reasons), and marked UXP-700c-4 work_status: done in the AC store via mark_ac_done.py (eligible under the test_required: false waiver, since the deliverable is prose pinned by UXP-700c-1/2/3's own executable tests)."
commits:
breaking: false
---

## Entry

Two more `EPIC-TruthfulProjectRecord` tickets are finished: `UXP-700c-4` (a
how-to for reading a drift report and reconciling the record) and
`UXP-700c-5` (a sequence diagram of how a change reaches a drift finding).
Both were built and their deliverables committed together in `89a27640` by a
`/build-feature` drive. Ticket 28 (`UXP-700c-5`) went on to be fully signed
off and closed in a follow-up commit (`026181ad`). Ticket 27's
(`UXP-700c-4`) own record was left behind: the drive's phase agent died on a
schema retry cap after the shared commit landed, so `documentation-verifier`
and `commit` never ran for it even though its deliverables were already
shipped.

**`UXP-700c-4`** adds
`docs/how-to/reading-a-drift-report-and-reconciling-the-record.md`: a
lookup table naming every finding kind the product-truth checker can report
(`[pointer]`, `[pointer-unresolvable]`, `[freshness]`,
`[freshness-never-confirmed]`, plus the related vanished-AC-id case) and
what to open first for each; a full walkthrough reconciling one behind
journey end to end, including how to re-confirm it against the current code;
the split between "the code was right, the record was wrong" and "the
record was right, the code was wrong"; and the rule that a separator-only
difference between platforms is never drift.

**`UXP-700c-5`** adds
`docs/architecture/diagrams/c3-009-record-freshness-check-sequence.md`, an
L3-Component sequence diagram tracing the ordered exchange from a change
reaching the automatic checks, through ADR-049 trigger-scope resolution and
pointer/freshness checking, to the ADR-043 `behind` mark being written — with
five distinct terminations so `checked-and-sound`, `nothing-examined`, and
`not-checked` can never be read as one outcome.

This recovery pass verified `UXP-700c-4`'s `## Agent Contracts` against the
committed diff and the how-to's actual content (all four AC clauses
present), closed out its `documentation-verifier` and `commit` phases by
hand, and reconciled `files_touched`/`out_of_scope` against the whole branch
diff between the two sibling tickets — crediting ticket 28's diagram and its
cross-link target, and an already-separately-committed sibling ticket's
source files, to `out_of_scope` with reasons rather than silently dropping
them. `UXP-700c-4` was marked `work_status: done` in the AC store via
`mark_ac_done.py`, eligible under its `test_required: false` waiver since the
deliverable is prose whose subject behaviours are pinned by `UXP-700c-1/2/3`'s
own executable tests.
