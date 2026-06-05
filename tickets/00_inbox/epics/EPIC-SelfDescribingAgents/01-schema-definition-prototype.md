---
title: "INF-600 Ticket 1: Add self-description metadata fields to python-coder prototype"
status: todo
components:
  - build_pipeline
created: 2026-06-05
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/agents/python-coder.md
  - config/agent_registry.json
agents:
  architect-review: signed_off
  test-writer: not_needed
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
source_acs:
  - INF-600i
  - INF-600j
  - INF-600a-1
  - INF-600a-2
  - INF-600a-3
  - INF-600a-4
  - INF-600a-5
  - INF-600a-6
  - INF-600a-1-i
  - INF-600a-2-i
  - INF-600a-3-i
  - INF-600a-4-i
  - INF-600a-6-i
ac_path: docs/acceptance-criteria/infrastructure/INF-600-self-describing-agents/
ac_coverage: 0/13
---

# INF-600 Ticket 1: Add self-description metadata fields to python-coder prototype

## Actor / Goal

In order to make agent cards fully auto-generable, we need to add six
structured metadata fields to `templates/agents/python-coder.md` frontmatter
and its corresponding `config/agent_registry.json` entry so that the card
generator (Ticket 2) has a complete structured source of truth without
having to parse template prose.

## Context

The prototype agent card at `docs/agents/cards/python-coder.card.md` was
hand-authored and documents all the "auto-generation gaps" — fields that would
need to be in structured sources for the card generator to produce the card
without reading prose. This ticket closes those gaps for `python-coder` only,
establishing the schema contract for the card generator and the rollout
(Ticket 5).

The gaps identified in the card's "Auto-Generation Gap Summary" section are:

| Gap | Target field | Location |
|-----|-------------|----------|
| Knowledge channels consumed | `knowledge_channels` array | `agent_registry.json` |
| All skills invoked (not just declared) | `skills_invoked` array | `agent_registry.json` |
| `file_size_limit_py` config undeclared | Add to `config_keys` | `templates/agents/python-coder.md` |
| Pre-flight reads list | `pre_flight_reads` array | `templates/agents/python-coder.md` |
| Input/output contract | `inputs` / `outputs` / `mutates` arrays | `templates/agents/python-coder.md` |
| Behavioral patterns | `behavioral_patterns` array | `templates/agents/python-coder.md` |

The expected final state of `python-coder` is the prototype card at
`docs/agents/cards/python-coder.card.md`. All structured data inferred in that
card's tables must be present in the YAML sources after this ticket lands.

All ACs are at:
`docs/acceptance-criteria/infrastructure/INF-600-self-describing-agents/`

## Acceptance Criteria

The full Gherkin criteria are in the source AC YAML files listed in `source_acs`.
Key criteria per deliverable:

### Deliverable 1 — `skills_invoked` in `config/agent_registry.json` (INF-600a-1, INF-600a-1-i)

```gherkin
# INF-600a-1: skills_invoked array
Given the registry entry for python-coder
When the entry is read by the card generator
Then the entry contains a `skills_invoked` array
And each element has: skill_id, mode (always|conditional), condition (when conditional)
And the array includes signoff, doc-enforcer, complexity-reduction, collector-enforcer
And the existing `skills_used` field is retained as an alias

# INF-600a-1-i: validation
Given a registry entry where skills_invoked contains skill_id "nonexistent-skill"
When the build system validates the registry
Then validation fails naming the unresolvable skill_id
And distinguishes "not in templates/skills/" from "not in .claude/skills/"
```

### Deliverable 2 — `inputs`, `outputs`, `mutates` in frontmatter (INF-600a-2, INF-600a-2-i)

```gherkin
# INF-600a-2: structured I/O contract
Given the python-coder template frontmatter
When parsed
Then it contains an `inputs` array (each: name, type, required, description)
And an `outputs` array (each: name, type, description)
And a `mutates` array (each: name, surface, description)
And the card generator can produce the I/O Contract section from these alone

# INF-600a-2-i: empty inputs is valid
Given a utility agent template with inputs: []
When parsed
Then the build system accepts it (empty inputs is valid)
And the card generator renders "No structured inputs" rather than omitting the section
```

### Deliverable 3 — `knowledge_channels` in registry (INF-600a-3, INF-600a-3-i)

```gherkin
# INF-600a-3: knowledge_channels array
Given the registry entry for python-coder
When read by the card generator
Then the entry contains a `knowledge_channels` array
And each element has: channel (1-11), source, injection_mode, description
And the array covers channels 1, 2, 5, 6, 7, 8, 9, 10, 11 for python-coder

# INF-600a-3-i: out-of-range validation
Given a registry entry where knowledge_channels contains channel: 12
When the build system validates
Then validation fails citing valid range 1-11
And names the agent entry containing the invalid channel
```

