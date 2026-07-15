---
title: "Wire knowledge-query skill into PO v3, BA v3, and IT PO v3 agent templates"
status: todo
components:
  - ac_driven_dev
created: 2026-06-05
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/agents/product-owner-v3.md
  - templates/agents/business-analyst-v3.md
  - templates/agents/it-po-v3.md
  - config/agent_registry.json
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  llm-expert: needed
ac_coverage: 0/9
ac_traceability:
  l1: ACD-300e
  l2:
    - ACD-300e-1
    - ACD-300e-2
    - ACD-300e-3
    - ACD-300e-4
    - ACD-300e-5
  l3:
    - ACD-300e-2-i
    - ACD-300e-2-ii
    - ACD-300e-5-i
  ac_path: docs/acceptance-criteria/ac-driven-dev/
---

# Wire knowledge-query skill into PO v3, BA v3, and IT PO v3 agent templates

## Actor / Goal

In order to ground every AC-authoring decision in the full project context rather
than the limited set of files each agent reads directly, we need to wire the
`knowledge-query` skill into the three v3 AC-authoring agent templates (PO v3,
BA v3, IT PO v3). Each agent must invoke `knowledge-query` during its
knowledge-acquisition phase, handle empty and error results gracefully, cite
graph findings in its output, and not block when the graph is empty.

This ticket is **template/prompt editing work only** — no Python code changes.

## Context

The `knowledge-query` skill (`templates/skills/knowledge-query/SKILL.md`) wraps
`python scripts/knowledge_query.py` and provides cross-surface graph search
across agents, skills, tickets, docs, ADRs, and hooks. The three v3 authoring
agents currently have no awareness of this skill.

The changes required are additive: the knowledge-query invocation block is
inserted into the existing S1/§1 knowledge-acquisition section of each template.
No existing S1 steps are removed or renumbered. The zero-result and error
handling prose is added to all three templates so behaviour is consistent.

Key reference: `templates/skills/knowledge-query/SKILL.md` — the exact Bash
invocation syntax the agent must emit is:

```bash
python scripts/knowledge_query.py --query <term>
python scripts/knowledge_query.py --query <term> --surface docs
python scripts/knowledge_query.py --surface agents
python scripts/knowledge_query.py --surface skills
python scripts/knowledge_query.py --query <component-name>
```

The `config/agent_registry.json` `skills_used` arrays for all three agents are
currently empty (`[]`) and must be updated to include `"knowledge-query"`.

## Acceptance Criteria

### ACD-300e-1 — Frontmatter skills_used declaration (all three templates + registry)

- [ ] AC-1: `templates/agents/product-owner-v3.md` frontmatter `skills_used` list includes `"knowledge-query"` alongside the existing `"ac-tree-split"` entry, the frontmatter remains valid YAML, and `"knowledge-query"` resolves to `templates/skills/knowledge-query/SKILL.md` via the standard skill lookup path.
- [ ] AC-2: `templates/agents/business-analyst-v3.md` frontmatter `skills_used` list includes `"knowledge-query"` alongside the existing `"ac-tree-split"` entry, the frontmatter remains valid YAML.
- [ ] AC-3: `templates/agents/it-po-v3.md` frontmatter `skills_used` list includes `"knowledge-query"` (the template currently has no `skills_used` key — add it), the frontmatter remains valid YAML.
- [ ] AC-4: `config/agent_registry.json` entries for `product-owner-v3`, `business-analyst-v3`, and `it-po-v3` each have `"knowledge-query"` added to their `skills_used` array (currently `[]`). All other fields in each registry entry are unchanged.

### ACD-300e-2 — PO v3 S1 knowledge-query invocation block

- [ ] AC-5: `templates/agents/product-owner-v3.md` S1 section contains a new knowledge-query step inserted after the existing five read steps, specifying: (a) a keyword query derived from the user's request with `--surface docs`, (b) a component-scoped query using the component name identified in the preceding S1 steps, and (c) an instruction to use the returned node list to identify overlapping L0/L1 ACs, current-behaviour docs, and related skills or agents.
- [ ] AC-6: The PO v3 S1 knowledge-query step includes the exact Bash invocation syntax from `SKILL.md` (`python scripts/knowledge_query.py --query <term> --surface docs` and `python scripts/knowledge_query.py --query <component-name>`). The step is additive — no existing S1 steps are removed or renumbered.
- [ ] AC-7: The PO v3 S1 step instructs the agent to defer the component-scoped query until after the component has been identified (Step 1), so the query is never invoked with an unknown component name.
- [ ] AC-8: The PO v3 S1 step instructs the agent that the knowledge-query step is mandatory — it must not be skipped even if the preceding file reads returned sufficient context.

