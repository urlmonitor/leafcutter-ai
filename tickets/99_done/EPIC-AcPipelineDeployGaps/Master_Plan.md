---
title: "EPIC: AC Pipeline Deployment Gaps"
type: epic
status: done
components:
  - infrastructure
created: 2026-06-16
depends_on: []
priority: high
---

# EPIC: AC Pipeline Deployment Gaps

Four independent latent architecture/deployment gaps in the leafcutter-ai v2.0.0 AC pipeline, surfaced by post-merge manual behavioral testing. These are not regressions from recent work — they are pre-existing issues that predate the AC pipeline consolidation mop-up and require design decisions. Two tickets are HIGH priority (create-ticket.js silent failure and plan-feature.js missing deployment), two are MEDIUM (skill portability mismatch and triage schema drift).

## Sub-Tickets

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_resolve_create_ticket_dead_deliverable.md](./01_resolve_create_ticket_dead_deliverable.md) | Resolve create-ticket.js dead deliverable from stale business-analyst contract | `[ ]` |
| 02 | [02_deploy_plan_feature_to_consumers.md](./02_deploy_plan_feature_to_consumers.md) | Deploy plan-feature.js to consumer installs via templates/workflows-js | `[ ]` |
| 03 | [03_reconcile_ac_scanner_portability.md](./03_reconcile_ac_scanner_portability.md) | Reconcile ac-scanner/build-ac skill portability with script deployment reality | `[ ]` |
| 04 | [04_align_finalize_feature_triage_schema.md](./04_align_finalize_feature_triage_schema.md) | Align finalize-feature.js triage schema between step-3 instructions and step-6a reader | `[ ]` |
| 05 | [05_fix_build_ac_script_invocation_paths.md](./05_fix_build_ac_script_invocation_paths.md) | Fix build-ac/ac-scanner script invocation paths for consumer-install reachability (follow-up to 03, found by spot-check) | `[ ]` |