### Deliverable 4 — `config_keys` completeness (INF-600a-4, INF-600a-4-i)

```gherkin
# INF-600a-4: every referenced config key declared
Given the python-coder template references {{config.file_size_limit_py}}
When the config_keys block is inspected
Then file_size_limit_py has an entry with: required, description, source fields
And no Mustache variable in the template body is undeclared

# INF-600a-4-i: build detection of undeclared keys
Given a template containing {{config.undeclared_key}} not in config_keys
When the build validates
Then it emits a warning/error naming the template, line, and variable
And suggests adding the key with required/description/source fields
```

### Deliverable 5 — `pre_flight_reads` in frontmatter (INF-600a-5)

```gherkin
# INF-600a-5: pre_flight_reads array
Given the python-coder template frontmatter
When parsed
Then it contains a `pre_flight_reads` array
And each element has: source, required, condition (when not required)
And the array covers: ticket_path (required), cited ADRs (conditional),
  docs/conventions/*.md (conditional)
And the card generator can produce the pre-flight row in the knowledge-flow
  table from this array without parsing the template body
```

### Deliverable 6 — `behavioral_patterns` in frontmatter (INF-600a-6, INF-600a-6-i)

```gherkin
# INF-600a-6: behavioral_patterns array
Given the python-coder template frontmatter
When parsed
Then it contains a `behavioral_patterns` array
And each element has: name, trigger, behavior, related_agent
And the array covers all 7 patterns from the prototype card:
  Contract-Aware Mode, TDD Red-Baseline Gate, Stop-and-Ask,
  Contract-Shrinkage Guard, Test Delegation, File-Size Limit,
  Research Delegation

# INF-600a-6-i: empty array valid for utility agents
Given a utility agent with no conditional behaviors
Then behavioral_patterns: [] is accepted (not rejected by build)
And the card generator renders "No conditional behaviors — single fixed path"
```

## AC Coverage

| AC ID | Level | Title | Agent |
|-------|-------|-------|-------|
| INF-600i | L1 | Agent template declares its knowledge and skills | — |
| INF-600j | L1 | Agent template declares its contracts and behaviors | — |
| INF-600a-1 | L2 | Registry declares every skill an agent invokes, with invocation mode | python-coder |
| INF-600a-2 | L2 | Agent frontmatter declares structured inputs, outputs, and mutates | python-coder |
| INF-600a-3 | L2 | Registry declares which knowledge channels feed each agent | python-coder |
| INF-600a-4 | L2 | Every config value referenced in template body is declared in config_keys | python-coder |
| INF-600a-5 | L2 | Agent frontmatter declares structured pre-flight reads | python-coder |
| INF-600a-6 | L2 | Agent frontmatter declares structured behavioral patterns | python-coder |
| INF-600a-1-i | L3 | skills_invoked rejects skill IDs that do not resolve to a template | python-coder |
| INF-600a-2-i | L3 | Agent with empty inputs array is valid | python-coder |
| INF-600a-3-i | L3 | knowledge_channels rejects channel numbers outside 1-11 | python-coder |
| INF-600a-4-i | L3 | Build detects Mustache variables not declared in config_keys | python-coder |
| INF-600a-6-i | L3 | Agent with no conditional behaviors has empty behavioral_patterns array | python-coder |

## Sign-offs

- [x] architect-review — 2026-06-05 10:00
- [x] python-coder — 2026-06-05 10:30
- [x] pr-reviewer — 2026-06-05 11:00
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-05 10:00 — architect-review (status: ok)
feedback-id: fb_2026-06-05_9fcee98c
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true

**Architectural Review — INF-600 Ticket 1: Schema Definition Prototype**

**Blast-Radius Analysis:** 2 files touched (`templates/agents/python-coder.md`, `config/agent_registry.json`), 1 component (`build_pipeline`). No Alembic migration, no hypertable change, no public API change, no ADR contract change. Classification: **Small** (threshold: ≤5 files, 1 component, no always-large trigger).

**Schema Approvals:**

1. `skills_invoked` (skill_id, mode, condition) — Approved. The `mode: always | conditional` plus `condition` string is sufficient for the card generator to distinguish invocation patterns without parsing template prose.

2. `inputs / outputs / mutates` type enums — Approved. The six type values (`file_path`, `structured_payload`, `config_value`, `file`, `structured_response`, `sign_off_comment`) cover the prototype card's I/O Contract diagram at the right granularity. Adding `type: file_path` vs `type: file` correctly distinguishes path arguments from file content objects.

3. `knowledge_channels` (channel integer 1-11) — Approved with note: always declare channels 1, 9, 10, 11 per-agent in this ticket (no `include_universal_channels` flag until Ticket 3 designs the convention). Channel 3 (PROJECT_CONTEXT.md) is listed in the prototype card's knowledge flow table as "On-demand" — it is acceptable to include it if the agent uses it.

