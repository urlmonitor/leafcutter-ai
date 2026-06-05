---
title: "INF-600 Ticket 2: Write scripts/generate_agent_cards.py and wire into build.py"
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
  - scripts/generate_agent_cards.py
  - scripts/build.py
  - scripts/build_phases.py
agents:
  architect-review: needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
source_acs:
  - INF-600b
ac_path: docs/acceptance-criteria/infrastructure/INF-600-self-describing-agents/
ac_coverage: 0/1
---

# INF-600 Ticket 2: Write scripts/generate_agent_cards.py and wire into build.py

## Actor / Goal

In order to make agent cards a build artifact (never hand-written), we need
a `scripts/generate_agent_cards.py` script that reads each agent's template
frontmatter, registry entry, and knowledge plane mapping, then produces
`.card.md` files. The expected output for `python-coder` must match the
manually-authored prototype card at `docs/agents/cards/python-coder.card.md`.

## Context

This ticket implements INF-600b: "Agent cards are assembled during the build."

Ticket 1 (TICKET-20260605-INF600-SchemaDefinitionPrototype.md) must land
first — it adds the structured metadata fields (`skills_invoked`,
`knowledge_channels`, `inputs`/`outputs`/`mutates`, `pre_flight_reads`,
`behavioral_patterns`) that this generator reads.

The prototype card at `docs/agents/cards/python-coder.card.md` is the golden
output. The generator must produce a card for `python-coder` that is
semantically equivalent (same sections, same tables, same data) — exact
whitespace need not match. The generator should also produce valid card files
for all other agents; those cards will have sparser data until Ticket 5
(rollout) lands.

The generator is wired into `build.py` so that every `python build.py` run
regenerates the cards. Cards are written to `docs/agents/cards/`.

All ACs for this deliverable are in:
`docs/acceptance-criteria/infrastructure/INF-600-self-describing-agents/INF-600b.yaml`

## Acceptance Criteria

```gherkin
# INF-600b: Agent cards are assembled during the build
Given the build system runs (python build.py)
When generate_agent_cards.py executes as a build phase
Then for each agent template in templates/agents/
  It reads the template frontmatter (name, description, model, tools,
    portable, signoff, config_keys, inputs, outputs, mutates,
    pre_flight_reads, behavioral_patterns)
  And reads the agent's registry entry from config/agent_registry.json
    (skills_invoked, knowledge_channels, spawned_by, spawn_allowlist,
    tier, priority, auto_dispatch)
  And produces a .card.md file at docs/agents/cards/<agent-id>.card.md

Given the generator runs on python-coder
When it reads the post-Ticket-1 structured sources
Then the generated docs/agents/cards/python-coder.card.md contains:
  - ## When to Use section (auto-dispatch conditions from registry)
  - ## Knowledge Flow section (table from knowledge_channels array)
  - ## Spawn and Dependency section (mermaid flowchart from spawn graph)
  - ## Input / Output Contract section (tables/diagram from inputs/outputs/mutates)
  - ## Skills Used section (from skills_invoked array)
  - ## Configuration section (from config_keys block)
  - ## Contributor Notes section (behavioral_patterns as table)
And the generated card is semantically equivalent to the prototype card

Given an agent template with no skills_invoked (pre-Ticket-5 state)
When the generator runs on that agent
Then it produces a card with a Skills Used section showing
  the existing skills_used array (backward compat with old field)
And the build does not fail or warn for agents lacking the new fields

Given build.py runs with --dry-run
Then generate_agent_cards.py logs which files it would write
And does not write any .card.md files
```

## Sign-offs

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### architect-review

- [ ] Confirm the generator's input reading order: which field wins when both
  `skills_invoked` and the legacy `skills_used` are present? Define a precedence
  rule so `python-coder` doesn't produce a "double Skills Used" section.
- [ ] Confirm the spawn graph rendering strategy: the prototype uses a Mermaid
  `flowchart TD` with `classDef` style blocks. The generator must read
  `spawned_by` and `spawn_allowlist` from the registry and derive the flowchart.
  Confirm the Mermaid template approach (string template with substitution) vs.
  a proper graph library is acceptable.
- [ ] Confirm where the knowledge plane mapping lives for the generator: the
  `knowledge_channels` array in the registry entry (Ticket 1 deliverable) is the
  source. Confirm the generator does not need to also read
  `docs/architecture/agent_knowledge_plane.md` at build time.
- [ ] Confirm the dry-run integration point: should `generate_agent_cards.py`
  be a new function in `build_phases.py` (matching the pattern of
  `build_vision()`, `build_ticket_lifecycle()`, etc.) or a standalone script
  invoked by `build.py`? Recommend the `build_phases.py` function pattern for
  consistency.
- [ ] Confirm the output path: `docs/agents/cards/` already contains the
  hand-authored `python-coder.card.md`. The generator must overwrite it on
  each build. Confirm this is acceptable (cards are generated, not hand-edited).
- [ ] Define a minimal card template for agents that have none of the new
  structured fields yet (i.e., pre-Ticket-5 agents). The card should still
  compile from the existing `description`, `model`, `tools`, `spawned_by`,
  and `skills_used` fields without erroring.

**Delivers to python-coder:** Approved architecture for the generator module
and its integration into build.py.

### test-writer

Write tests before python-coder begins implementation.

Create `unit_tests/test_generate_agent_cards.py`:

- `test_card_generated_for_python_coder_matches_prototype_sections`:
  Given a fully-populated python-coder fixture (post-Ticket-1 fields),
  call `generate_card(agent_id="python-coder", template_path=<fixture>,
  registry_entry=<fixture>)` and assert the output contains the required
  section headings: `## When to Use`, `## Knowledge Flow`,
  `## Input / Output Contract`, `## Skills Used`, `## Configuration`,
  `## Contributor Notes`.

