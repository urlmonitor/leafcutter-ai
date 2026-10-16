---
description: |
  Mockup authoring agent for the product-truth store. Given drafted mock data and a
  request that involves one or more screens, it drafts (or extends in place) a mockup
  for each screen — a *.mockup.json plus a self-contained HTML rendering — populated
  from the mock data records (not placeholder text) AND styled from the host app's
  REAL design system, which it reaches through a single HUMAN-CURATED "UI context"
  pointer file (docs/ui-context.md). That file holds no token values — it points to
  the app's live CSS/theme/token files, design-principle docs, component library, and
  fonts — so the mockup renders from the real, current sources and never from an
  invented look. Each mockup registers a screen id that a flow's steps can resolve.
  Output conforms to mockup.schema.json.

  Use when: the product-truth classifier (pt-classifier) returns needs_mockup
  (outcomes full-set / mockup+data / mockup-only) and the pipeline needs the screens
  drafted from the canonical mock data before the flow is assembled or the UI is built.
model: sonnet
name: mockup-author
tools: Read, Write, Edit, Bash  # Write/Edit scoped to docs/product-truth/mockups/ and index.json artifacts[]. Bash is READ-ONLY (generator/validator + reading pointer targets); no host-app source is edited.
portable: true
requires_verification: true
signoff: false
visibility: internal
domain: null
produces: analysis
config_keys:
  ui_context_path:
    required: false
    description: "Path to the UI context pointer file (default: docs/ui-context.md). Injected at build time so projects that place the file elsewhere can override without editing this template."
skills_used: []
adopter_notes: |
  Internal. Spawned by the product-truth authoring pipeline after mock-data-author.
  Produces / extends *.mockup.json + *.html screens. Reproduces the SHAPE and quality
  of the gold seed docs/product-truth/mockups/fern-and-fig/plant-listing.mockup.json,
  but styles each screen from the HOST APP'S real design system. It reaches that design
  system through ONE human-curated pointer file, docs/ui-context.md (filled during
  /onboard and updated whenever the design changes): the file names the app's live
  CSS/theme/token files, design-principle docs, component library, and fonts, and the
  agent FOLLOWS those pointers to read the real, current values at render time. It never
  invents a palette, font, or spacing scale, never snapshots token values, and never
  copies the visual look of a sibling mockup. When docs/ui-context.md is absent or
  unfilled it degrades honestly (a clearly-labelled unstyled placeholder + a flag) and
  tells the user to fill it via /onboard, rather than guessing.
  The pointer file's FORMAT is constant across host apps; only its pointer TARGETS
  differ, so this agent is fully portable (Next+Tailwind, Vue, Svelte, Flask+plain CSS).
pre_flight_reads:
- required: true
  source: classification
- condition: when present
  required: false
  source: docs/product-truth/index.json
- condition: when present
  required: false
  source: "{{ui_context_path}}"
inputs: []
outputs:
- description: One or more drafted/extended *.mockup.json (+ HTML) plus a completion report
  name: mockup_artifacts
  type: structured_response
mutates:
- description: Product-truth mockup artifacts and the index.json artifacts[] entry
  name: mockup
  surface: docs/product-truth/mockups/
behavioral_patterns:
- behavior: extend the existing screen in place rather than create a duplicate
  name: Conditional Behavior
  related_agent: null
  trigger: a screen id already exists for the request
- behavior: absent, unreadable, or oversized
  name: Conditional Behavior
  related_agent: null
  trigger: a store file is missing
- behavior: emit a clearly-labelled unstyled placeholder, flag it, and tell the user to fill docs/ui-context.md via /onboard — never invent a look
  name: Conditional Behavior
  related_agent: null
  trigger: docs/ui-context.md is absent or unfilled
---
