---
title: "Add portable route-knowledge skill for user-triggered knowledge capture"
status: todo
components:
  - build_pipeline
  - config_loader
created: 2026-05-26
depends_on:
  - TICKET-20260526-knowledge_plane_architecture_doc.md
priority: high
tags:
  - knowledge-management
  - skills
  - documentation-expert
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
requires_documentation: []
files_touched:
  - leafcutter-ai/templates/skills/route-knowledge/SKILL.md
  - leafcutter-ai/config/skill_registry.json
  - leafcutter-ai/templates/agents/documentation-expert.md
agents:
  architect-review: not_needed
  python-coder: not_needed
  test-writer: not_needed
  test-runner: not_needed
  documentation-expert: signed_off
  change-scope-reviewer: not_needed
  pr-reviewer: signed_off
  commit: needed
  pull-request: not_needed
  status-checker: not_needed
  sql-coder: not_needed
  sql-query: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
user_facing_surface: null
---

# Add portable route-knowledge skill for user-triggered knowledge capture

## Goal

Create a portable `route-knowledge` skill that classifies a piece of knowledge into
the correct persistence surface and returns a structured routing decision. This
formalises the ad-hoc routing behaviour that currently varies by agent when a user
says "remember this", "capture this somewhere", or "we should write this down".

## Context

Today, when a user triggers knowledge persistence, the destination is decided
informally and differently depending on which agent is listening. The existing
`route-learning` skill (referenced in `leafcutter-ai/docs/architecture/agent_knowledge_system.md`)
covers the signoff §7 / phase-agent path, but there is no skill that:

1. Handles user-initiated "remember X" triggers from the main conversation thread.
2. Acts as a pre-flight gate for `documentation-expert` (so doc-expert only performs
   within-Diataxis routing once this skill has confirmed a doc surface is the right
   destination at all).
3. Covers the full surface taxonomy including memory subtypes, per-folder READMEs,
   agent frontmatter, glossary flow, `settings.json`, ticket bodies, and
   `skills_config.json`.

The sibling ticket `TICKET-20260526-knowledge_plane_architecture_doc.md` (must land
first or in parallel) will produce the canonical "knowledge-distribution" architecture
doc that this skill cites as its surface-inventory source of truth.

### Surface taxonomy this skill must cover

| Surface | Condition |
|---|---|
| `memory/*.md` (user / feedback / project / reference subtypes) | User-specific guidance about how Claude should behave for this user |
| Root `CLAUDE.md` — inline entry | Broad project-wide know-how every agent should see; fits in a short bullet or paragraph |
| Root `CLAUDE.md` — TOC link | The content is too long for inline; a heading + link to a deeper doc is correct |
| Per-folder `README.md` | Folder-scoped context injected when an agent works in that folder |
| Agent `PROJECT_CONTEXT.md` / frontmatter | Domain knowledge a specific worker agent needs |
| ADR (`docs/architecture/adrs/ADR-*.md`) | Architectural decision + rationale |
| Architecture doc (C4) | Structural / component description |
| How-to (Diataxis) | Step-by-step task procedure |
| Reference (Diataxis) | Lookup table, schema dictionary, enum list |
| Explanation (Diataxis) | Conceptual understanding, "why does X work this way?" |
| Glossary (via `glossary-triage` flow) | Novel project terms; never hand-edited |
| `settings.json` (via `update-config`) | Hooks, permissions, env vars |
| Ticket frontmatter / body | Work-in-progress scope items |
| `skills_config.json` | Onboarding-time configuration values |

### CLAUDE.md inline vs TOC-link rule (from user)

> "CLAUDE.md at root should have broad project know-how AND a TOC."

The decision tree must distinguish:
- **Inline**: short, universal fact or rule — add directly as a bullet/paragraph.
- **TOC link**: the content warrants its own section or file; add a heading in
  CLAUDE.md that links to `docs/` or another file, do not paste the full text inline.

### Integration callers

1. **Main conversation thread** — when user says "remember X" / "capture this" /
   "we should write this down".
2. **`documentation-expert` pre-flight** — before its Diataxis routing, so that doc-expert
   only handles within-Diataxis dispatch when the knowledge has already been confirmed
   to belong on a doc surface.
3. **Any phase agent** that receives feedback worth persisting (complements signoff §7
   which uses `route-learning` for the agent-discovery path).

### Relationship to `route-learning`

`route-learning` (referenced in `agent_knowledge_system.md`) covers the same domain
but is scoped to agent-internal post-signoff captures (signoff §7). `route-knowledge`
is the user-facing / caller-friendly variant with:
- Broader surface coverage (includes glossary, settings.json, ticket bodies, skills_config.json).
- Structured JSON output callers can act on programmatically.
- Explicit CLAUDE.md inline-vs-TOC rule.
- A description that enables auto-detection when the user says "remember X".

If `route-learning` already exists as a template when this ticket is implemented,
the implementer should evaluate whether to (a) extend `route-learning` with the
missing surfaces and rename/alias, or (b) keep them separate and document the split.
The ticket does not prescribe the choice — document the decision in a comment on
this ticket before starting.

## Acceptance Criteria

