# BA learnings — BP-1000 source↔template parity decomposition (build-pipeline)

Captured 2026-06-22 by business-analyst during /create-ac L2/L3 decomposition.
Origin: EPIC-CodeQualityHooks retrospective KI-2 (jscpd hook's templates/ copy
drifted from its scripts/ canonical copy, lost GE-100c measured%/threshold%
logic, shipped broken, caught only post-merge). Component: build-pipeline (folder
build_pipeline/ underscore, component: field hyphenated — per PROJECT_CONTEXT).

## What was decomposed (do NOT re-decompose; enrich the existing files)

BP-1000a (core parity mechanism), BP-1000c (visibility), BP-1000d (scope) are
decomposed. BP-1000b (merge-gate timing/enforcement point) is NOT yet decomposed
— its sequence-diagram trigger and its gate-enforcement L2s are still open.

Children, all readiness: draft, priority: medium (inherited), origin_agent:
business-analyst:
- BP-1000a-1 (L2, python-coder) — ANY byte-level diff on a mirrored
  source↔template script pair blocks the merge gate. PRODUCES the per-pair
  parity verdict (delivers_to python-coder). This is the spine other ACs consume.
- BP-1000a-2 (L2, python-coder) — source edited, template copy not updated =>
  drift + block (the exact jscpd-drift reproduction). expects_from a-1.
- BP-1000a-3 (L2, python-coder) — all pairs byte-identical => pass, merge
  proceeds. expects_from a-1.
- BP-1000a-1-i (L3, python-coder) — cumulative cross-ticket drift: gate compares
  FINAL branch state, catches drift each per-ticket sync individually passed.
  Gate SUPPLEMENTS (does not replace) per-ticket template-sync verification.
- BP-1000a-4 (L2, architecture-diagram-author) — component diagram
  (documentation_triggers [component-diagram]).
- BP-1000c-1 (L2, python-coder) — failure names every drifted file path + shows
  per-pair diff; lists ALL drifted pairs not just the first. expects_from a-1.
- BP-1000c-2 (L2, documentation-expert) — how-to (read failure, resolve drift,
  re-run). expects_from c-1.
- BP-1000d-1 (L2, python-coder) — source-only script with NO template counterpart
  is excluded from the comparison and never causes a false failure; verdict
  depends solely on mirrored pairs. expects_from a-1 (pairing/enumeration logic).
- BP-1000d-2 (L2, documentation-expert) — reference-doc enumerating in-scope
  mirrored dir pairs + the in-scope/exempt rule + how a new script enters scope.

## Cross-AC contract spine (delivers_to / expects_from) for IT-PO enrichment

The mechanism is ONE thing — a parity check producing a per-pair verdict over
mirrored scripts/ ↔ templates/scripts/ directories at the merge gate. I factored
it as:
- BP-1000a-1 PRODUCES the per-pair verdict (the single load-bearing primitive).
- a-2, a-3, c-1, d-1 all CONSUME it (expects_from BP-1000a-1). c-1 renders the
  message; d-1 constrains the pairing/enumeration; a-2/a-3 are the block/pass
  outcomes.
- a-1-i pins the verdict is computed over FINAL branch state, not per-ticket
  deltas — that is what makes it a backstop for cumulative drift.

Did NOT split each behavior into separate detect+enforce+message ACs per agent;
kept one behavioral AC per concern with contracts naming the boundary. IT-PO may
break the deterministic helpers out further if it prefers.

## Agent assignment (expect IT-PO to keep or re-route by surface)

All behavioral ACs => python-coder. Per the BA directory_patterns routing note,
build-pipeline owns scripts/build*.py etc.; the parity check is a build/merge-gate
mechanism (a diff runner over scripts/ vs templates/scripts/), so python-coder is
correct. Doc ACs: documentation-expert (how-to c-2, reference-doc d-2);
architecture-diagram-author (component-diagram a-4).

## Boundary kept clean vs BP-100k (per PROJECT_CONTEXT)

BP-100k = compiled-workflow-OUTPUT drift, pre-commit, hash manifests. BP-1000 =
SOURCE-to-shipped script parity, merge gate, byte diff. a-4's component diagram
explicitly distinguishes the two. Did not duplicate BP-100k work.

## Structural note

BP-1000c-1 and BP-1000d-1 are the FIRST children of their L1s, so they are
structurally L2 (PREFIX-NNNx-N), even though the task framed edges 4/5 as "L3".
Only edge 6 (cumulative drift) is a true L3 (BP-1000a-1-i) because it hangs off
the L2 scenario BP-1000a-1.
