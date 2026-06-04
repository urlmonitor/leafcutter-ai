---
title: "Introduce llm-expert agent: LLM craft peer to the coding agents"
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/agents/llm-expert.md
  - config/agent_registry.json
  - docs/agents/README.md
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
---

# Introduce llm-expert agent: LLM craft peer to the coding agents

## Actor / Goal

In order to have a specialist that owns the craft of writing, auditing, and
maintaining the text inside agent templates, skill files, and slash-command
prompts — the way `python-coder` owns Python files — we need an `llm-expert`
agent that BA and IT PO can dispatch when a ticket requires prompt engineering,
agent authoring, or skill authoring work.

## Context

The leafcutter coding-agent family (`python-coder`, `sql-coder`,
`frontend-coder`) follows a consistent pattern: each agent has a dedicated
`PROJECT_CONTEXT.md`, loads domain-specific skills, and is dispatched by
`ticket-supervisor` as a first-class ticket phase. The same pattern does not
yet exist for the craft of writing LLM instructions themselves.

The immediate pain-point that surfaced this gap: several agent and skill
templates were found to contain compound bash commands that violated the
shell convention in `CLAUDE.md` (chained `&&`, relative `cd`, etc.), causing
permission prompts during drives. There was no agent whose responsibility it
was to review, audit, or write the *prompts and instructions* inside those
files. The `workflow-architect` agent is the closest existing steward — it
owns the package surface (registry, build pipeline) — but it is an
*infrastructure meta-agent*, not a craft specialist. Prompt review and
authoring would be scope-creep for it.

The proposed agent is named `llm-expert` (broader than "prompting agent")
because its remit covers:
- Writing and editing agent templates (`templates/agents/*.md`)
- Writing and editing skill bodies (`templates/skills/*/SKILL.md`)
- Auditing prompts/instructions for convention violations (shell rules,
  nesting limits, tool allowlists, signoff protocol adherence)
- Applying skills like `add-agent-to-package` and `add-skill-to-package`
  when a new template needs to be promoted into the package
- Fielding tickets whose `agents:` map BA/IT PO mark as requiring
  prompt-engineering or template work

### Relationship to existing agents

| Agent | Responsibility boundary |
|---|---|
| `workflow-architect` | Package infrastructure: registry, build pipeline, hook wiring |
| `python-coder` | Python implementation files |
| `sql-coder` | SQL files |
| `frontend-coder` | Frontend/UI files |
| **`llm-expert`** (new) | Agent template bodies, skill SKILL.md bodies, slash-command md bodies, prompt conventions |

`llm-expert` will use `workflow-architect` as its infrastructure arm via the
`add-agent-to-package` and `add-skill-to-package` skills when a newly authored
agent or skill needs to be promoted. It does NOT own the registry write itself
— that remains `workflow-architect`'s domain.

### Skills the agent will load

| Skill | Purpose |
|---|---|
| `add-agent-to-package` | Promote a newly authored agent template into the package |
| `add-skill-to-package` | Promote a newly authored skill into the package |
| `signoff` | Standard ticket sign-off protocol |

Additional skills (`package-audit`, `create-hook`) may be used read-only
for audit passes but are not primary.

### PROJECT_CONTEXT.md scope