### ACD-300e-3 — BA v3 §1 knowledge-query invocation block

- [ ] AC-9: `templates/agents/business-analyst-v3.md` §1 Knowledge Acquisition Protocol contains a new knowledge-query step positioned after the L1/L0 read step (Step 1) and the index.yaml traversal (Step 2) but before the decomposition planning. The step specifies: (a) a component-name query to discover all nodes related to the target component across all surfaces, and (b) a keyword query derived from the L1 title to discover cross-component behaviors with similar concerns.
- [ ] AC-10: The BA v3 §1 knowledge-query step instructs the agent to use the returned node list to identify: (a) existing L2/L3 ACs in sibling components that address similar behaviors, (b) skills and agents already registered for the target domain, and (c) architecture docs and ADRs that constrain the behaviors being decomposed.
- [ ] AC-11: The BA v3 §1 step instructs the agent that any cross-component L2 patterns discovered are noted in the assumption log with source citation `"knowledge-query result"`, and that the step is mandatory even if the §1 file reads returned sufficient context.

### ACD-300e-4 — IT PO v3 S1 knowledge-query invocation block

- [ ] AC-12: `templates/agents/it-po-v3.md` S1 Knowledge Acquisition section contains a new knowledge-query step positioned after the L2/L3 AC file reads (Step 1) and before the agent registry read (Step 2). The step specifies three queries: (a) `--surface agents` to list all registered agents and descriptions, (b) `--surface skills` to list all registered skills, and (c) a component-name query to discover architecture docs, ADRs, and hook registrations.
- [ ] AC-13: The IT PO v3 S1 step instructs the agent to use the returned node list to inform: (a) `assigned_agent` selection by matching AC behaviors to graph-discovered capabilities, (b) `delivers_to`/`expects_from` contract design using existing inter-agent contracts in sibling ACs, and (c) `doc_links` population using architecture docs and ADRs discovered via the graph.
- [ ] AC-14: The IT PO v3 S1 step does not direct the agent to read any source code files, in compliance with ADR-009. The step is mandatory even if the S1 registry reads returned sufficient context.

### ACD-300e-2-i and ACD-300e-2-ii — Zero-result and error handling (all three templates)

- [ ] AC-15: All three agent templates contain a zero-result handling instruction with the exact log message format: `"knowledge-query returned 0 nodes for '<query-term>' — no related context discovered, proceeding with file-based reads only"`. On zero results the agent continues its normal workflow without error, retry, deduplication warning, or placeholder fields in its output.
- [ ] AC-16: All three agent templates contain an error-handling instruction covering both script-not-found and non-zero exit code scenarios, with the exact log message format: `"knowledge-query failed: <error message> — skipping graph context, proceeding with file-based reads only"`. The agent does NOT abort, does NOT return `status: blocked`, does NOT retry, and does NOT surface the error to the user unless verbose output was requested.
- [ ] AC-17: The zero-result and error-handling instructions are consistent in format and continuation behaviour across all three templates — same log message structure, same no-retry rule, same no-confirmation-gate rule.

### ACD-300e-5 — Citation and deduplication behaviour (all three templates)

- [ ] AC-18: All three agent templates instruct the agent that when a knowledge-graph node overlaps with a behavior it is about to author or enrich, the agent presents the overlap to the user before proceeding, stating the node's surface, title, and id in the format `"[<surface>] <title> (<id>)"`. This presentation must occur at the user confirmation gate — it does not halt the agent.
- [ ] AC-19: All three agent templates instruct the agent that when the overlapping node is an existing AC, the deduplication warning includes the AC's id and title (e.g., `"ACD-200a-1 already specifies this behavior — skipping or creating a variant"`), and when the overlap is with a doc or ADR, the path is added to the new AC's `doc_links` with `relationship: context`.
- [ ] AC-20: All three agent templates instruct the agent that when no overlapping nodes are found, the agent logs the assumption `"knowledge-query returned no related nodes for <query> — proceeding with file-based context only"` and does not block.

### ACD-300e-5-i — Empty-graph handling (all three templates)

