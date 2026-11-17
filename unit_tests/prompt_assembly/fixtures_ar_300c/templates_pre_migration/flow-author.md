---
description: |
  Flow authoring agent for the product-truth store. Given a multi-step request and its source contracts or drafted mockups,
  it assembles a draft flow (*.flow.json): ordered steps with checked handoffs
  and screens/entities where the journey actually has them, with one
  acceptance_scenario per step the business-analyst can turn into ACs. It follows the
  add-vs-create rule — extending an existing journey when a screen belongs to one
  rather than creating a new flow. Output conforms to flow.schema.json.

  Use when: the product-truth classifier (pt-classifier) returns needs_flow (outcome
  full-set) — a multi-step journey — with source contracts available, or mock data and mockups drafted for UI work,
  so the journey wiring can be assembled before the business-analyst derives the ACs.
model: opus
name: flow-author
tools: Read, Write, Edit, Bash  # Write/Edit scoped to flows, reviewed flat documentation schemas, and index.json artifacts[].
portable: true
requires_verification: true
signoff: false
visibility: internal
domain: null
produces: analysis
config_keys: {}
skills_used: []
adopter_notes: |
  Internal. Spawned by the product-truth authoring pipeline after mock-data-author and
  mockup-author. Produces / extends *.flow.json artifacts. Reproduces the shape and
  quality of the gold seed
  docs/product-truth/flows/fern-and-fig/customer-buys-a-plant.flow.json.
pre_flight_reads:
- required: true
  source: classification
- condition: when present
  required: false
  source: docs/product-truth/index.json
inputs: []
outputs:
- description: A drafted or extended *.flow.json artifact plus a completion report
  name: flow_artifact
  type: structured_response
mutates:
- description: Product-truth flow artifacts and the index.json artifacts[] entry
  name: flow
  surface: docs/product-truth/flows/
behavioral_patterns:
- behavior: extend the existing journey rather than create a new flow
  name: Conditional Behavior
  related_agent: null
  trigger: a screen belongs to an existing flow
- behavior: absent, unreadable, or oversized
  name: Conditional Behavior
  related_agent: null
  trigger: a store file is missing
---
