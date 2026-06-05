---
title: "/create-ac workflow — triage, orchestrate, and gate AC authoring"
status: todo
components:
  - ac-store
  - ticket-creation
created: 2026-06-05
depends_on:
  - tickets/00_inbox/epics/EPIC-ACDrivenDevelopment/00_ac_readiness_gate_and_authoring_pipeline.md
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/workflows/create-ac.js
  - templates/agents/ac-triage.md
  - templates/skills/create-ac/SKILL.md
  - config/ac_schema.json
  - tests/ac_store/test_create_ac_workflow.py
agents:
  architect-review: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  test-writer: needed
  python-coder: needed
  llm-expert: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
source_acs:
  - ACD-300
  - ACD-300a
  - ACD-300a-1
  - ACD-300a-2
  - ACD-300a-3
  - ACD-300b
  - ACD-300b-1
  - ACD-300b-2
  - ACD-300c
  - ACD-300c-1
  - ACD-300c-2
  - ACD-300c-3
  - ACD-300d
  - ACD-300d-1
---

# 08: /create-ac workflow — triage, orchestrate, and gate AC authoring

## Actor / Goal

As a user of leafcutter-ai, I want to invoke a single `/create-ac` command that
triages my request, routes it through the correct authoring agents (PO v3,
BA v3, IT PO v3) in sequence with confirmation gates between stages, and writes
all output to the AC store — so that I can author well-structured acceptance
criteria without manually coordinating agents or knowing which pipeline stage
to start at.

## Context

The authoring agents (product-owner-v3, business-analyst-v3, it-po-v3) exist
and know how to write ACs. The readiness field and schema validation (ticket 00)
gate the scanner from picking up unfinished ACs. What is missing is the
orchestration layer that:

1. **Pre-triages** the user's request with a fast Haiku-tier agent to check for
   duplicates and classify the routing path (strategic / behavioral / technical /
   already-covered).

2. **Dispatches** the correct agents in sequence based on the triage decision,
   skipping upstream agents when the request only needs downstream work.

3. **Gates** each transition with user confirmation — the user sees the ACs
   produced at each stage and can approve, request edits, or cancel before the
   next agent starts.

4. **Writes exclusively to the AC store** — no ticket files are produced. Ticket
   generation is a separate downstream concern (ticket 01: AC scanner).

This ticket produces:

- **`templates/agents/ac-triage.md`** — a Haiku-pinned agent template that reads
  the AC store, evaluates the user's request for duplication and routing, and
  returns a structured JSON decision.

- **`scripts/workflows/create-ac.js`** — a JavaScript workflow script (same
  pattern as `build-ticket.js` and `finalize-feature.js`) that receives the
  triage decision and dispatches PO v3, BA v3, and/or IT PO v3 in sequence with
  user gates between each stage.

- **`templates/skills/create-ac/SKILL.md`** — the skill definition that maps
  `/create-ac` to the workflow script.

- **Tests** validating the triage routing logic and gate behavior.

## Acceptance Criteria

```gherkin
# AC-1: Haiku triage checks AC store for duplicates before routing

Given the user invokes /create-ac with a feature description,
When the ac-triage agent evaluates the request,
Then it reads all active ACs in docs/acceptance-criteria/ for the relevant component,
And if ACs already cover the request semantically, it returns route: "covered"
  with the list of matching AC ids,
And the workflow presents the existing ACs to the user with options to
  cancel, amend, or force-create new ACs.

# AC-2: Triage classifies "new feature" requests as strategic route

Given the user's request describes a new capability with no matching L1 parent,
When the ac-triage agent evaluates the request,
Then it returns route: "strategic",
And the workflow dispatches PO v3 -> user gate -> BA v3 -> user gate -> IT PO v3
  -> final user gate.

# AC-3: Triage classifies "behavioral addition" requests as behavioral route

Given the user's request adds scenarios to an existing feature that has an L1 AC,
When the ac-triage agent evaluates the request,
Then it returns route: "behavioral" with the parent_l1_id,
And the workflow dispatches BA v3 -> user gate -> IT PO v3 -> final user gate,
And PO v3 is not invoked.

# AC-4: Triage classifies "technical constraint" requests as technical route

Given the user's request only adds technical constraints to existing ACs,
When the ac-triage agent evaluates the request,
Then it returns route: "technical" with the AC ids to amend,
And the workflow dispatches IT PO v3 -> final user gate,
And neither PO v3 nor BA v3 is invoked.

# AC-5: User gate after PO v3 offers approve, edit, or cancel

Given PO v3 has written L0/L1 ACs with readiness: draft,
When the workflow presents gate 1,
Then the user sees all produced AC ids, titles, and criteria,
And can approve (proceed to BA v3), edit (re-invoke PO v3 with feedback),
  or cancel (abort pipeline, ACs remain as drafts).

# AC-6: User gate after BA v3 offers approve, edit, or cancel

Given BA v3 has written L2/L3 ACs with readiness: draft,
When the workflow presents gate 2,
Then the user sees all produced L2/L3 ACs with their parent L1 references,
And can approve (proceed to IT PO v3), edit (re-invoke BA v3 with feedback),
  or cancel (abort pipeline, ACs remain as drafts).

# AC-7: Final gate after IT PO v3 allows priority setting and approval

Given IT PO v3 has enriched ACs and set readiness: reviewed,
When the workflow presents the final gate,
Then the user sees all enriched fields (assigned_agent, complexity, contracts),
And is prompted to set a priority (critical/high/medium/low),
And can approve (set readiness: approved + priority on all ACs),
  edit (re-invoke IT PO v3), or defer (leave as reviewed).

# AC-8: All output goes to AC store, never to tickets/

Given the /create-ac workflow completes successfully,
When the user inspects the filesystem,
Then all new AC files are in docs/acceptance-criteria/<component>/,
And no files were created or modified in tickets/,
And each AC file passes validate_ac_schema.py.

# AC-9: Workflow script follows the JS workflow pattern

Given create-ac.js is the workflow script,
When it is invoked via the /create-ac skill,
Then it uses the same dispatch pattern as build-ticket.js (sub-agent calls,
  structured JSON interchange, error handling with retry),
And it logs each stage transition to the telemetry sink,
And it exits non-zero if a required agent fails after retry.

# AC-10: The ac-triage agent is pinned to Haiku tier

Given the ac-triage agent template exists at templates/agents/ac-triage.md,
When it is dispatched by the workflow,
Then it runs on a Haiku-tier model (not Opus or Sonnet),
And it completes triage in under 3 seconds for a store of 200 ACs,
And it returns a JSON object with keys: route, existing_acs, parent_l1_id, rationale.
```

