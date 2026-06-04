---
title: "Add complexity assessment and brainstorm escalation to BA"
status: todo
components:
  - build_pipeline
created: 2026-06-03
depends_on:
  - 03_ba_question_enforcement.md
priority: medium
phase: "Phase 2"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
user_facing_surface: null
files_touched:
  - templates/agents/business-analyst.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
  architecture-diagram-author: not_needed
  user-surface-smoker: not_needed
---

# 03a: BA Complexity Assessment + Brainstorm Escalation

## Business Intent

After the BA understands the request (ticket 03), it classifies complexity to
determine pipeline routing, and spawns a brainstorm swarm for novel/ambiguous
features where multiple valid approaches exist.

## Agent Contracts

### python-coder

- [x] AC-1: business-analyst.md includes "§5 Complexity Assessment" — classifies request after research as trivial (skip questions + IT PO), simple (skip IT PO), standard (full pipeline), or novel (brainstorm first)
- [x] AC-2: Complexity classification is included in the BA output payload as `complexity` field
- [x] AC-3: business-analyst.md includes "§6 Brainstorm Escalation" — when complexity = novel, spawns 2-3 brainstorm-worker agents with different perspectives, synthesizes options, presents to user, writes ACs only after user picks direction
- [x] AC-4: BA output payload includes `questions_asked`, `assumptions_made`, `research_findings`, and `complexity` fields

## Sign-offs

- [x] python-coder — 2026-06-04 09:15
- [x] pr-reviewer — 2026-06-04 09:20
- [x] commit — 2026-06-04 09:25
- [ ] pull-request

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | §5 Complexity Assessment in business-analyst.md | yes |
| AC-2 | | `complexity` field in Output Contract | yes |
| AC-3 | | §6 Brainstorm Escalation in business-analyst.md | yes |
| AC-4 | | `questions_asked`, `assumptions_made`, `research_findings` (pre-existing) + `complexity` (new) | yes |

## Risk & Safety

- Touches money? No.
- Touches data? No — modifies agent template only.
- Reversibility? Fully reversible — additive sections to existing template.
- Risk: Brainstorm swarm adds cost/time for novel features.
  Mitigation: only triggered when complexity = novel (rare).

## Comments

### 2026-06-04 09:15 — python-coder (status: ok)
feedback-id: fb_2026-06-04_6fccbb52
completion_manifest:
  ac1_complexity_section: true
  ac2_complexity_field_in_payload: true
  ac3_brainstorm_escalation_section: true
  ac4_all_payload_fields_present: true
Added §5 Complexity Assessment and §6 Brainstorm Escalation to templates/agents/business-analyst.md. The `complexity` field (trivial/simple/standard/novel) and optional `brainstorm_summary` field are now in the Output Contract. Step 1.75 in the Orchestration Sequence wires the two new sections into the BA flow. `brainstorm-worker` added to the sub-agent allowlist.

### 2026-06-04 09:20 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-04_b0627b59
completion_manifest:
  ac1_satisfied: true
  ac2_satisfied: true
  ac3_satisfied: true
  ac4_satisfied: true
  no_regressions: true
All 4 ACs satisfied. §5 and §6 are cleanly additive to existing template structure. Output Contract correctly includes `complexity` and optional `brainstorm_summary`. `brainstorm-worker` added to spawn allowlist. No existing behaviour changed.

### 2026-06-04 09:25 — commit (status: ok)
feedback-id: fb_2026-06-04_852a2f51
completion_manifest:
  files_staged_correctly: true
  commit_created: true
  no_cross_ticket_pollution: true
Staged templates/agents/business-analyst.md and ticket 03a; committed changes for §5 Complexity Assessment and §6 Brainstorm Escalation.
