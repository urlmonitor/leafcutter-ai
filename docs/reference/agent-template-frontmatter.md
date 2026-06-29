---
title: "Reference: Agent Template Frontmatter Fields"
description: "Complete field reference for agent template YAML frontmatter, including registry id conventions, tool allowlists, spawn_allowlist, and signoff protocol fields."
type: reference
status: active
created: 2026-05-28
last_updated: 2026-06-29
components:
  - build_pipeline
  - config_loader
related_docs:
  - "config/agent_registry.json"
  - "config/agent_registry.schema.json"
  - "templates/agents/"
  - "scripts/template_compiler.py"
  - "scripts/build_phases.py"
---

# Agent Template Frontmatter Fields

Every agent in the leafcutter ecosystem is defined by a Markdown template file
under `templates/agents/`. The file begins with a YAML frontmatter block
(`---` … `---`) that controls two distinct concerns:

- **Runtime keys** — consumed by Claude Code at agent-invocation time. These
  keys survive `build.py` compilation and appear verbatim in the deployed
  `.claude/agents/<name>.md` file.
- **Build directives** — consumed by `build.py` and `template_compiler.py`
  during compilation. These keys are stripped from the output and never reach
  the running agent.

**Source of truth for this reference**: `templates/agents/` (concrete
examples), `scripts/template_compiler.py` (key processing logic), and
`config/agent_registry.json` (registry-side complement). When a field is
present in both the frontmatter and the registry, the registry is authoritative
for deploy decisions; the frontmatter copy governs agent-runtime behaviour.

---

## Runtime Keys