## Sign-offs

- [ ] test-writer
- [ ] llm-expert
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### llm-expert

- [ ] Write `templates/agents/ac-triage.md`:
  - Model pin: Haiku tier (add `model: haiku` to agent frontmatter).
  - Input: the user's natural-language request + the component hint (if any).
  - Behavior: read all active ACs from docs/acceptance-criteria/ for the
    relevant component(s). Compare the user request semantically against
    existing L0/L1 criteria text. Classify route as one of:
    - `strategic` — new capability, no matching L1 parent.
    - `behavioral` — addition to existing feature, matching L1 found.
    - `technical` — only technical constraints, matching ACs found.
    - `covered` — request is already fully covered by existing ACs.
  - Output: structured JSON to stdout:
    `{ "route": "strategic|behavioral|technical|covered",
       "existing_acs": ["ACD-100a", ...],
       "parent_l1_id": "ACD-100a" | null,
       "rationale": "..." }`
  - Include a `spawn_allowlist: []` (triage agent should not spawn sub-agents).
  - Include a `tool_allowlist: [Read, Bash]` — only needs to read files.

- [ ] Write `templates/skills/create-ac/SKILL.md`:
  - Skill frontmatter mapping `/create-ac` to `scripts/workflows/create-ac.js`.
  - Description matching the trigger phrases: "create acceptance criteria",
    "new AC", "author ACs", "write requirements", "/create-ac".
  - Args: optional component name, optional `--force` to skip duplication check.

### python-coder

- [ ] Write `scripts/workflows/create-ac.js`:
  - Parse args: user request text, optional component, optional `--force`.
  - Stage 1 (triage): dispatch ac-triage agent, parse JSON response.
  - If route is "covered" and not `--force`: present existing ACs, prompt
    user for cancel/amend/force. If cancel, exit 0. If amend, set route
    to "technical". If force, set route to "strategic".
  - Stage 2 (authoring): based on route, dispatch agents in sequence:
    - strategic: PO v3 -> gate -> BA v3 -> gate -> IT PO v3 -> final gate
    - behavioral: BA v3 -> gate -> IT PO v3 -> final gate
    - technical: IT PO v3 -> final gate
  - Each gate: read newly written AC files from store, present to user,
    prompt for approve/edit/cancel. On edit, re-dispatch same agent with
    feedback. On cancel, exit 0 (ACs remain as drafts).
  - Final gate: prompt for priority, write readiness: approved + priority
    to all ACs in batch.
  - Error handling: if an agent fails, retry once. If retry fails, exit 1
    with error message.
  - Telemetry: log stage transitions to the telemetry sink.

### test-writer

- [ ] Write `tests/ac_store/test_create_ac_workflow.py`:
  - `test_triage_returns_strategic_for_new_feature`: mock AC store with no
    matching L1; assert triage returns route: strategic.
  - `test_triage_returns_behavioral_for_existing_feature`: mock AC store with
    matching L1; assert triage returns route: behavioral with parent_l1_id.
  - `test_triage_returns_covered_for_duplicate`: mock AC store with matching
    ACs; assert triage returns route: covered with existing_acs list.
  - `test_strategic_route_dispatches_three_agents`: mock agents; assert PO v3,
    BA v3, IT PO v3 are called in order.
  - `test_behavioral_route_skips_po`: mock agents; assert only BA v3 and
    IT PO v3 are called.
  - `test_technical_route_skips_po_and_ba`: mock agents; assert only IT PO v3
    is called.
  - `test_cancel_at_gate_preserves_draft_acs`: mock gate returning cancel;
    assert ACs remain with readiness: draft, no downstream agent called.
  - `test_final_gate_sets_approved_and_priority`: mock gate returning approve
    with priority: high; assert all ACs get readiness: approved, priority: high.
  - `test_no_files_written_to_tickets`: after full workflow, assert no files
    exist in tickets/ that were not there before.

## Risk & Safety

- Touches money? No.
- Touches data? Writes new AC YAML files to docs/acceptance-criteria/. Does not
  modify existing ACs unless the user selects "amend" on a covered request.
- Breaking change? No. This adds a new /create-ac command. Existing /create-ticket
  and /create-ticket-v2 workflows are unmodified.
- Reversibility? The workflow script, agent template, and skill can be deleted
  independently. ACs written by the workflow are standard AC YAML files.