```gherkin
Given a piece of knowledge is presented to the route-knowledge skill
When the invoker passes the text and (optionally) the originating context
Then the skill returns a structured object: { target_surface, path, rationale }

Given the knowledge is a user preference about Claude's behaviour
When route-knowledge processes it
Then target_surface is "memory" and path is "memory/<subtype>.md"

Given the knowledge is a short project-wide rule
When route-knowledge processes it
Then target_surface is "CLAUDE.md-inline" or "CLAUDE.md-toc"
And the SKILL.md decision tree explains the distinction with a concrete example

Given the knowledge is a novel project term
When route-knowledge processes it
Then target_surface is "glossary" and the output instructs the caller to use the glossary-triage flow, not to hand-edit

Given documentation-expert receives a "remember this" request
When it calls route-knowledge in its pre-flight step
Then if target_surface is not a Diataxis surface, documentation-expert does NOT dispatch a Diataxis writer
And it instead routes to the correct non-doc surface named in the routing decision

Given the skill template is installed via build.py
When leafcutter is built into a consumer project
Then .claude/skills/route-knowledge/SKILL.md exists in the consumer project
```

## Sign-offs

- [x] documentation-expert — 2026-05-30 14:00
- [x] pr-reviewer — 2026-05-30 14:05
- [ ] commit

## Implementation Tasks

### documentation-expert
- [x] Read the knowledge-distribution architecture doc (sibling ticket output) to
      extract the canonical surface list.
- [x] Draft `leafcutter-ai/templates/skills/route-knowledge/SKILL.md` with:
  - Frontmatter: `name: route-knowledge`, `allowed-tools: Read`, `description`
    that triggers auto-selection when user says "remember X" / "capture this".
  - `## Input Contract` section: knowledge text, optional context (originating agent,
    file being edited, ticket in scope).
  - `## Output Contract` section: structured JSON `{ target_surface, path, rationale }`.
  - `## Decision Tree` section: one step per surface in the taxonomy table above,
    ordered from most-specific to least-specific. Each step includes:
    - Condition (when to route here).
    - Example input + expected output.
    - Any exclusion rules (e.g. "do NOT use this surface for X").
  - `## CLAUDE.md inline vs TOC-link` sub-section with the inline/TOC rule and
    two worked examples.
  - `## Glossary surface` sub-section: instructs callers to use `glossary-triage`
    flow, never hand-edit.
  - `## References` section citing the knowledge-distribution architecture doc as
    surface-inventory source of truth.
- [x] Update `leafcutter-ai/templates/agents/documentation-expert.md`:
  - Add `route-knowledge` to the `## Pre-Flight Reads` / pre-flight section.
  - Insert a `## Pre-Flight: Knowledge Surface Check` step (before the Diataxis
    dispatch table) that invokes the `route-knowledge` skill.
  - Document the conditional: if `target_surface` is not a Diataxis surface
    (`how_to`, `reference`, `explanation`, `tutorial`, `adr`, `architecture`),
    do not dispatch a Diataxis writer; instead return the routing decision to the
    caller for them to act on the correct surface.

### pr-reviewer
- [x] Verify `SKILL.md` frontmatter is valid (name, description, allowed-tools).
- [x] Verify decision tree covers all 14 surfaces in the acceptance criteria taxonomy.
- [x] Verify CLAUDE.md inline-vs-TOC distinction is explicit with examples.
- [x] Verify `documentation-expert.md` pre-flight section calls `route-knowledge`.
- [x] Verify `skill_registry.json` has been updated with the new skill entry.

### commit
- [ ] Stage and commit:
  - `leafcutter-ai/templates/skills/route-knowledge/SKILL.md`
  - `leafcutter-ai/config/skill_registry.json`
  - `leafcutter-ai/templates/agents/documentation-expert.md`
- [ ] Commit message: `feat(skills): add route-knowledge skill for user-triggered knowledge capture`

## Risk & Safety

- **No code changes**: this ticket touches only Markdown skill templates, a JSON
  registry file, and an agent prompt. No Python, no schema migrations, no hooks.
- **documentation-expert change is additive**: the new pre-flight step does not
  remove existing Diataxis dispatch logic; it gates it. Worst case: the skill is
  skipped and doc-expert behaves as before.
- **depends_on constraint**: if the sibling architecture doc ticket has not landed,
  the `## References` section of the skill will cite a not-yet-existing file. The
  implementer may use a placeholder path and update it when the doc lands.

## Comments

### 2026-05-30 14:00 — documentation-expert (status: ok)
feedback-id: fb_2026-05-30_0fe90789
completion_manifest:
  doc_written: true
  cross_links_added: true
  diataxis_genre_correct: true
Created `templates/skills/route-knowledge/SKILL.md` with full 17-step decision tree covering all 14+ surfaces in the taxonomy (Steps 0–17 including duplicate detection). Added `## Pre-Flight: Knowledge Surface Check` section to `templates/agents/documentation-expert.md` that gates Diataxis routing on `route-knowledge` output. Added `route-knowledge` entry to `config/skill_registry.json`. The `route-learning` skill was confirmed absent from templates (no existing skill to extend/alias), so `route-knowledge` is a new standalone skill as designed. References point to the sibling architecture doc at `docs/architecture/agent_knowledge_plane.md` which was confirmed to exist (committed as 0671a10).

### 2026-05-30 14:05 — pr-reviewer (status: ok)
feedback-id: fb_2026-05-30_9aeb4ce9
completion_manifest:
  frontmatter_valid: true
  surfaces_covered: true
  claude_md_rule_explicit: true
  doc_expert_preflight: true
  skill_registry_updated: true
All 5 PR reviewer checks passed. SKILL.md frontmatter is valid (name: route-knowledge, allowed-tools: Read, description triggers auto-selection). Decision tree covers all 14 required surfaces (memory subtypes, CLAUDE.md inline/TOC, per-folder README, agent frontmatter, ADR, architecture doc, how-to, reference, explanation, glossary, settings.json, ticket body, skills_config). CLAUDE.md inline-vs-TOC rule has two worked examples with expected JSON output. documentation-expert.md pre-flight invokes route-knowledge with non-Diataxis routing logic. skill_registry.json entry present with portable: true and correct template_path.
