---
description: |
  Product-truth request classifier. Given a plain-language feature request, decides
  which product-truth artifacts it needs — needs_flow, needs_mock_data, needs_mockup
  (a boolean each) — maps that combination to a routing outcome (full-set /
  mockup+data / mockup-only / mock-data-only / none), and names the target component,
  the entities, and the add-vs-create decision. Read-only: it writes NO files and
  returns a structured JSON decision the authoring pipeline routes on, so only the
  agents a request actually needs are dispatched.

  Use when: the product-truth authoring pipeline (define-a-feature's draft step)
  needs to decide which of the mock-data-author / mockup-author / flow-author agents
  to run for a request. Runs first, before any authoring agent.
model: haiku
name: pt-classifier
tools: Read, Bash  # Read-only. No Write/Edit — the decision is a returned JSON payload, not a file.
portable: true
requires_verification: false
signoff: false
visibility: internal
domain: null
produces: analysis
config_keys: {}
skills_used: []
adopter_notes: |
  Internal. The routing gate of the product-truth authoring pipeline. Scored against
  the gold eval set docs/product-truth/classifier/eval.jsonl. Never invoke to write
  artifacts — it only classifies and routes.
pre_flight_reads:
- required: true
  source: user_request
- condition: when present
  required: false
  source: docs/product-truth/index.json
inputs: []
outputs:
- description: Structured classification + routing decision (JSON)
  name: classification
  type: structured_response
mutates:
- description: Read-only agent — no filesystem mutations
  name: none
  surface: none
behavioral_patterns:
- behavior: absent, unreadable, or oversized
  name: Conditional Behavior
  related_agent: null
  trigger: a store file is missing
---
