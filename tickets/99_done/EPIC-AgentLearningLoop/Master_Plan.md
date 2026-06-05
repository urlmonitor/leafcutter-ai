---
title: "EPIC: Agent Learning Loop — Agents That Get Smarter Over Time"
type: epic
status: done
components:
  - infrastructure
created: 2026-06-05
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: true
source_acs:
  - INF-400
  - INF-400a
  - INF-400b
  - INF-400c
  - INF-400d
  - INF-400e
  - INF-400f
---

# EPIC: Agent Learning Loop — Agents That Get Smarter Over Time

## Problem

The v3 pipeline agents (PO v3, BA v3, IT PO v3) produce output and exit —
nothing they learn persists. They have `signoff: false` in their frontmatter,
so the mandatory §7 knowledge-capture trigger never fires. Every run starts
cold: no memory of previous work, no accumulated conventions, no learned
preferences.

The knowledge system already exists (route-knowledge, capture-learning,
PROJECT_CONTEXT.md, 11 injection channels) — but the v3 agents don't
participate in it. This epic connects them.

After it lands:

- Every v3 agent reads accumulated learnings at spawn (knowledge injection)
- Every v3 agent emits learnings before exit (knowledge capture)
- A dedicated harvester routes raw emissions to proper knowledge surfaces
- Component/domain folders accumulate context files that grow with each run
- Cross-agent knowledge sharing works through shared persistence (no special messaging)
- Repeat work on the same domain is measurably better than the first time

## Scope

Five tickets in dependency order:

| # | File | Capability | Source ACs | Status |
|---|------|------------|-----------|--------|
| 00 | [00_v3_template_knowledge_steps.md](./00_v3_template_knowledge_steps.md) | Add pre-flight inject + post-work emit steps to all three v3 agent templates | INF-400a, INF-400b | `[ ]` |
| 01 | [01_harvester_agent_and_adr.md](./01_harvester_agent_and_adr.md) | ADR decision on emission sink + harvester agent implementation | INF-400c | `[ ]` |
| 02 | [02_folder_context_accumulation.md](./02_folder_context_accumulation.md) | Component README + skill PROJECT_CONTEXT.md growth mechanics | INF-400d | `[ ]` |
| 03 | [03_cross_agent_knowledge_sharing.md](./03_cross_agent_knowledge_sharing.md) | Same-pipeline cross-agent learning flow via shared persistence | INF-400f | `[ ]` |
| 04 | [04_quality_improvement_verification.md](./04_quality_improvement_verification.md) | Verify second-run quality improvement for PO, BA, IT PO | INF-400e | `[ ]` |

## Dependency Graph

```
00 (template steps: inject + emit)       [no deps - starts first]
 ├── 01 (harvester + ADR)               depends_on: 00
 │    └── 02 (folder context)           depends_on: 01
 ├── 03 (cross-agent sharing)           depends_on: 00
 └── 04 (quality verification)          depends_on: 00, 02, 03
```

Ticket 00 starts first (no deps). Tickets 01 and 03 can start after 00
(parallel). Ticket 02 depends on 01 (harvester must exist to write context
files). Ticket 04 depends on 00, 02, and 03 (needs the full loop working to
verify quality improvement).

## Architecture Decision Records Needed

- ADR: Learning emission sink decision (reuse agent_telemetry.jsonl vs
  separate knowledge_emissions.jsonl). Scoped to ticket 01 (INF-400c-1).

## Phase-1 Advancement

This epic directly advances the phase_1 outcome:

> "Stable MVP that installs into any project and helps the user build good
> software — portable, self-onboarding, and reliable enough to use across
> multiple repos."

Knowledge accumulation is what makes "helps build good software" improve
with each use. A system that forgets everything between runs can never
become reliable enough for autonomous use across projects.

## Out of Scope

- Extending knowledge capture to ALL agents (phase agents already have
  signoff §7). This epic scopes to the v3 pipeline agents only.
- Building a new knowledge system from scratch. The route-knowledge,
  capture-learning, and PROJECT_CONTEXT.md patterns already exist — this
  epic connects the v3 agents to them.
- User-facing knowledge management UI. The learning is automatic and
  invisible to the user.
