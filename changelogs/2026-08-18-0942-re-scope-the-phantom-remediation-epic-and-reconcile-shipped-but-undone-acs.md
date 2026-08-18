---
title: "docs(build-pipeline): re-scope the phantom-remediation epic and reconcile shipped-but-undone ACs"
date: "2026-08-18"
time: "09:42"
type: manual
components:
  - build_pipeline
  - ac_driven_dev
  - build_orchestration
summary: "Re-scopes EPIC-BuildPipelinePhantomRemediation against the current tree — closes two tickets already fixed on main, bundles six newer in-scope ACs into three tickets, reconciles ten shipped-but-undone AC rows against executed evidence, and files two verified defects."
description: "A three-reviewer scope refresh (product-owner, business-analyst, it-po) over EPIC-BuildPipelinePhantomRemediation found the epic had drifted from the tree it was written against. Tickets 01 (BP-900c-3) and 05 (BP-1200b) were already fixed on main — with deliberate, AC-naming inline rationale and green covers-tagged tests — so both close as done with per-claim evidence rather than being driven, which would have dispatched test-writer onto an already-green suite in violation of TDD order. Forty-nine newer ACs were assessed for inclusion; six are in scope and land as three tickets bundled by root-cause file rather than one-ticket-per-AC: 07 (BP-100k-1/-2, the build manifest recording what the drift gates compare), 08 (BP-100k-3/-3-i, drift gates reporting gaps instead of passes), and 09 (BP-1100b-4/-5, presence-only assertions no longer counting as proof). Master_Plan gains a file-collision table replacing a false parallelism claim: 02/06 collide on build_phases.py, 08/09 on commit_guardian.json, 04/09 on finalize-feature.js, and 08 depends on 07. Separately, an AC-store reconciliation applied a three-condition bar for work_status: done — shipped code matching the criterion, a covers-tagged test naming the AC, and that test observed green under AC_ENFORCE_STRICT=1. Ten AC rows met it and flipped; twelve did not and stay todo, with the distinction between missing bookkeeping and missing coverage recorded per row. Covers tags were added only where an execution audit proved the test really runs the behaviour. Two verified defects are filed: TICKET-20260721-FIN-100g-4 is reopened because deploy_consistent and redeployed are requested from the parity agent and never read, and the ACD-1900b-5-i / BP-300e-4 conflict is adjudicated in favour of the shipped, tested behaviour. BP-900c-3's list-form it_requirements is converted to the structured object form so check-ac-schema passes without a hook skip. Two child_limit_override waivers (BP-300e at 6, FIN-100c at 14) are documented as scoped, pre-existing, and explicitly not resolutions — both want ac-tree-split Pattern C."
pr: 464
commits:
  - e73b1265d
  - 6c3dcf66b
  - 7ad893f72
  - c1c03b60e
---

## Entry

An epic written to remediate phantom-done had itself gone stale: two of its six
tickets described defects that `main` had already fixed. Driving them would have
sent `test-writer` at a green suite — a TDD-order violation dressed up as
progress. Both close as `done` with the evidence read off the tree, not inferred
from the ticket.

The rest of the re-scope is about honesty in the epic's own metadata. The
Master_Plan claimed the tickets could run in parallel; four pairs collide on a
shared file and one is a hard dependency. That claim is replaced with the
collision table a supervisor can actually schedule from.

The AC-store half applies one bar consistently: an AC is `done` when the shipped
code matches the criterion, a `# covers:`-tagged test names it, and that test was
watched going green with `AC_ENFORCE_STRICT=1` set. Ten rows cleared it. Twelve
did not, and are left `todo` — several of them are *implemented* but genuinely
uncovered, which is exactly the state this repository exists to keep visible
rather than paper over with a tag.

Two defects surfaced during the review and are filed rather than fixed in place:
a finalize parity result that is computed, requested, and then never read; and a
gate-template contradiction that is adjudicated toward the behaviour that ships
and is tested.
</content>
</invoke>