Runtime keys are preserved verbatim in the compiled output file. The set is
defined by `output_fm_keys` in `template_compiler._build_output_header()`:
`{name, description, model, tools, memory}`.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | **yes** | — | Canonical agent identifier. Must match the `id` field in `agent_registry.json` and the filename stem under `templates/agents/`. Pattern: `^[a-z][a-z0-9-]*$`. Appears in auto-generated tables, spawn allowlists, and all ticket `agents:` maps. |
| `description` | string | **yes** | — | Human-readable prose that tells Claude Code when to activate this agent. Multi-line values must use the YAML block scalar (`|` for literal line breaks, `>` for folding). Surfaced in agent-selection tables and in the Claude Code project sidebar. |
| `model` | string | **yes** | — | Claude model to use when this agent is invoked. See [valid model values](#model-valid-values) below. |
| `tools` | string | **yes** | — | Comma-separated list of Claude Code tool names the agent is permitted to use. See [valid tool names](#tools-valid-values) below. |
| `memory` | boolean | no | `false` | When `true`, the agent is granted access to Claude Code's project-level memory (read and write). Only a small number of agents carry persistent memory: `commit`, `pr-reviewer`, `user-surface-smoker`, and `worktree-agent`. Omit entirely when the agent does not require memory access. |

### `model` Valid Values

| Value | Model | Typical use case |
|---|---|---|
| `sonnet` | claude-sonnet-* (current) | Default for most phase agents. Balanced speed and capability. |
| `opus` | claude-opus-* (current) | Reserved for deep reasoning tasks: `adr-author`, `architecture-diagram-author`, `architect-review-deep`, `brainstorm-worker`. |
| `haiku` | claude-haiku-* (current) | Fast, cheap sub-agents invoked in high-volume fan-out: `onboard-config-section`, `brainstorm-worker` (in Haiku-tier mode). |

### `tools` Valid Values

The `tools` field is a single string of comma-separated tool names. All
known tool names in the current template corpus:

| Tool name | Description |
|---|---|
| `Read` | Read files from the filesystem. |
| `Edit` | Replace strings in existing files. |
| `Write` | Create or overwrite files. |
| `Bash` | Run arbitrary shell commands. Broad; prefer `Skill` or a constrained form where possible. |
| `Glob` | List files matching a glob pattern. |
| `Grep` | Search file contents. |
| `Agent` | Spawn a sub-agent. Required for any agent that dispatches phase agents or utility agents. |
| `Skill` | Load and execute a named skill. Used by `architecture-diagram-author` to invoke the `write-c4-diagram` skill directly. |
| `mcp__jcodemunch__get_blast_radius` | MCP tool: compute blast radius for a code change. Present on `architect-review` only. |
| `mcp__jcodemunch__get_dependency_graph` | MCP tool: fetch the dependency graph. Present on `architect-review` only. |

**Representative tool-list combinations from the corpus:**

```
Read                              # read-only utility
Bash, Read                        # research / read-heavy
Bash, Read, Agent                 # research with delegation
Bash, Read, Edit                  # in-place editor
Bash, Read, Edit, Agent           # editor that spawns sub-agents
Bash, Read, Edit, Write, Agent    # full read-write agent (most phase agents)
```

---

## Build Directives

Build directives are read by `build.py` and `template_compiler.py` during
template compilation. They are **stripped from the compiled output** and do not
appear in the deployed `.claude/agents/<name>.md` file.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `portable` | boolean | no | `true` | When `true` (default), the agent is domain-agnostic and compiled by `build.py` for all adopter projects. When `false`, the agent is domain-specific and excluded from package compilation. Domain agents appear in `agent_registry.json` with `"portable": false`. In practice, every agent in `templates/agents/` currently has `portable: true`. |
| `signoff` | boolean | no | `false` | When `true`, `template_compiler.compile_agent_template()` appends the canonical sign-off block (from `templates/agents/_signoff_block.md`) to the compiled body. Phase agents that invoke the `signoff` skill as their final action should set this to `true`. |
| `domain` | string or null | no | `null` | Domain tag for project-specific agents (e.g. `"bybit-trader"`). When `null` (the standard case), the agent is portable. Mirrors the `domain` field in `agent_registry.json`. |
| `config_keys` | map or `{}` | no | `{}` | Structured map of project-specific config keys the agent reads from `skills_config.json`. Each entry declares `required` (boolean) and `description` (string). An empty map (`{}`) means the agent needs no project-specific config. Used by the `onboard` wizard to prompt the user for values and by `build.py` to validate config completeness. |
| `adopter_notes` | string (block scalar) | no | — | Free-text notes for developers who adopt the leafcutter package. Describes invocation context, constraints, or installation prerequisites. Stripped from the compiled output; only visible in the template source. When absent, omit the field entirely (do not write `adopter_notes: ""`). |
| `requires_verification` | boolean | no | `false` | When `true`, `template_compiler.compile_agent_template()` appends the standard post-edit verification block before the sign-off block. The verification block prompts the agent to run `git diff --stat` after every Edit/Write batch. Phase agents that modify files should set this to `true`. |
| `inject_registry` | boolean | no | `false` | When `true`, the compiler resolves the `{{registry_phase_agents_table}}` placeholder in the agent body by building a formatted table of all `is_ticket_phase: true` agents from `agent_registry.json`. Used by `workflow-architect` to keep its internal registry summary current. |
| `spawn_allowlist` | list of string | no | `[]` | Names of agents this agent is explicitly permitted to spawn via the `Agent` tool. Resolved by `template_compiler._apply_registry_injection()` into the `{{my_spawn_allowlist}}` table placeholder when present in the body. An empty list (`[]`) or absent field means the agent spawns no sub-agents or the allowlist is managed via the registry only. |

### `config_keys` Structure

When an agent requires project-specific configuration, `config_keys` is a
mapping where each key is a dot-notation config path and each value is an
object with at least `required` and `description`:

```yaml
config_keys:
  frontend.project_context_path:
    required: false
    description: "Path to PROJECT_CONTEXT.md for the frontend-coder agent"
  frontend.optional_skills:
    required: false
    description: "List of installed optional skill names (e.g. [webapp-testing, frontend-design])"
  frontend.test_command:
    required: false
    description: "Command to run the frontend test suite after changes"
```

Most agents use `config_keys: {}` (empty map), meaning they rely on the
globally-injected config (e.g. `skills_config.json` top-level paths) rather
than agent-specific keys.

### `spawn_allowlist` and Registry Injection

When the agent body contains `{{my_spawn_allowlist}}`, the compiler replaces
it at build time with a formatted Markdown table of agents from the
`spawn_allowlist` field, cross-referenced against `agent_registry.json`. The
`spawn_allowlist` field in the frontmatter is the human-editable source; the
registry `spawn_allowlist` array (under `agent_registry.json`) is the
authoritative copy for tooling. Keep both in sync when adding a new spawn
relationship.

The special value `__ticket_phase_agents__` in the registry spawn allowlist
(used by `ticket-supervisor`) is a macro that expands to all agents whose
`is_ticket_phase` is `true`.

---

## Agent Registry Cross-Reference

`config/agent_registry.json` is the single source of truth for agent
registration. It complements the template frontmatter: where frontmatter
describes how an agent behaves at runtime, the registry describes where it fits
in the ecosystem. Each entry in the `agents` array describes one agent.

> The fields below are **registry fields**, not frontmatter fields. They are
> not present in template frontmatter. They are documented here because a
> developer reading template frontmatter will often need to cross-check the
> registry to understand the agent's full profile.

| Registry Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | **yes** | Unique agent identifier. Must match the frontmatter `name` field and the filename stem under `templates/agents/`. Must NOT carry a version suffix: values matching `/-v[0-9]+$/` or containing `-v1`, `-v2`, or `-v3` are forbidden (AC ACD-1100b-3-i). Use the canonical unversioned name (e.g. `business-analyst`, not `business-analyst-v3`). |
| `name` | string | **yes** | Human-readable display name (Title Case). Used in documentation tables and the Claude Code sidebar. |
| `tier` | string | **yes** | Agent classification: `supervisor` (orchestrates others), `phase` (runs inside a ticket), or `utility` (general-purpose). |
| `role` | string | **yes** | Functional role: `orchestration`, `analysis`, `coding`, `documentation`, `commit`, `review`, or `utility`. |
| `portable` | boolean | **yes** | `true` = domain-agnostic; compiled for all projects. `false` = domain-specific; not distributed. Mirrors the frontmatter `portable` field. |
| `domain` | string or null | **yes** | Domain tag for domain-specific agents. `null` for portable agents. |
| `spawn_allowlist` | array of string | **yes** | Agent IDs this agent may spawn. May contain the macro `__ticket_phase_agents__`. |
| `spawned_by` | array of string | **yes** | Agent IDs (or `"user"`) that are expected to spawn this agent. Used for documentation and validation. |
| `is_ticket_phase` | boolean | **yes** | When `true`, this agent appears in the `agents:` map of a ticket and is dispatched by `ticket-supervisor`. The `create-ticket` workflow uses this flag to populate new ticket `agents:` maps. |
| `selection_criteria` | object or null | **yes** | Structured criteria used by `ticket-supervisor` to decide whether to include this agent in a ticket's `agents:` map. `null` when the agent is not ticket-phase or is always/never included. |
| `template_path` | string | for portable | Relative path from the leafcutter workspace root to the template file. Format: `templates/agents/<id>.md`. |
| `model` | string | **yes** | Default model, mirroring the frontmatter `model` field. |
| `skills_used` | array of string | no | Skill IDs the agent loads at runtime. Used by `registry_validator.py` to validate skills exist. |
| `priority` | number or null | no | Numeric dispatch priority for ticket-phase agents. Lower numbers run earlier. See [priority values](#registry-priority-values) below. |
| `priority_rationale` | string | no | Human-readable explanation for the priority value. |
| `requires_ticket_section` | boolean | no | When `true`, the agent requires a named section (e.g. `## Smoke Fixture`) in the ticket body to operate. |
| `conditional` | boolean | no | When `true`, the agent is only added to a ticket's `agents:` map when a ticket-frontmatter field matches `conditional_field`. |
| `conditional_field` | string | no | The ticket frontmatter field whose non-null value triggers inclusion of a `conditional: true` agent. |
| `invocation_surface` | string | no | CLI command (e.g. `/po-review`) that invokes this agent directly. Present on user-facing agents only. |
| `owns_file_extensions` | array of string | no | File extensions this agent is authoritative for (e.g. `[".py"]` for `python-coder`, `[".sql"]` for `sql-coder`). Used by blast-radius analysis. |

### Registry Priority Values

| Priority | Agent |
|---|---|
| 1 | `status-checker` |
| 2 | `adr-author` |
| 3 | `architecture-diagram-author` |
| 4 | `architect-review` |
| 5 | `test-writer` |
| 6 | `python-coder` |
| 7 | `sql-coder`, `sql-query` |
| 9 | `test-runner` |
| 10 | `change-scope-reviewer`, `documentation-expert`, `explanation-author`, `how-to-author`, `reference-author` |
| 11 | `pr-reviewer` |
| 11.5 | `ac-validator`, `user-surface-smoker` |
| 11.7 | `ac-fulfillment-gate` |
| 12 | `commit` |
| 13 | `pull-request` |

Agents without a priority value run after all listed agents, in YAML
declaration order.

---

## Examples

### Minimal Template Frontmatter

Required runtime keys only. No build directives. Suitable for a simple utility
agent that modifies no files and spawns no sub-agents.

```yaml
---
name: my-agent
description: |
  One-sentence summary of when to use this agent.
  (internal — invoked by documentation-expert only)
model: sonnet
tools: Bash, Read
---
```

### Maximal Template Frontmatter

All fields, suitable for a full-featured phase agent with project-specific
config, sub-agent spawning, and a sign-off block.

```yaml
---
description: |
  Full prose description. Mention what the agent does, when it is triggered,
  and any Stop-and-Ask rules. Include "(internal — invoked by X only)" when the
  agent is not user-facing.
model: sonnet
name: my-phase-agent
tools: Bash, Read, Edit, Write, Agent
# memory: omit entirely when false (the default); only write when true
portable: true
signoff: true
domain: null
config_keys:
  myagent.context_path:
    required: false
    description: "Path to the project context file this agent reads at startup."
adopter_notes: |
  Phase agent. Invoked by ticket-supervisor. Requires the my-skill skill to be
  installed in the target project before use.
requires_verification: true
# inject_registry: omit entirely when false (the default); only write when true
spawn_allowlist:
  - research-agent
---
```

---

## Relationship Between Frontmatter and Registry

```
templates/agents/my-agent.md          config/agent_registry.json
─────────────────────────────         ────────────────────────────────
name: my-agent           ←── must match ──→  "id": "my-agent"
description: ...         ←── doc source  ──→  (registry may override display name)
model: sonnet            ←── mirrors     ──→  "model": "sonnet"
portable: true           ←── mirrors     ──→  "portable": true
spawn_allowlist: [...]   ←── input to    ──→  "spawn_allowlist": [...]
```

The frontmatter is the human-editable source; `build.py` reads it and writes
the compiled output to `.claude/agents/`. The registry is the machine-readable
authority; `registry_validator.py` cross-checks template paths and skills
references on every build. When the two diverge, run `python scripts/build.py
--validate` to surface errors.

---

## See Also

- `docs/reference/skill-frontmatter.md` — equivalent reference for SKILL.md frontmatter fields.
- `docs/reference/skills-config-fields.md` — reference for `skills_config.json` keys.
- `docs/agent-registry.md` — overview of the agent registry and its role in the build pipeline.
- `scripts/template_compiler.py` — compilation logic that reads these fields.
- `scripts/registry_validator.py` — validation logic that enforces registry-frontmatter consistency.
- `docs/how-to/creating-an-agent-template.md` — task guide for writing a new agent template.
