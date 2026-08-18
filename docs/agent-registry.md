---
title: Agent Registry Reference
type: reference
status: active
created: 2026-05-13
last_updated: 2026-08-18
components:
- infrastructure
description: Overview of Agent Registry Reference.
---
# Agent Registry Reference

`leafcutter/config/agent_registry.json` is the single source of truth
for which agents exist, their spawn relationships, ticket-phase roles, selection
criteria, and skills used.

## Schema

Each agent entry requires these fields:

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique ID matching template filename (e.g. `python-coder`) |
| `name` | string | Human-readable display name |
| `tier` | `supervisor\|phase\|utility` | Tier determines execution context |
| `role` | string | Functional role (`orchestration`, `coding`, `review`, etc.) |
| `portable` | boolean | `true` = domain-agnostic; `false` = domain-specific |
| `domain` | string or null | Domain tag (e.g. `"billing"`) for domain agents |
| `spawn_allowlist` | array | Agent IDs this agent may spawn |
| `spawned_by` | array | Agent IDs or `"user"` that invoke this agent |
| `is_ticket_phase` | boolean | `true` = appears in ticket `agents:` maps |
| `selection_criteria` | object or null | Machine-readable assignment conditions |
| `template_path` | string | Path to template file (relative to package root) |
| `model` | string | Preferred model tier (`"sonnet"` or `"opus"`) |
| `skills_used` | array | Skills this agent loads at runtime (may be `[]`) |
| `permits_shell` | boolean (optional) | `true` if the agent's registered charter permits running repository-mutating shell commands (`git fetch`/`branch`/`worktree add`, file writes outside its own scratch area, etc.). `false` or absent means the agent must be treated as read-only for dispatch-permission gates such as the isolated-workspace setup step in `plan-feature.js` (see [Agent Code Delivery Workflows §6](architecture/agent_delivery_workflows.md#6-detail-view-isolated-authoring-worktree-lifecycle-bo-1500a-3)). Distinct from tool possession — an agent can carry `Bash` in its tools purely for read-only diagnostics (e.g. `status-checker`) without `permits_shell` being `true`. |

## Portable vs. Domain Agents

The registry contains two categories:

**Portable agents** (`portable: true`, `domain: null`) — domain-agnostic agents
included in the leafcutter package. `build.py` compiles their templates
into the target project's `.claude/agents/` directory.

**Domain agents** (`portable: false`, `domain: "<name>"`) — project-specific agents
that live in the target project's `.claude/agents/` directory. They are registered
here for:
- Spawn graph completeness (topology diagrams include them)
- Bidirectional consistency validation (spawn_allowlist ↔ spawned_by)
- Skills-used mapping (which project-specific skills they load)

Domain agent templates are NOT compiled by `build.py` — they are maintained
directly in the target project.

## Template Placeholders (Build-Time Injection)

`build.py` resolves three placeholder types in agent templates at compile time.
Each placeholder is replaced with generated markdown before the template is
written to `.claude/agents/`.

### Type 1: Per-Agent Sub-Agent Table (`{{my_spawn_allowlist}}`)

Injected into any agent template that contains this placeholder. Replaced with a
markdown table of the agent's `spawn_allowlist` entries (Agent, Role, Tier columns).

The special macro `__ticket_phase_agents__` in `spawn_allowlist` expands to all
agents where `is_ticket_phase: true`.

When `spawn_allowlist` is empty, replaced with:
`You have no sub-agent spawning capability.`

When a `spawn_allowlist` entry references an unknown agent ID, `build.py` raises
an error naming the unknown ID.

### Type 2: Per-Agent Skills Table (`{{my_skills_used}}`)

Injected into any agent template that contains this placeholder. Replaced with a
markdown table of the agent's `skills_used` entries (Skill, Description columns).
The description is read from each skill's `SKILL.md` frontmatter `description:` field.

When `skills_used` is empty or absent, replaced with empty string (section suppressed).

### Type 3: Phase-Agent Selection Table (`{{registry_phase_agents_table}}`)

Opt-in via `inject_registry: true` in the template frontmatter. Only active for
`create-ticket.md` and `create-epic.md` (the two templates that need the full
phase-agent selection table for ticket scaffolding).

Replaced with a table of all `is_ticket_phase: true` agents (Agent, Default Status,
Trigger Conditions columns). Used by these templates to infer the default `agents:`
map when no BA payload is available.

The `inject_registry` key is stripped from the compiled output frontmatter — it is
a build directive, not a runtime key.

## Adding a Portable Agent

1. Create the template file at `leafcutter/templates/agents/<id>.md`
2. Add an entry in `agent_registry.json` with `"portable": true`
3. Add `skills_used` (array, may be `[]`)
4. If the agent spawns others, update their `spawned_by` arrays too
5. Run `python leafcutter/scripts/build.py --validate` to confirm

## Adding a Domain Agent

1. Create the agent file at `.claude/agents/<id>.md` in your target project
2. Add an entry in `agent_registry.json` with `"portable": false, "domain": "<your-domain>"`
3. The `template_path` should point to the file in the target project (e.g. `.claude/agents/<id>.md`)
4. Skills in `skills_used` are informational for domain agents — they reference
   skills that exist in the target project, not the portable package
5. Run `build.py --validate` — domain agents are reported as INFO, not compiled

## Domain Agents Section

No domain agents ship with this package — every agent in `agent_registry.json`
carries `"portable": true` and `"domain": null`.

A consumer project registers its own domain agents in the same file, using its
own domain tag. They are listed alongside the portable agents and are reported
as INFO (not compiled) by `build.py --validate`:

| Agent | Role | Skills Used |
|---|---|---|
| `<your-agent-id>` | What the agent does in your domain | Skills that exist in your project |

## Diagram Generation

Run this to regenerate the agent topology diagrams from the registry:

```bash
python leafcutter/scripts/generate_agent_diagram.py --output-format embed
```

Or via build.py:

```bash
python leafcutter/scripts/build.py --update-diagrams
```

See [agentic-runtime-flow.md](agentic-runtime-flow.md) and
[agents/README.md](agents/README.md) for the embedded diagrams.
