---
title: "Kernel V0: ground option generation, widen native sources and fix evidence, gap and usage records"
status: in_progress
components:
  - decision_kernel
created: 2026-10-01
depends_on: []
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - grounding
  - retrieval
last_updated: 2026-10-01
agents:
  commit: needed
---

# Kernel V0: ground option generation, widen native sources and fix evidence, gap and usage records

## Actor / Goal
In order to trust what the kernel proposes and reports, we need decisions with unknown
options to ground those options in evidence the kernel retrieved, native retrieval to reach
the repository's own project metadata, and the evidence, gap and usage records to say what
really happened.

## Context
A second round of live exploratory runs of the Decision Kernel V0 (PR #973) exposed these
weaknesses (G1 to G9):

1. G1: for "Decide which acceptance criterion is most critical to implement next." the
   decision asked `host.generate_options` for options BEFORE any research. The packet carried
   no evidence and the operation has no repository permission, so the host could not see the
   acceptance-criteria store and a human was asked to approve five options that are not real
   criteria. The approval packet also had `decision_id: null`, and two decision records were
   created for one decision.
2. G2: the default retrieval sources covered only `kernel/`, `scripts/`, `docs/architecture`
   and the knowledge map. "Where are tests saved in leafcutter?" could not find
   `tests/README.md`, `pytest.ini` or `config/paths.json` natively; only host research did.
3. G3: `need.existing_patterns` was reported `satisfied` from one irrelevant excerpt.
4. G4: one contradiction appeared twice in the research bundle, next to a non-localised one
   from Jev.
5. G5: the kernel stripped leading indentation from host-provided verbatim excerpts,
   re-hashed them, changed the evidence ids and reported the host hash as replaced.
6. G6: the `host.research` output schema required `id` and `content_hash` while its
   instructions said not to invent hashes or ids.
7. G7: merged gaps took their title from the latest occurrence; drafts were titled with the
   root goal; a host-only gap with a native twin got no draft; a decline kept the
   `decision_report.v1` output schema; the write decline blamed the caller's permissions.
8. G8: envelope usage rows had `model_id` and `cost_usd` null while Langfuse had the Jev model
   and per-call costs; host-reported usage was not listed.
9. G9: `report.md` had no trace link.

Evidence (envelopes, host submissions, gap records, trace ids) is kept by the orchestrator
under the session scratchpad `explore/` folder (`v2_g2_*` for "Where are tests saved", `v2_g5_*`
for the acceptance-criterion decision, `runs2/` for run data, `client/v2_*host*.json` for host
submissions).

Governing text: Rev 3 spec sections 10.1 (an existing implementation is a pattern, not
proof), 10.2 to 10.5 (sources come from project metadata; no research just to raise a score;
conflicts are preserved), 10.3 (every result carries source, location, revision, hash and
truncation; a failed fetch is not an empty result), 10.4 (options are proposals), 11.3 (host
packets) and 12 (tracing); ADR-052 and ADR-053.

## Scope (no acceptance criteria by user decision)
- Decision grounding: unknown options trigger one bounded research request (task_context,
  existing_patterns, prior_decisions), then an options request carrying that evidence;
  generated options cite evidence ids in `source_refs` and are flagged or refused otherwise;
  `host.generate_options` stays without repository access. A stable decision id.
- Default sources for docs, acceptance criteria, roadmap and vision, tickets, config (with
  secret deny globs) and test layout, with bounded candidate counts.
- Coverage only from evidence that passed the relevance bar; deduplicated contradictions;
  verbatim excerpts; an honest host evidence schema.
- Gap record fixes, per-provider usage rows with model id and known cost, trace link in the
  report.
- Docs: how-to, and "As built (grounding)" notes in design parts 3, 4 and 5.

## Out of Scope
- Write capabilities (the V0 kernel stays read-only).
- Domain-specific logic in the kernel (grounding is generic research plus configured sources).
- Pushing; the orchestrator merges this branch into the PR branch.

## Comments