4. `config_keys` + `source` field — Approved. The `source` field (`skills_config | settings | build_injected`) is additive to the existing dict structure. Checked `build_phases.py` presence: the registry parser in `config/agent_registry.json` does not read `config_keys` from registry (config_keys is a template frontmatter field only). Additive fields in YAML frontmatter are safe — no existing tooling reads config_keys with strict schema enforcement.

5. `pre_flight_reads` (source, required, condition) — Approved. The three-field schema is sufficient for knowledge-flow table row generation. `condition` is optional (omit when required: true).

6. `behavioral_patterns` (name, trigger, behavior, related_agent) — Approved. The four-field schema matches the "Key Behavioral Patterns" table in the prototype card. `related_agent: null` for single-agent patterns is the correct sentinel.

**Decision History:** DECISION 2026-06-05 10:00 [architect-review]: All six schema designs approved as-is from the prototype card (#EPIC-SelfDescribingAgents/01). No ADR required (single component, additive fields only, no cross-cutting policy decision).

**Escalation:** Branch: none. Reason: 2 files, 1 component; no always-large trigger fired.

**Delivers to python-coder:** All six field schemas approved. Proceed with implementation per the ticket's Implementation Tasks section.

### 2026-06-05 10:30 — python-coder (status: ok)
feedback-id: fb_2026-06-05_b7e9b087
completion_manifest:
  code_implemented: true
  tests_passing: true
  doc_enforcer_clean: true
  complexity_check_clean: true

Implemented all six self-description metadata deliverables. `templates/agents/python-coder.md` frontmatter extended with `pre_flight_reads` (3 entries), `inputs` (5 entries), `outputs` (5 entries), `mutates` (5 entries), `behavioral_patterns` (7 patterns matching prototype card), and `config_keys` completeness (added `source` field to existing 3 entries, added `file_size_limit_py` and `testing_context.max_test_duration_seconds`). `config/agent_registry.json` extended with `skills_invoked` (4 entries: signoff always, doc-enforcer always, complexity-reduction conditional, collector-enforcer conditional) and `knowledge_channels` (9 entries covering channels 1,2,5,6,7,8,9,10,11). JSON validated. All fields match prototype card's Auto-Generation Gap Summary — zero remaining gaps.

### 2026-06-05 11:00 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-05_4a0f0dfe
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true

**PR Review — INF-600 Ticket 1 (EPIC-SelfDescribingAgents)**

All six deliverables confirmed present and correct:

1. `skills_invoked` (4 entries): signoff/always, doc-enforcer/always, complexity-reduction/conditional, collector-enforcer/conditional — matches AC INF-600a-1.
2. `knowledge_channels` (9 entries, channels 1,2,5,6,7,8,9,10,11): all within valid range 1-11 — matches AC INF-600a-3.
3. `inputs`/`outputs`/`mutates` (5+5+5 entries): matches prototype card I/O Contract diagram — matches AC INF-600a-2.
4. `config_keys` completeness: `file_size_limit_py` and `testing_context.max_test_duration_seconds` added, `source` field on all existing entries — matches AC INF-600a-4.
5. `pre_flight_reads` (3 entries): ticket_path required, ADRs conditional, conventions conditional — matches AC INF-600a-5.
6. `behavioral_patterns` (7 patterns): all 7 from prototype card Key Behavioral Patterns table present — matches AC INF-600a-6.

Additive only — no existing fields removed, no JSON broken. `skills_used: ["signoff"]` retained as alias. Approved.

## Implementation Tasks

### architect-review

Review the schema design for all six new fields before any edits are made:

- [x] Confirm the `skills_invoked` schema (skill_id, mode, condition) is
  sufficient for the card generator to distinguish "always" from "conditional"
  invocations without reading the template body prose.
- [x] Confirm the `inputs` / `outputs` / `mutates` schema covers the full
  I/O Contract diagram from the prototype card. Specifically: verify the
  `type` enum values (`file_path`, `structured_payload`, `config_value`,
  `file`, `structured_response`, `sign_off_comment`) are the right granularity.
- [x] Confirm the `knowledge_channels` schema: channel integer 1-11 is
  sufficient as the key, and that `include_universal_channels: false` flag
  at the registry level is a reasonable optional optimization vs. always
  declaring channels 1, 9, 10, 11 per-agent.
- [x] Confirm the `config_keys` extension: adding `source` field
  (`skills_config | settings | build_injected`) to existing entries is
  backward-compatible. The existing `config_keys` format in the template
  lacks `source` — verify no existing tooling reads `config_keys` in a way
  that would break when `source` is added.
- [x] Confirm the `pre_flight_reads` schema (source, required, condition) is
  the right structure for the knowledge-flow table row generation.
- [x] Confirm the `behavioral_patterns` schema (name, trigger, behavior,
  related_agent) is the right structure for the Key Behavioral Patterns table.
- [x] Document any schema decisions as inline DECISION HISTORY comments in
  the modified files.

**Delivers to python-coder:** Approved field schemas for all six fields.

### python-coder

**Important:** Do not begin until architect-review has signed off.

**Deliverable 1 — `config/agent_registry.json`: `skills_invoked` array for python-coder**

Add `skills_invoked` array to the python-coder registry entry:

```json
"skills_invoked": [
  {"skill_id": "signoff", "mode": "always"},
  {"skill_id": "doc-enforcer", "mode": "always"},
  {"skill_id": "complexity-reduction", "mode": "conditional",
   "condition": "when flagged functions exceed complexity threshold"},
  {"skill_id": "collector-enforcer", "mode": "conditional",
   "condition": "when paths under collector/ are edited"}
]
```

Retain the existing `skills_used` field (now an alias for backward compat).

**Deliverable 2 — `config/agent_registry.json`: `knowledge_channels` array for python-coder**

Add `knowledge_channels` array to the python-coder registry entry. Reference the
prototype card's Knowledge Flow table (all 13 rows including pre-flight self-reads).
Channels that are universally injected (1, 9, 10, 11) must still be included in
the entry (no `include_universal_channels: false` flag until the registry-level
convention is designed in Ticket 3).

**Deliverable 3 — `templates/agents/python-coder.md`: `inputs`, `outputs`, `mutates`**

Add three arrays to the python-coder frontmatter. Use the prototype card's
Input/Output Contract diagram as the authoritative source:

- `inputs`: ticket_path (file_path, required), ticket body sections (structured_payload,
  required), red_baseline (config_value, not required), cited ADRs (file, conditional),
  Python conventions (file, conditional).
- `outputs`: edited/new .py files (file), completion report (structured_response),
  sign-off comment (sign_off_comment), red_baseline_results (structured_response),
  completion_manifest (structured_response).
- `mutates`: ticket frontmatter agents status (ticket frontmatter), sign-offs checklist
  (ticket body sign-offs section), implementation tasks checkboxes (ticket body),
  agent contracts AC checkboxes (ticket body, v2 only), AC coverage table (ticket body, v2 only).

**Deliverable 4 — `templates/agents/python-coder.md`: `config_keys` completeness**

Add `file_size_limit_py` to the `config_keys` block with:
- `required: false`
- `description: "Maximum lines for new .py files; referenced as {{config.file_size_limit_py}}"`
- `source: build_injected`

Add `source` field to all existing `config_keys` entries:
- `test_command_live_trader`: source `skills_config`
- `test_output_dir`: source `skills_config`
- `collector_enforcer_paths`: source `skills_config`

Also add `testing_context.max_test_duration_seconds`:
- `required: false`
- `description: "5-second ceiling for auto-run tests"`
- `source: skills_config`

**Deliverable 5 — `templates/agents/python-coder.md`: `pre_flight_reads` array**

Add `pre_flight_reads` array to frontmatter:

```yaml
pre_flight_reads:
  - source: "ticket_path"
    required: true
  - source: "docs/architecture/adrs/ADR-*.md"
    required: false
    condition: "when ticket body references ADR files"
  - source: "docs/conventions/*.md"
    required: false
    condition: "when editing modules covered by a conventions file"
```

**Deliverable 6 — `templates/agents/python-coder.md`: `behavioral_patterns` array**

Add `behavioral_patterns` array to frontmatter, with all 7 patterns from the
prototype card. Each entry must have: name, trigger, behavior, related_agent (null
when no other agent is involved). Use the "Key Behavioral Patterns" table in
`docs/agents/cards/python-coder.card.md` as the canonical source.

**Verification:** After all edits, confirm the prototype card's Auto-Generation
Gap Summary section would have zero remaining gaps if the card were regenerated
from the updated YAML sources.

## Risk & Safety

- Touches money? No.
- Touches data? No — adds fields to YAML frontmatter and JSON registry.
  The new fields are additive; no existing fields are removed or renamed.
- Reversibility? Fully reversible — removing the new YAML fields restores
  the previous state.
- Risk of regressions: low for `templates/agents/python-coder.md` (frontmatter
  additions are not read by any existing build step). Medium for
  `config/agent_registry.json` — the registry is parsed by `build_phases.py`;
  verify the registry parser does not error on unknown top-level keys.
- Dependency on Ticket 2: the card generator reads these fields, but Ticket 1
  can land before Ticket 2 (the new fields are simply unused until the generator
  is written). The architect-review on Ticket 2 should reference the Ticket 1
  schema to confirm alignment before generator implementation begins.
