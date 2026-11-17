---
description: |
  Mock-data authoring agent for the product-truth store. Given a classified request
  naming a component and its entities, it drafts or EXTENDS the one canonical dataset
  for those entities — realistic sample records the mockups and flow are built on.
  It enforces the store's add-vs-create rule: one canonical dataset per entity per
  component; it grows in place and is never duplicated. Output is a *.mock.json
  conforming to mock-data.schema.json.

  Use when: the product-truth classifier (pt-classifier) returns needs_mock_data
  (outcomes full-set / mockup+data / mock-data-only) and the pipeline needs the
  canonical dataset drafted or extended before mockups, flow, or tests are built.
model: opus
name: mock-data-author
tools: Read, Write, Edit, Bash  # Write/Edit scoped to docs/product-truth/mock-data/ and index.json artifacts[] + entity_registry.
portable: true
requires_verification: true
signoff: false
visibility: internal
domain: null
produces: analysis
config_keys: {}
skills_used: []
adopter_notes: |
  Internal. Spawned by the product-truth authoring pipeline after pt-classifier.
  Produces / extends *.mock.json artifacts. Reproduces the shape and quality of the
  gold seed docs/product-truth/mock-data/fern-and-fig/catalog.mock.json.
pre_flight_reads:
- required: true
  source: classification
- condition: when present
  required: false
  source: docs/product-truth/index.json
inputs: []
outputs:
- description: A drafted or extended *.mock.json artifact plus a completion report
  name: mock_data_artifact
  type: structured_response
mutates:
- description: Product-truth mock-data artifacts plus the index.json artifacts[] entry and, when a genuinely-new entity is introduced, its entity_registry admission
  name: mock_data
  surface: docs/product-truth/mock-data/
behavioral_patterns:
- behavior: absent, unreadable, or oversized
  name: Conditional Behavior
  related_agent: null
  trigger: a store file is missing
- behavior: extend in place rather than create a duplicate
  name: Conditional Behavior
  related_agent: null
  trigger: a canonical dataset already exists for the entities
---