The `llm-expert` agent must ship with a `PROJECT_CONTEXT.md` (analogous to
`python-coder`'s context file). It should contain:

1. **Shell convention** — the single-command rule from `CLAUDE.md`; how to
   detect compound-command violations in template files.
2. **Agent frontmatter schema** — required fields (`name`, `description`,
   `model`, `tools`, `portable`, `signoff`), valid values, and which fields
   are build-injected vs hand-authored.
3. **Skill frontmatter schema** — `name`, `description`, `allowed-tools`.
4. **Signoff protocol** — how phase agents sign off; what the parity guard
   checks; why timestamps matter.
5. **Nesting / spawn-allowlist rules** — the depth-3 cap; why agents must
   declare `spawn_allowlist`; how `spawned_by` is used by ticket-supervisor.
6. **Prompt-quality checklist** — checklist an LLM expert applies when
   reviewing a prompt: no compound bash, no absolute paths from training data,
   tool allowlist matches what the body actually uses, no mention of tools not
   in the allowlist, clear stop-and-ask rules for out-of-scope edits.

## Acceptance Criteria

```gherkin
Given the build system deploys the leafcutter package
When the deploy target is inspected
Then templates/agents/llm-expert.md exists
And config/agent_registry.json contains an entry with id "llm-expert"
And the entry declares tier "phase", role "authoring"
And the entry lists skills_used containing "add-agent-to-package" and "add-skill-to-package" and "signoff"
And docs/agents/README.md agent table includes a row for llm-expert

Given the llm-expert template is read
When its frontmatter is inspected
Then it contains name, description, model, tools, portable, signoff, requires_verification fields
And description clearly states when to dispatch it (tickets that produce or modify agent templates, skill bodies, or slash-command markdown files)
And tools includes at minimum Bash, Read, Edit, Write
And signoff is true
And requires_verification is true

Given the llm-expert template is read
When its body is inspected
Then a "## Pre-Flight Reads" section names PROJECT_CONTEXT.md and the relevant SKILL.md files
And a "## Prompt-Quality Checklist" section is present with at minimum 5 checklist items
And the checklist includes a check for compound bash commands violating CLAUDE.md shell convention
And a "## Stop-and-Ask Rule" section is present that defers infrastructure edits (registry, build pipeline) to workflow-architect
And a "## Skills" section lists the three skills the agent may invoke
And a "## Sign-off" section follows the signoff skill §2c recipe

Given a ticket's agents map contains llm-expert: needed
When ticket-supervisor drives the ticket
Then llm-expert is dispatched as a phase agent

Given llm-expert is dispatched on a ticket that modifies a compound bash command in an agent template
When llm-expert reads the template
Then it detects the violation via its Prompt-Quality Checklist
And it edits the template to split the compound command into separate Bash tool calls
And it appends a sign-off comment to the ticket
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |
| AC-7 | | | |

## Sign-offs

- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### workflow-architect — author the agent template

- [ ] Create `templates/agents/llm-expert.md` with:

  **Frontmatter:**
  ```yaml
  name: llm-expert
  description: |
    LLM craft specialist. Authors, edits, and audits agent templates
    (templates/agents/*.md), skill bodies (templates/skills/*/SKILL.md),
    and slash-command markdown files (templates/workflows/*.md). Applies the
    Prompt-Quality Checklist to detect convention violations (compound bash,
    wrong tool allowlist, missing signoff protocol). Uses add-agent-to-package
    and add-skill-to-package skills to promote new templates into the package.

    Use when: a ticket produces or modifies an agent template, skill SKILL.md,
    or slash-command .md file; or when auditing existing templates for
    convention violations.
  model: sonnet
  tools: Bash, Read, Edit, Write, Agent
  portable: true
  signoff: true
  domain: null
  inject_registry: false
  requires_verification: true
  config_keys:
    llm_expert.project_context_path:
      required: false
      description: "Path to PROJECT_CONTEXT.md (default: .claude/agents/llm-expert/PROJECT_CONTEXT.md)"
  spawn_allowlist:
    - research-agent
  default_artifact_checklist:
    - template_authored
    - prompt_quality_checklist_passed
    - signoff_protocol_correct
  adopter_notes: |
    No project-specific configuration required for the base agent. If your
    project has additional prompt conventions, add them to PROJECT_CONTEXT.md.
  ```

  **Body sections (in order):**
  1. `## Pre-Flight Reads` — read PROJECT_CONTEXT.md; read the SKILL.md for
     each skill the task requires; read the target template file before editing.
  2. `## Prompt-Quality Checklist` — minimum 6 items the agent must verify
     on any template it produces or modifies:
     - No compound bash commands (`&&`, `;`, `||`, pipes that chain writes)
     - Tool allowlist in frontmatter matches tools actually used in the body
     - No tools referenced in the body that are absent from the allowlist
     - `spawn_allowlist` declared for any agent that spawns sub-agents
     - Signoff protocol section present for `signoff: true` agents
     - Stop-and-ask rules present for any scope boundary (e.g. "don't edit
       Python files; defer to python-coder")
  3. `## Stop-and-Ask Rule` — if the task requires editing `config/agent_registry.json`,
     `scripts/build.py`, or any hook script, stop and defer to `workflow-architect`.
     `llm-expert` owns template *bodies*, not infrastructure wiring.
  4. `## Skills` — table of three skills and when to invoke each:
     `add-agent-to-package`, `add-skill-to-package`, `signoff`.
  5. `## Implementation Sequence` — ordered steps:
     (a) Read pre-flight docs; (b) activate contract-aware mode if `## Agent Contracts`
     present; (c) apply Prompt-Quality Checklist; (d) write/edit the template;
     (e) re-read and re-apply checklist; (f) invoke skill if promotion needed;
     (g) sign off.
  6. `## Response Payload` — required completion report block (files changed,
     checklist items verified, skills invoked, notes).
  7. `## Sign-off` — follow signoff SKILL.md §2c recipe.
  8. `## Constraints` — do not edit Python/SQL/frontend files; do not edit
     registry or build pipeline; delegate cross-file search to research-agent;
     single-command bash only.

### workflow-architect — register the agent

- [ ] Add an entry to `config/agent_registry.json` for `llm-expert`:
  ```json
  {
    "id": "llm-expert",
    "name": "LLM Expert",
    "tier": "phase",
    "role": "authoring",
    "portable": true,
    "domain": null,
    "spawn_allowlist": ["research-agent"],
    "spawned_by": ["ticket-supervisor"],
    "is_ticket_phase": true,
    "selection_criteria": {
      "type": "llm",
      "rule": "Select when the ticket produces or modifies an agent template, skill SKILL.md, slash-command markdown, or requires auditing prompts/instructions for convention violations."
    },
    "template_path": "templates/agents/llm-expert.md",
    "model": "sonnet",
    "skills_used": ["add-agent-to-package", "add-skill-to-package", "signoff"],
    "default_status": "not_needed",
    "trigger_conditions": [
      {
        "type": "dsl",
        "rule": "files_touched contains any path matching templates/agents/*.md OR templates/skills/*/SKILL.md OR templates/workflows/*.md"
      }
    ]
  }
  ```

- [ ] Add `llm-expert` to the `spawn_allowlist` of `ticket-supervisor` in
  `config/agent_registry.json` (ticket-supervisor spawns all is_ticket_phase agents).

### workflow-architect — create PROJECT_CONTEXT.md

- [ ] Create `templates/agents/llm-expert/PROJECT_CONTEXT.md` with the six
  sections described in the Context section above:
  1. Shell convention (single-command rule; detection heuristics for `&&`, `;`)
  2. Agent frontmatter schema (required fields, build-injected vs hand-authored)
  3. Skill frontmatter schema
  4. Signoff protocol summary (pointing to signoff SKILL.md §2 and §4)
  5. Nesting / spawn-allowlist rules (depth-3 cap, spawn_allowlist contract)
  6. Prompt-quality checklist (the same 6+ items from the agent body, expanded
     with examples of good and bad patterns)

### workflow-architect — update docs/agents/README.md

- [ ] Add a row for `llm-expert` in the agent table in `docs/agents/README.md`.
  Place it in the **phase agents** section, alphabetically among peers.
  One-liner: "Authors, edits, and audits agent templates, skill bodies, and
  slash-command markdown files. Applies the Prompt-Quality Checklist."

## Risk & Safety

- Touches money? No.
- Touches data? No. This ticket produces template files and a registry JSON
  entry only. No data or schema changes.
- Reversibility? Fully reversible. All files are new additions. Removing the
  template and registry entry returns the system to its prior state. The
  `build.py` run after deletion re-deploys without the agent.
- Shared contract? Adding `llm-expert` to `config/agent_registry.json` with
  `is_ticket_phase: true` means BA will begin emitting it in `agents:` maps
  for matching tickets after the build. Verify the `default_status: not_needed`
  is set so existing tickets are unaffected until explicitly opted in.
- Build dependency? The `add-agent-to-package` skill handles template promotion
  idempotently. Run `build.py` after the template is committed to deploy the
  agent into `.claude/agents/`.
- Naming? `llm-expert` does not conflict with any existing agent ID in
  `config/agent_registry.json` (verified at ticket-authoring time).
