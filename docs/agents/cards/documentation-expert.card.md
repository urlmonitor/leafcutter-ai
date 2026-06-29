---
agent_id: documentation-expert
title: "Agent Card: documentation-expert"
description: "Diataxis-routing documentation orchestrator that classifies doc requests by intent and dispatches to specialist sub-agents."
type: card
status: active
created: 2026-06-05
card_version: "generated"
---
# documentation-expert

**Diataxis-routing documentation orchestrator. Classifies a "write or update
a doc" request by intent (do / decide-record / design / look up / understand),
dispatches to the matching specialist sub-agent (how-to-author, adr-author,
architecture-author, reference-author, explanation-author), and returns a
unified payload listing every doc file produced.
Use when: user says "write a doc for X"; "document this feature"; "add a
how-to for Y"; "write an ADR for Z"; "update the reference for W";
"explain why V works this way"; or asks to "document this end-to-end".
Auto-triggers on any request whose primary verb is "document", "write a doc",
"update a doc", or "add documentation".**

| Field | Value |
|-------|-------|
| Model | sonnet |
| Tier | phase |
| Priority | 10 |
| Portable | Yes |
| Sign-off capable | Yes |

---

## When to Use

### Spawned By

- `ticket-supervisor`
---

## Knowledge Flow

*No knowledge channels declared.*

---

## Spawn and Dependency

```mermaid
flowchart TD
    classDef supervisor fill:#dbeafe,stroke:#2563eb,stroke-width:2px
    classDef phase fill:#d1fae5,stroke:#059669,stroke-width:2px
    classDef utility fill:#f3f4f6,stroke:#4b5563,stroke-width:2px
    classDef target fill:#fee2e2,stroke:#dc2626,stroke-width:3px

    ticket_supervisor["ticket-supervisor\n(supervisor tier)"]:::supervisor
    documentation_expert["documentation-expert\n(phase tier, priority 10)"]:::target
    research_agent["research-agent\n(utility tier)"]:::utility
    adr_author["adr-author\n(phase tier)"]:::phase
    architecture_diagram_author["architecture-diagram-author\n(phase tier)"]:::phase
    explanation_author["explanation-author\n(phase tier)"]:::phase
    how_to_author["how-to-author\n(phase tier)"]:::phase
    reference_author["reference-author\n(phase tier)"]:::phase
    glossary_triage["glossary-triage\n(phase tier)"]:::phase

    ticket_supervisor -->|dispatches| documentation_expert
    documentation_expert -->|spawns| research_agent
    documentation_expert -->|spawns| adr_author
    documentation_expert -->|spawns| architecture_diagram_author
    documentation_expert -->|spawns| explanation_author
    documentation_expert -->|spawns| how_to_author
    documentation_expert -->|spawns| reference_author
    documentation_expert -->|spawns| glossary_triage
```
---

## Input / Output Contract

*No structured I/O contract declared.*
---

## Tools Available

| Tool |
|------|
| `Bash` |
| `Read` |
| `Edit` |
| `Write` |
| `Agent` |
---

## Skills Used

| Skill | Mode | Condition |
|-------|------|-----------|
| `route-knowledge` | conditional | — |
| `signoff` | conditional | — |
| `direct-write` | conditional | Glossary coverage lint — agent writes directly to docs/glossary.md and docs/glossary_blacklist.md for simple glossary updates, without spawning a specialist |
---

## Configuration

*No configuration keys declared.*
---

## Behavioral Patterns

| Pattern | Trigger | Action | Decision Boundary |
|---------|---------|--------|-------------------|
| `delegate-to-specialist` | Request requires a full diataxis-typed document (how-to guide, ADR, C4 diagram, explanation, or reference page), OR the guide exceeds ~5 implementation steps, OR user explicitly names a doc type | Classify intent → dispatch matching specialist via Agent tool | Delegates when: output is a standalone doc requiring diataxis structure; guide > 5 steps; ADR-level record needed; C4 diagram requested |
| `direct-write` | Simple inline update to an existing doc — add a paragraph, fix a table row, append a short note — AND no new diataxis-structured document is required | Write or edit the file directly using Read/Edit/Write tools; no specialist spawned | Handles directly when: targeting an existing file; no genre routing needed; single-file patch of low structural complexity |
| `glossary-coverage-lint` | Novel project terms detected in any written output | Spawn `glossary-triage` to classify candidate terms | Always runs post-write as a conditional delegation |

---

## Contributor Notes

This agent has two execution paths: **delegation** (complex docs → specialist sub-agents) and **direct-write** (simple inline edits → own tools). The `spawn_allowlist` lists all specialists that may be delegated to for complex cases. The `behavioral_patterns` table above defines the decision boundary between the two paths.