- [ ] AC-21: All three agent templates explicitly state that an empty graph (zero nodes, zero edges) is a normal condition on a freshly installed project, not an error. The agent treats the empty result identically to a zero-result response: logs the assumption and proceeds. The agent does NOT prompt the user with any confirmation gate when the graph is empty. The absence of graph context does not cause any field in the output AC YAML to be left blank or set to a placeholder value.

## AC Coverage

| AC    | Test | Implementation | Validated |
|-------|------|----------------|-----------|
| AC-1  |      | product-owner-v3.md frontmatter skills_used | |
| AC-2  |      | business-analyst-v3.md frontmatter skills_used | |
| AC-3  |      | it-po-v3.md frontmatter skills_used | |
| AC-4  |      | config/agent_registry.json skills_used arrays | |
| AC-5  |      | product-owner-v3.md S1 knowledge-query step | |
| AC-6  |      | product-owner-v3.md S1 Bash syntax | |
| AC-7  |      | product-owner-v3.md S1 deferred component query | |
| AC-8  |      | product-owner-v3.md S1 mandatory instruction | |
| AC-9  |      | business-analyst-v3.md §1 knowledge-query step | |
| AC-10 |      | business-analyst-v3.md §1 node-use instructions | |
| AC-11 |      | business-analyst-v3.md §1 assumption-log instruction | |
| AC-12 |      | it-po-v3.md S1 knowledge-query step (three queries) | |
| AC-13 |      | it-po-v3.md S1 node-use instructions | |
| AC-14 |      | it-po-v3.md S1 ADR-009 compliance | |
| AC-15 |      | zero-result log message in all three templates | |
| AC-16 |      | error-handling instruction in all three templates | |
| AC-17 |      | consistency of handling across all three templates | |
| AC-18 |      | overlap citation format in all three templates | |
| AC-19 |      | deduplication warning + doc_links in all three templates | |
| AC-20 |      | no-overlap assumption log in all three templates | |
| AC-21 |      | empty-graph normal-condition statement in all three templates | |

## Agent Contracts

### llm-expert

- [ ] AC-1: `product-owner-v3.md` frontmatter `skills_used` includes `"knowledge-query"` alongside `"ac-tree-split"`.
- [ ] AC-2: `business-analyst-v3.md` frontmatter `skills_used` includes `"knowledge-query"` alongside `"ac-tree-split"`.
- [ ] AC-3: `it-po-v3.md` frontmatter gains a `skills_used` key containing `"knowledge-query"`.
- [ ] AC-4: `config/agent_registry.json` `skills_used` arrays updated for all three agents.
- [ ] AC-5 through AC-8: PO v3 S1 knowledge-query block added per ACD-300e-2 criteria.
- [ ] AC-9 through AC-11: BA v3 §1 knowledge-query block added per ACD-300e-3 criteria.
- [ ] AC-12 through AC-14: IT PO v3 S1 knowledge-query block added per ACD-300e-4 criteria.
- [ ] AC-15 through AC-17: Zero-result and error-handling prose added to all three templates per ACD-300e-2-i and ACD-300e-2-ii.
- [ ] AC-18 through AC-20: Citation and deduplication prose added to all three templates per ACD-300e-5.
- [ ] AC-21: Empty-graph normal-condition statement added to all three templates per ACD-300e-5-i.

**Delivers to pr-reviewer:**
```
Four modified files:
  - templates/agents/product-owner-v3.md (frontmatter + S1 section modified)
  - templates/agents/business-analyst-v3.md (frontmatter + §1 section modified)
  - templates/agents/it-po-v3.md (frontmatter + S1 section modified)
  - config/agent_registry.json (skills_used arrays updated for three entries)
All changes are additive — no existing prose removed, no sections renumbered.
```

**Depends on upstream:** None. All required reference material is available:
`templates/skills/knowledge-query/SKILL.md` exists, all three agent templates
exist, and `config/agent_registry.json` exists.

### pr-reviewer

Reviews the four modified files for:
- Additive-only constraint: no existing S1/§1 steps removed or renumbered.
- Consistent log message format across all three templates.
- Exact Bash syntax matches `templates/skills/knowledge-query/SKILL.md`.
- ADR-009 compliance in the IT PO v3 template (no source-code read instructions added).
- Valid YAML frontmatter in all three agent templates.

**Depends on llm-expert:** Enriched files from the llm-expert deliverable above.