- `test_card_generated_for_minimal_agent`:
  Given an agent fixture with only `name`, `description`, `model`, `tools`,
  `skills_used: ["signoff"]`, and no new structured fields,
  assert the generator produces a card without raising an exception
  and the card contains at least `## Skills Used`.

- `test_skills_invoked_takes_precedence_over_skills_used`:
  Given an agent with both `skills_invoked` and `skills_used`,
  assert the Skills Used section uses `skills_invoked` data
  and does not double-list skills.

- `test_knowledge_flow_table_populated_from_registry`:
  Given registry entry with `knowledge_channels: [{channel: 1, source: "Root CLAUDE.md",
  injection_mode: "always", description: "..."}]`,
  assert the generated Knowledge Flow section contains a table row for channel 1.

- `test_dry_run_writes_no_files`:
  Given dry_run=True, assert no files are written to `docs/agents/cards/`.

- `test_behavioral_patterns_produce_table`:
  Given `behavioral_patterns: [{name: "Stop-and-Ask", trigger: "...",
  behavior: "...", related_agent: "sql-coder"}]`,
  assert the Contributor Notes section contains a markdown table row
  for "Stop-and-Ask".

- `test_empty_behavioral_patterns_renders_no_conditional_behaviors_message`:
  Given `behavioral_patterns: []`,
  assert the Contributor Notes section renders the fallback message
  "No conditional behaviors — this agent follows a single fixed execution path"
  (matching INF-600a-6-i).

- `test_build_phase_integration`:
  Call `build_agent_cards(target_root=<tmp_dir>, config={}, dry_run=False, force=False)`
  and assert it returns an integer (written file count) and the card file exists.

**Depends on architect-review:** Approved generator architecture.

### python-coder

**Important:** Do not begin until architect-review and test-writer have signed off.

**Deliverable 1 — `scripts/generate_agent_cards.py`**

Write the generator module. Key design requirements:

1. **Entry point**: `generate_card(agent_id, template_frontmatter, registry_entry) -> str`
   Returns the complete markdown card content as a string.

2. **Section rendering functions** (one per card section):
   - `render_when_to_use(registry_entry)` — auto-dispatch conditions from
     `auto_dispatch`, `spawned_by`, negative-use cases from template prose.
   - `render_knowledge_flow(registry_entry)` — table from `knowledge_channels` array.
   - `render_spawn_diagram(registry_entry)` — Mermaid flowchart from
     `spawned_by` + `spawn_allowlist`.
   - `render_io_contract(template_frontmatter)` — tables from
     `inputs`, `outputs`, `mutates` arrays.
   - `render_skills(template_frontmatter, registry_entry)` — `skills_invoked`
     takes precedence over `skills_used`.
   - `render_configuration(template_frontmatter)` — from `config_keys` block.
   - `render_behavioral_patterns(template_frontmatter)` — table from
     `behavioral_patterns`; renders fallback when array is empty.
   - `render_tools(template_frontmatter)` — from `tools` field.

3. **Graceful degradation**: every render function must handle absent fields
   gracefully (missing key → omit section or render minimal placeholder).
   The generator must not raise KeyError for any pre-Ticket-5 agent template.

4. **YAML frontmatter parsing**: use `yaml.safe_load()` on the content between
   the first and second `---` delimiters. Do not use the full template body
   for data — frontmatter only.

5. **Output path**: `docs/agents/cards/<agent-id>.card.md`. Create
   `docs/agents/cards/` if it does not exist.

6. **Error handling**: all file I/O wrapped in `try/except OSError`.
   No bare excepts. No silent swallows. (Project error handling policy.)

7. **Minimal card header**: every card must begin with YAML frontmatter
   (`agent_id`, `title`, `type: card`, `status: active`,
   `created: <today>`, `card_version: "generated"`).

**Deliverable 2 — `build_agent_cards()` in `scripts/build_phases.py`**

Add a new phase function following the `build_vision()` pattern:

```python
def build_agent_cards(target_root, config, dry_run, force) -> int:
    """Generate .card.md files for all agent templates."""
    ...
```

- Reads all `.md` files in `target_root / "templates" / "agents"` (excluding
  `_*.md` helper files).
- For each template, reads YAML frontmatter and the corresponding registry
  entry from `config/agent_registry.json`.
- Calls `generate_card(...)` and writes to `docs/agents/cards/<id>.card.md`.
- Respects `dry_run` (no writes) and `force` (overwrite existing).
- Returns count of written (or would-write) files.

**Deliverable 3 — Wire into `scripts/build.py`**

Add `build_agent_cards(...)` to the main build pipeline, after the agent
template compilation phase. The cards depend on compiled templates being
present in `docs/agents/cards/`, so it runs last in the templates phase.

**Verification:** After implementation, run:
```bash
python scripts/build.py --target-dir /home/henzeh/projects/leafcutter
```
and confirm `docs/agents/cards/python-coder.card.md` is regenerated with the
same sections as the prototype.

## Risk & Safety

- Touches money? No.
- Touches data? No — generates read-only documentation files.
- Reversibility? The generator overwrites `docs/agents/cards/python-coder.card.md`
  on each build. The hand-authored prototype would be overwritten. Ensure the
  prototype is preserved in git history and that the generated output is checked
  in (committed) so reviewers can diff generator output against the prototype.
- Risk of regressions: low. The generator is a new code path; existing build
  phases are not modified except to call the new function.
- The generator reads `config/agent_registry.json` — ensure the Ticket 1
  schema additions did not break the registry's existing parser paths.
