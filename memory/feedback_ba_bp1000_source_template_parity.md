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

## BP-900e registry-completeness — the THIRD deployment-gap axis (2026-06-22, BA)

A NEW L1 under the existing L0 BP-900 (do NOT create a new L0; user explicitly
nested it). Slug folder reused: BP-900-deployment-completeness/. Next free L1
letter after a/b/c/d was BP-900e. Children all readiness: draft, priority:
critical (inherited from BP-900), origin_agent: business-analyst:
- BP-900e-1 (L2, python-coder) — registered hook with NO templates/ copy => fail.
  PRODUCES the registry-completeness verdict (the spine). Regression fixtures:
  check_test_fixture_bloat.py + hooks/check_agent_spawn_consistency.py (both
  registered, present in scripts/commit_guardian/, ABSENT from templates/).
- BP-900e-2 (L2, python-coder) — registered hook WITH a template copy => pass;
  presence is sufficient, content-equality explicitly out of scope (that's BP-1000).
- BP-900e-3 (L2, python-coder) — source-only script NOT registered/referenced
  (build.py, epic_lock.py) => never flagged. The critical no-false-positive class.
  Candidate set is the UNION of registered+referenced; build the promised set
  first, never enumerate-then-subtract.
- BP-900e-4 (L2, python-coder) — failure report names each undeployed script,
  WHERE promised (registry hook id+file vs referencing template path), and the
  suggested action (promote to derived templates/scripts/ path). Lists ALL, not first.
- BP-900e-5 (L2, python-coder) — fires at the FINALIZE MERGE GATE (same position
  as BP-1000), NOT the build.py preflight. Negative clause pins BP-900b stays preflight.
- BP-900e-1-i (L3) — template-referenced script with no template copy also flagged;
  coordination with BP-900b (complements, not subsumes — reuse BP-900b-1 extraction
  patterns; report once per surface).
- BP-900e-3-i (L3) — allowlist seam: build_propagation_audit.EXTERNAL_DEPENDENCY_ALLOWLIST
  entries exempt, same allowlist BP-900b-1-1 honors (one allowlist, both surfaces).

### The three-way deployment-gap seam (cite this when authoring near any of them)

ONE missing-deployment family, THREE orthogonal axes — keep distinct, never duplicate:
- BP-1000 (a–d): byte-equality of scripts present in BOTH scripts/ AND templates/.
  BP-1000d-1 EXPLICITLY excludes source-only scripts from parity.
- BP-900b: build.py PREFLIGHT — template script references vs the deployable
  manifest. Reads templates only; does NOT read commit_guardian.json.
- BP-100b-11: registry entry -> script exists within its OWN tree (referential
  integrity), pre-commit. Does NOT check registry->deployment completeness.
- BP-900e (this run): registry/template-ref promised script has a DEPLOY-SOURCE
  copy AT ALL (zero template copy). Merge gate. This is exactly the case BP-1000
  excludes. Decision recorded in BP-900e body: COMPLEMENTS BP-900b for template
  refs (merge-gate re-assert + adds the registry source BP-900b never reads);
  does NOT subsume it.

Pattern for IT-PO: spine AC (e-1) PRODUCES the verdict via delivers_to python-coder;
e-2/e-3/e-4/e-5 + both L3s CONSUME it via expects_from BP-900e-1. One behavioral AC
per concern; helpers expressed as contracts, not pre-split per agent.
