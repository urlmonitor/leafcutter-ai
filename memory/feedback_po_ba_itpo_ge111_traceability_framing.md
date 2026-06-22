# GE-111 traceability-stays-honest — PO framing note (for BA + IT-PO)

Captured 2026-06-22 by product-owner during /create-ac authoring.
Component: guardrail-engine (GE). origin_agent: BrainCandy (user-authored).

## What GE-111 is

GE-111 ("Refactoring can never silently break the link between your requirements
and your code") is a NEW L0 in guardrail-engine, slug folder
GE-111-traceability-stays-honest/, with five L1 children GE-111a..e. It is a
BLOCKING pre-commit reconciliation check that keeps the AC `implemented_by`
link honest across refactors: when source referenced by an AC's `implemented_by`
is moved/renamed/deleted, the commit is blocked until the link is reconciled.

This is the second L0 in the GE component (GE-104 was the first; GE-100..103,
105..110 are flat sibling L1/L2). The old PROJECT_CONTEXT note "GE-1xx are
authored as L1 directly under the component, no L0" is now superseded twice over
— L0 roots are an accepted shape in GE.

## User-confirmed decisions — do NOT re-litigate at L2

- Enforcement is BLOCKING, not audit-only (explicit user instruction). Do not
  decompose warn-only as the default. A configurable warn tier may exist as a
  deliberate opt-in (mirroring GE-100's warn-vs-block config) but BLOCK is the
  headline + default. Lives on GE-111a.

## THE design question the PO deliberately left OPEN (GE-111b)

File-path vs symbol-level drift granularity is to be DECIDED during decomposition,
not assumed. Two granularities:
  1. file-path-only existence check (always-on floor, no jcodemunch dep; misses a
     moved/renamed FUNCTION inside a surviving file — the exact staleness the user
     wants closed).
  2. symbol/function-level via the repo's existing jcodemunch tooling
     (blast-radius / find-references / symbol search). `implemented_by` already
     allows an optional `#symbol` anchor that is currently NOT parsed; symbol-level
     resolution starts parsing it and uses jcodemunch to confirm/locate the symbol.
User direction: leverage jcodemunch "where possible" so a moved/renamed function
is detected as drift. NOT mandated for every case. Suggested L2 split is written
into GE-111b notes: file-path floor + symbol-tier (anchor present) + suggest-new-
location-on-move. IT-PO must decide graceful degradation / fail-open when
jcodemunch is unavailable or the language is unsupported (mirror GE-100 "fails
open when the binary is missing", and GE-107's OSError fail-open).

## L1 split (do not re-cut at L1 — decompose each into L2)

- GE-111a — block the commit + the actionable block decision. how-to + sequence-diagram.
- GE-111b — detection granularity (file vs symbol). Carries the design question. reference-doc.
- GE-111c — staged-files-only scoping (only links THIS commit touched; pre-existing
  breaks elsewhere are a separate store-wide scan, not the pre-commit gate).
  Precedents: check_ac_circular_deps (staged-only), ACS-400e-2. docs: none (rationale set).
- GE-111d — two reconciliation routes: UPDATE the link, or CONFIRM code still
  satisfies. Keep BOTH. Open Qs: durable record of a "confirm" so the next commit
  doesn't re-flag; ACS-400b-2 already permits implementation agents to write
  implemented_by so the update route does not collide with field-write governance.
  how-to + sequence-diagram.
- GE-111e — block-message quality (names AC id, the broken implemented_by entry,
  the change kind, pointer to GE-111d options). Mirrors ACS-400e-1. docs: none.

## Overlap check the PO already ran (so BA/IT-PO need not repeat)

ACS-400 family governs WHO may WRITE AC fields (authorization); ACS-400b-2 lets
implementation agents write implemented_by. NONE of ACS-400 verifies that
implemented_by still points at code that exists/matches reality. No overlap —
GE-111 is link-INTEGRITY (triggered by source refactors), complementary to
ACS-400's write-AUTHORIZATION governance. Component choice = guardrail-engine
because the mechanism is a `check_*.py` pre-commit hook and the trigger is source
code changing (GE directory_patterns), exactly like GE-104 doc enforcement.
