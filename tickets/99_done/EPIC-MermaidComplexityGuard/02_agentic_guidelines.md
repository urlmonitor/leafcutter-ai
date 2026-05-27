---
title: "Agentic split guidelines in write-c4-diagram skill + architecture-diagram-author"
status: done
components:
  - architecture_docs
created: 2026-05-26
last_updated: 2026-05-26
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
files_touched:
  - templates/skills/write-c4-diagram/SKILL.md
  - templates/agents/architecture-diagram-author.md
agents:
  architect-review: not_needed
  python-coder: not_needed
  test-writer: not_needed
  test-runner: not_needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
  sql-coder: not_needed
---

# 02: Agentic split guidelines in skill + agent prompt

## Goal

Add a "Single Concept Rule" to the write-c4-diagram skill and a matching
guardrail step to the architecture-diagram-author agent prompt, so the agent
proactively splits diagrams that mix unrelated concerns instead of producing
one overloaded diagram.

## Context

The write-c4-diagram skill has 9 sections governing diagram authoring but none
address conceptual scope. The architecture-diagram-author agent follows a
linear 7-step process (load skill → determine tier → allocate filename →
scaffold → complete → validate → return payload) with no split-detection step.

When a user requests "document the auth + authoring flow", the agent currently
produces one diagram mixing Entra login with in-app authoring — two distinct
temporal phases and bounded contexts connected only by a session token. These
should be separate diagrams with cross-links.

## Acceptance Criteria

```gherkin
Given a request to document two distinct user journeys in one diagram
When the architecture-diagram-author evaluates the single-concept rule
Then it produces separate diagrams for each journey with cross-links

Given a request to document "login with Entra + authoring flow"
When the agent runs the split criteria check
Then it identifies two bounded contexts (identity vs. business domain)
And it identifies two temporal phases (auth completes before authoring begins)
And it produces two separate diagram files linked by related_diagrams frontmatter

Given a request that genuinely covers one concept with many nodes
When the agent runs the split criteria check
Then it proceeds with one diagram (the rule is about concepts, not node count)

Given the write-c4-diagram skill is loaded by any agent
When the agent reads Section 2a
Then it finds the three split criteria with examples and the cross-linking recipe
```

## Implementation Details

### Change 1: write-c4-diagram SKILL.md — Add Section 2a

Insert a new section between existing Section 2 (flight_level decision tree)
and Section 3 (diagram format rule):

**Section 2a: Single Concept Rule**

Content to add:

> Before proceeding to scaffold, evaluate whether the requested diagram covers
> a single concept. A diagram MUST explain exactly **one concept, one flow, or
> one boundary**. Apply these three split criteria:
>
> 1. **Distinct actors** — Count the actors (user roles, external systems,
>    subsystems) that initiate independent flows. If >1 actor initiates a flow
>    that could be understood without the other → split into separate diagrams.
>
> 2. **Distinct temporal phases** — If you would describe the diagram as "first
>    X happens, then later Y happens" and X is complete before Y begins → split.
>    Each phase gets its own diagram.
>
> 3. **Distinct bounded contexts** — If two parts of the diagram belong to
>    different domains (e.g. identity/auth vs. business logic) and connect only
>    through a single handoff (token, session, API call) → split and cross-link.
>
> **When splitting:**
> - Run the scaffold (§4) once per diagram, each with its own filename
> - Add `related_diagrams:` to each file's frontmatter listing the sibling paths
> - Add a `See also: [title](path)` line after the mermaid block in each file
> - The parent doc's `children:` list must include all split diagrams
>
> **When NOT to split:**
> - A single flow with many steps (that's just a long sequence — keep it, but
>   consider whether it exceeds the pre-commit complexity thresholds)
> - Components within one bounded context that collaborate tightly
> - A system context (L1) showing one system + its external dependencies
>
> **Example — split required:**
> Request: "Document the login + content authoring flow"
> - Entra login = identity bounded context, temporal phase 1
> - Content authoring = business domain, temporal phase 2
> - Connection: session token handoff
> - Result: two diagrams, cross-linked via `related_diagrams:` and `See also:`
>
> **Example — no split needed:**
> Request: "Document the candle data ingestion pipeline"
> - Single bounded context (market data)
> - Single temporal flow (fetch → transform → store)
> - Result: one diagram

### Change 2: architecture-diagram-author.md — Add Step 2a

Insert between existing Step 2 (Determine the Tier) and Step 3 (Allocate the
Filename):

**Step 2a — Single Concept Check**

Content to add:

> Before allocating a filename, evaluate the single-concept rule from the
> write-c4-diagram skill (§2a). Apply the three split criteria:
>
> 1. Count distinct actors initiating independent flows
> 2. Check for distinct temporal phases
> 3. Check for distinct bounded contexts
>
> **If any criterion triggers:**
> - Inform the user that the request will produce N separate diagrams
> - Proceed to Step 3 once per diagram (each gets its own sequence number
>   and scaffold call)
> - After all diagrams are complete, cross-link them via `related_diagrams:`
>   frontmatter and `See also:` prose links
> - Return one structured payload per diagram in the Step 7 response
>
> **If the diagram would exceed pre-commit complexity thresholds** (>15 nodes
> for flowchart/C4, >8 participants for sequence, >4 boundaries for any type),
> flag this to the user and recommend splitting even if the single-concept
> criteria don't trigger — the pre-commit hook will warn on commit.

## Files Touched

| File | Action | What Changes |
|---|---|---|
| `templates/skills/write-c4-diagram/SKILL.md` | EDIT | Insert Section 2a between §2 and §3 |
| `templates/agents/architecture-diagram-author.md` | EDIT | Insert Step 2a between Step 2 and Step 3 |

## Out of Scope

- Modifying existing diagrams to comply with the new rule
- Adding split detection to agents other than architecture-diagram-author
- Automated splitting (the agent decides and informs; it doesn't silently split)

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request
