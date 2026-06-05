---
title: "INF-600 Ticket 3: Define 5 agent categories in agent_registry.json with default constraints"
status: todo
components:
  - build_pipeline
created: 2026-06-05
depends_on:
  - TICKET-20260605-INF600-SchemaDefinitionPrototype.md
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - config/agent_registry.json
  - templates/agents/python-coder.md
agents:
  architect-review: needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
source_acs:
  - INF-600h
ac_path: docs/acceptance-criteria/infrastructure/INF-600-self-describing-agents/
ac_coverage: 0/1
---

# INF-600 Ticket 3: Define 5 agent categories in agent_registry.json with default constraints

## Actor / Goal

In order to know what an agent can do from its category alone, we need to
define the five agent categories (`implementation`, `planning`, `testing`,
`research`, `supervisor`) in `config/agent_registry.json` and assign each
category a set of default tool permissions, required inputs, sign-off behavior,
and spawn constraints. Adding `category: implementation` to the `python-coder`
entry proves the schema works.

## Context

This ticket implements INF-600h: "Know what an agent can and cannot do from
its category alone."

Currently agents' capabilities are discoverable only by reading their individual
templates. The category system provides a tiered default contract: a consumer
who knows an agent is `implementation` category knows its default tool set,
sign-off capability, and spawn constraints without reading the template.

The five categories and their intended defaults (derived from the current
agent corpus):

| Category | Default tools | Sign-off | Spawn | Example agents |
|----------|--------------|----------|-------|----------------|
| `implementation` | Bash, Read, Edit, Write, Agent | Yes | research-agent, test-runner | python-coder, sql-coder, frontend-coder |
| `planning` | Read, Agent | No | multiple | business-analyst, architect-review, it-po |
| `testing` | Bash, Read, Edit, Write | Yes | none | test-writer, test-runner |
| `research` | Read, Agent | No | none | research-agent |
| `supervisor` | Bash, Read, Edit, Write, Agent | No | all | ticket-supervisor, create-epic |

The `category` field on each agent entry is the key. Per-agent overrides
(e.g., an implementation agent that cannot spawn) are expressed by explicit
field values that differ from the category default.

Depends on Ticket 1 (TICKET-20260605-INF600-SchemaDefinitionPrototype.md):
the registry schema additions from Ticket 1 must land before the category
additions here, to keep registry changes in a coherent sequence.

All ACs are at:
`docs/acceptance-criteria/infrastructure/INF-600-self-describing-agents/INF-600h.yaml`

## Acceptance Criteria

```gherkin
# INF-600h: Agent categories determine default constraints
Given the config/agent_registry.json file
When it is read
Then it contains a top-level "agent_categories" object
And the object defines exactly 5 categories:
  implementation, planning, testing, research, supervisor
And each category definition has:
  - default_tools (list of tool names)
  - required_inputs (list of required input field names)
  - signoff_capable (boolean)
  - spawn_constraints (object with allowed_spawn_targets or "all" / "none")
And the "agent_categories" object serves as the source of truth:
  when you see an agent's category value, you know its default behavior
  without reading its individual entry

Given the python-coder registry entry
When it is read
Then it contains a "category" field with value "implementation"
And the entry inherits default_tools [Bash, Read, Edit, Write, Agent]
  (its explicit "tools" field matches the category default or is absent)
And the entry's signoff capability is inferrable from the category default

Given a category definition with default spawn_constraints: "none"
And an agent entry with category: "research" and no explicit spawn_constraints
When a consuming system reads the agent's effective spawn constraints
Then it applies the category default (spawn_constraints: "none")
And per-agent overrides (explicit spawn_constraints in the entry) take
  precedence over the category default

Given the agent_categories object is present
And an agent entry contains an unrecognized "category" value
When the build system validates the registry
Then it emits a warning naming the agent and the invalid category value
And the valid category values are listed in the warning message
```

## Sign-offs

- [ ] architect-review
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### architect-review

