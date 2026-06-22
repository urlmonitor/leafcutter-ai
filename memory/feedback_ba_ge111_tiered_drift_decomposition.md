# BA learnings — GE-111 traceability-stays-honest decomposition (tiered drift)

Captured 2026-06-22 by business-analyst during /create-ac L2/L3 decomposition.
Component: guardrail-engine (GE). The five L1s GE-111a..e are now fully
decomposed (18 children). Do NOT re-decompose; enrich the existing files.

## How the file-vs-symbol design question (GE-111b) was resolved

The PO deliberately left the file-path-vs-symbol granularity OPEN for the BA to
decide at L2. Resolved as a TIERED design encoded as distinct children, NOT a
single either/or:
  - GE-111b-1 (L2) TIER 1 — file-path floor: implemented_by path no longer
    resolving in the staged tree = drift. ALWAYS ON, zero external tooling.
  - GE-111b-1-i (L3) — anchorless entries stay file-path-only (non-breaking for
    the existing store, where #anchor is currently NOT parsed; empty "path#"
    counts as anchorless).
  - GE-111b-2 (L2) TIER 2 — symbol tier: only when an implemented_by entry has a
    #symbol anchor AND the file survives (floor passed). Parse anchor, resolve
    via jcodemunch family (search_symbols / find_references / get_blast_radius),
    moved/renamed/removed symbol = drift.
  - GE-111b-2-i (L3) — graceful FAIL-OPEN of the symbol tier (tooling missing /
    language unsupported): symbol tier degrades to advisory, file-path floor
    STILL blocks. This is the explicit open question surfaced FOR THE IT-PO.
  - GE-111b-3 (L2) TIER 3 — suggest-new-location when a moved symbol has a single
    unambiguous new home; feeds GE-111d-1 (update route) and GE-111e-1 (message).
  - GE-111b-4 (L2) — reference-doc (documentation_triggers).

The load-bearing invariant the IT-PO must preserve: the file-path floor is
INDEPENDENT of jcodemunch, so it survives any tooling unavailability. Symbol tier
is opt-in via the #symbol anchor and degrades gracefully. Mirrors GE-100 ("fails
open when binary missing") and GE-107 (OSError fail-open).

## Cross-AC contract spine (delivers_to / expects_from), for IT-PO enrichment

Detection -> enforcement -> message is wired by contracts, not by stuffing one
agent per behavior into multiple ACs:
  - GE-111b-1/-2 PRODUCE the per-AC verdict (drift/clean + change kind + symbol +
    suggested location).
  - GE-111c-1 PRODUCES the in-scope AC set (staged-source-only) that GE-111b
    evaluates. Staged-files-only precedent: check_ac_circular_deps,
    check_ac_schema Phase 2, ACS-400e-2.
  - GE-111a-1 CONSUMES the verdict to make the block/proceed decision.
  - GE-111e-1 CONSUMES the verdict fields to render the actionable message;
    GE-111d-3 supplies the applicable-routes content.
  - GE-111d-1 (update) CONSUMES GE-111b-3's suggested new location.

## IT-PO open questions deliberately left for enrichment (do not assume)

1. GE-111b-2-i — the precise unavailability signals (missing binary, unsupported
   language, stale index, tooling timeout) and whether any should defer to a
   store-wide scan vs silent advisory skip.
2. GE-111d-2 (confirm route) — the durable, VERSION-AWARE confirmation storage
   field/format (amended_by entry? anchor? token keyed to source version?). The
   AC pins the BEHAVIOR (clears the block; re-flags when the confirmed source
   changes again) and leaves the field choice to IT-PO. ACS-400b-2 already lets
   implementation agents write implemented_by, so the update route does not
   collide with field-write governance.

## Agent assignment (expect IT-PO to keep or re-route by surface)

All behavioral ACs => python-coder (the work is a scripts/commit_guardian/
check_*.py hook + jcodemunch integration, all .py). Doc ACs: documentation-expert
for how-to (GE-111a-3, GE-111d-4) and reference-doc (GE-111b-4);
architecture-diagram-author for sequence diagrams (GE-111a-4, GE-111d-5). Per the
IT-PO surface-routing note: hook scripts are correctly python-coder here, so this
is one case where the BA's uniform python-coder stamp is right for the behaviors.

## Harness note

The `.build-feature.lock` inline_work_guard intermittently false-positive-blocked
a couple of parallel Write calls during this /create-ac authoring run (the lock
belongs to /build-feature, not /create-ac). Retrying the individual Write
immediately succeeded — the lock was absent on re-check. If it recurs, write AC
files one at a time rather than in a large parallel batch.
