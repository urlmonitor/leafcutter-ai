---
description: |
  Fast triage agent for /plan-feature workflow. Reads the AC store for the
  relevant component, compares the user's natural-language request against
  existing L0/L1 criteria text, and classifies the routing path as one of:
  strategic (new capability, no matching L1 parent), behavioral (adds to
  existing feature with a matching L1), technical (adds constraints to existing
  ACs), or covered (request fully covered by existing ACs). Returns a
  structured JSON decision immediately — no files are written by this agent.
  Model-pinned to Haiku tier for speed; must complete triage in < 3s for a
  store of 200 ACs.
  Use when: /plan-feature workflow Stage 0; before any authoring agent is invoked.
model: haiku
name: ac-triage
tools: Read, Bash
portable: true
signoff: false
domain: null
produces: analysis
spawn_allowlist: []
tool_allowlist:
  - Read
  - Bash
config_keys: {}
adopter_notes: |
  Stage-0 triage agent for the /plan-feature workflow. Pinned to Haiku for
  latency: it only reads files and does semantic classification — no edits.
  Dispatch via plan-feature.js; do not invoke standalone.
pre_flight_reads:
  - source: "docs/acceptance-criteria/"
    required: true
    condition: "always — reads the AC store to classify the routing path"
inputs:
  - name: user_request
    type: string
    required: true
    description: "Natural-language description of the feature or constraint the user wants to add"
  - name: component
    type: string
    required: false
    description: "Optional component name to scope the AC store read to a single subdirectory"
outputs:
  - name: routing_decision
    type: structured_response
    description: "JSON object with fields: route, existing_acs, parent_l1_id, rationale"
mutates: []
behavioral_patterns:
  - name: Covered Fast-Exit
    trigger: "One or more active ACs already fully cover the user_request semantically"
    behavior: "Returns route: covered immediately with the matching AC IDs in existing_acs; no further analysis needed"
    related_agent: null
  - name: Store-Absent Fallback
    trigger: "docs/acceptance-criteria/ directory does not exist"
    behavior: "Returns route: strategic with rationale 'AC store not found — treating as new capability.' without reading any file"
    related_agent: null
  - name: Large-Store Scope Guard
    trigger: "AC store contains more than 200 files and a component was supplied"
    behavior: "Reads only the component-scoped subdirectory to stay within the < 3s latency budget"
    related_agent: null
---

# ac-triage (pre-spawn-migration snapshot: frontmatter verbatim, body trimmed)

Unrelated body prose.
