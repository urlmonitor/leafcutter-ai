# PO learnings — TQ-400 (proof over time / durable done-proof) framing

Captured 2026-08-17 (product-owner) authoring a new L0 + 5 L1s in testing-quality.
For BA (L2/L3 decomposition) and IT-PO (enrichment).

## Why testing-quality, not build-orchestration

Namespace choice was constrained to BO or TQ. Chose TQ because the subject is
"does the test evidence for finished work still hold" — a sibling of TQ-100
(which tests gate main) and TQ-300 (does the tooling have tests at all). BO's
charter is drive-time orchestration (sequencing gates, dispatch preflight);
parking a store-wide periodic audit next to BO-2500 invites exactly the
mis-merge the L0 notes warn against. ac-store (ACS) would also have been
defensible — the store's own credibility — and is the re-home candidate if
TQ-400 ever grows a schema/governance-heavy child set. TQ-400 was free
(TQ-100/200/300 only).

## The three honesty axes — LOAD-BEARING, do not re-litigate or merge

- BO-2500 = proof AT MARK TIME (is there a real passing test on real data at the
  moment work is declared done).
- BP-1100 = phantom-done AT THE TICKET/EPIC LEVEL during a drive (does the
  change actually execute) — still a mark-time guarantee, one altitude up.
- TQ-400 = proof OVER TIME, whole-store, AFTER mark time, plus a supported
  path back out of done. Neither neighbour re-checks or can demote.
The L0 `notes` field states this explicitly; keep it intact when amending.

## L1 shape and the two axes the request did NOT ask for

Requested axes mapped to TQ-400a (whole-store sweep), TQ-400b (demotion with
recorded reason), TQ-400c (visible cadence), TQ-400d (triage the existing 240).
Added TQ-400e (no false demotions + a recorded "genuinely test-free" exemption)
because a sweep that demotes wrongly destroys trust in the sweep itself, and
without an exemption path the same records get re-flagged every cycle. TQ-400e
is a precondition for TQ-400b/d having any authority — sequence it early.
Also folded "demoted work reappears as pickable work" into TQ-400b rather than
splitting it out (5 L1s, cap is 7).

## Verified evidence to carry into L2 (measured 2026-08-17, HEAD 339b0981c)

- BO-2500d-2: work_status done, criterion false for the whole interval until
  PR #451, named tests never written. The canonical regression case — a good
  L3 replay fixture.
- 240 of 641 done L2/L3 records have no test carrying their `# covers:` tag.
- scripts/ac_store/done_proof.py already computes the per-AC verdict but only
  ever runs over STAGED files (check_done_proof hook + CI gate). The gap is
  scope and cadence, not the verdict itself — do NOT let L2 re-specify the
  verdict rule, that is BO-2500 territory.
- mark_ac_done.py is one-directional; no supported done -> todo transition.

## Field convention (matched TQ-100 / TQ-300 siblings, not stale schema)

components list uses graph ids [testing_quality, ac_store]; scalar component is
`testing-quality`. status: active, req_status: draft, work_status: todo,
readiness: draft, priority: medium, roadmap_phase: phase_1, origin_agent:
product-owner, created: 2026-08-17. change_target/risk_surface set on every
record. documentation_triggers on every L1 (all five have non-empty triggers, so
no documentation_rationale needed). validate_ac_schema.py takes explicit file
paths — all 6 passed.