- [ ] Define the exact JSON schema for the `agent_categories` top-level object.
  Specifically: should `spawn_constraints` be a list of allowed agent IDs,
  a string enum (`all` | `none`), or a structured object with `allowed` and
  `denied` lists? The Ticket 1 registry entries use `spawn_allowlist` (a list)
  — confirm whether `spawn_constraints` in the category definition should
  mirror this or use a different shape.

- [ ] Confirm the five category names. The existing registry entries use
  `tier: phase | utility | supervisor` as an approximation. Confirm whether
  the new `category` field replaces `tier`, coexists with `tier` (redundant
  data), or maps to `tier` (derived). If coexisting, document the semantic
  difference.

- [ ] Define the precedence rule for per-agent overrides: when an agent has
  `category: implementation` but its `tools` list differs from the category
  default, which wins at card-generation time and at validation time?

- [ ] Confirm which agents map to which category across the 40-agent corpus
  (at least the 10 most common agents). This mapping is needed for Ticket 5
  (rollout) and should be documented in the ADR or registry schema comment.

- [ ] Confirm backward compatibility: the existing `tier` field on registry
  entries must remain. The new `category` field is additive. No existing
  tooling that reads `tier` should break.

**Delivers to python-coder:** Approved `agent_categories` schema and
category-to-agent mapping for the python-coder prototype.

### python-coder

**Important:** Do not begin until architect-review has signed off.

**Deliverable 1 — `config/agent_registry.json`: `agent_categories` top-level object**

Add the `agent_categories` object at the top level of the registry JSON,
before the `agents` array. Use the schema approved by architect-review.

Example structure (pending arch-review approval):

```json
"agent_categories": {
  "implementation": {
    "default_tools": ["Bash", "Read", "Edit", "Write", "Agent"],
    "required_inputs": ["ticket_path"],
    "signoff_capable": true,
    "spawn_constraints": {
      "allowed": ["research-agent", "test-runner"]
    }
  },
  "planning": {
    "default_tools": ["Read", "Agent"],
    "required_inputs": [],
    "signoff_capable": false,
    "spawn_constraints": {"allowed": "all"}
  },
  "testing": {
    "default_tools": ["Bash", "Read", "Edit", "Write"],
    "required_inputs": ["ticket_path"],
    "signoff_capable": true,
    "spawn_constraints": {"allowed": "none"}
  },
  "research": {
    "default_tools": ["Read", "Agent"],
    "required_inputs": [],
    "signoff_capable": false,
    "spawn_constraints": {"allowed": "none"}
  },
  "supervisor": {
    "default_tools": ["Bash", "Read", "Edit", "Write", "Agent"],
    "required_inputs": [],
    "signoff_capable": false,
    "spawn_constraints": {"allowed": "all"}
  }
}
```

**Deliverable 2 — `config/agent_registry.json`: `category` field on python-coder entry**

Add `"category": "implementation"` to the python-coder registry entry.
This serves as the proof-of-concept that the schema works.

**Deliverable 3 — `templates/agents/python-coder.md`: `category` in frontmatter (optional)**

If architect-review approves a mirrored `category` field in the agent
frontmatter (for visibility without reading the registry), add it. If the
registry entry is the sole source of truth for category, skip this deliverable.

**Verification:**

- Read the updated registry JSON and confirm `agent_categories` parses without
  error via `python3 -c "import json; json.load(open('config/agent_registry.json'))"`.
- Confirm that the existing `tier` field on the python-coder entry is intact.
- Run `scripts/build.py --dry-run` and confirm no regressions.

## Risk & Safety

- Touches money? No.
- Touches data? No — adds schema to a JSON config file.
- Reversibility? Fully reversible — removing `agent_categories` and the
  `category` field from the python-coder entry restores the previous state.
- Risk of regressions: low. The `agent_categories` object is a new top-level
  key; existing parsers that iterate over `agents` array are unaffected. The
  build must be verified not to trip over the new top-level key.