## Implementation Notes

### IT PO v3 — skills_used frontmatter

The `it-po-v3.md` template currently has no `skills_used` key in frontmatter.
Add it as:

```yaml
skills_used:
  - knowledge-query  # Loaded during S1 to query agents, skills, and component docs.
```

### Placement of the knowledge-query step in each template

**PO v3 — S1:**
Insert after the existing Step 5 (`Read README.md and any customer-facing docs`).
Label it Step 6. No existing steps are renumbered — the new step extends the
existing numbered list.

**BA v3 — §1:**
Insert after Step 2 (`Read index.yaml and traverse the component tree`) but
before Step 3 (`Load standing ACs`). Label it Step 2a (or renumber Step 3
onward — implementer's choice, but the step must be positioned so that the
component is known and L1/L0 have been read before the query fires).

**IT PO v3 — S1:**
Insert after Step 1 (`Read the L2/L3 AC files to enrich`) and before Step 2
(`Read the agent registry`). Label it Step 1a or renumber — same convention
as BA v3. The component is known from the AC files read in Step 1.

### Bash invocation syntax (verbatim from SKILL.md)

```bash
# Keyword query restricted to docs surface
python scripts/knowledge_query.py --query <term> --surface docs

# Component-scoped query (all surfaces)
python scripts/knowledge_query.py --query <component-name>

# All agents
python scripts/knowledge_query.py --surface agents

# All skills
python scripts/knowledge_query.py --surface skills
```

### Zero-result log message (copy verbatim into all three templates)

```
"knowledge-query returned 0 nodes for '<query-term>' — no related context
discovered, proceeding with file-based reads only"
```

### Error-handling log message (copy verbatim into all three templates)

```
"knowledge-query failed: <error message> — skipping graph context, proceeding
with file-based reads only"
```

### Empty-graph statement (copy verbatim into all three templates)

The template must state that zero nodes and zero edges is the normal initial
state of a freshly installed project and is not an error condition.

### Constraint — do NOT touch

- `templates/workflows/create-ticket.md`
- `templates/agents/business-analyst.md`
- `templates/agents/create-ticket.md`
- `templates/agents/refinement.md`
- Any `templates/skills/ticket-authoring/SKILL.md`
- The `criteria` field of any existing AC YAML file

## Sign-offs

- [ ] llm-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## AC Traceability

| AC ID        | Level | Title | Agent |
|--------------|-------|-------|-------|
| ACD-300e-1   | L2 | Each authoring agent template declares knowledge-query in its skills_used frontmatter | llm-expert |
| ACD-300e-2   | L2 | PO v3 queries the knowledge graph during S1 to discover related L0/L1 nodes before framing | llm-expert |
| ACD-300e-2-i | L3 | Agent proceeds with baseline context when knowledge-query returns no matching nodes | llm-expert |
| ACD-300e-2-ii| L3 | Agent degrades gracefully when knowledge-query fails with an error | llm-expert |
| ACD-300e-3   | L2 | BA v3 queries the knowledge graph during §1 to discover related L2/L3 patterns and cross-component behaviors | llm-expert |
| ACD-300e-4   | L2 | IT PO v3 queries the knowledge graph during S1 to discover agent capabilities and architecture relationships | llm-expert |
| ACD-300e-5   | L2 | Agents cite knowledge-graph findings in their output to support deduplication and cross-referencing | llm-expert |
| ACD-300e-5-i | L3 | Agents do not block when the knowledge graph is entirely empty (fresh project) | llm-expert |

AC files: `docs/acceptance-criteria/ac-driven-dev/ACD-300e*.yaml`

## Out of Scope

- Python implementation changes to `scripts/knowledge_query.py` — the script already exists and works.
- Changes to the knowledge-query `SKILL.md` itself.
- Changes to v1 agents (`business-analyst.md`, `business-analyst-v2.md`, etc.).
- Changes to any `templates/workflows/` file.
- Adding automated tests for the template changes — this is prompt/template work; validation is human review via pr-reviewer.

## Risk & Safety

- Touches money? No.
- Touches data? No — template and registry edits only; no user data affected.
- Reversibility? All changes are additive prose insertions into Markdown and a JSON
  array update. Reverting requires removing the added step blocks and reverting the
  JSON arrays.
- Risk of regressions: low. The knowledge-query step is additive and its failure
  path explicitly continues the normal workflow rather than blocking it.
