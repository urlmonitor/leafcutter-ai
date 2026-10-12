---
title: 'Reference: Agent Template Frontmatter Fields'
type: reference
status: active
created: 2026-05-28
last_updated: 2026-10-09
components:
- build_pipeline
- config_loader
related_docs:
- config/agent_registry.json
- config/agent_registry.schema.json
- templates/agents/
- scripts/template_compiler.py
- scripts/build_phases.py
- scripts/agent_skills_declaration.py
- scripts/agent_spawn_declaration.py
- scripts/skill_tool_grant_validator.py
description: 'Overview of Reference: Agent Template Frontmatter Fields.'
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
for deploy decisions; the frontmatter copy governs agent-runtime behaviour. The
exceptions are `skills` and `spawn_allowlist`: the frontmatter is the only place
they are authored and the registry holds a derived copy (see
[Granting Skills and Sub-Agents](#granting-skills-and-sub-agents)).

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
| `opus` | claude-opus-* (current) | Reserved for deep reasoning tasks: `adr-author`, `architecture-diagram-author`, `brainstorm-worker`. |
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
| `Agent` | Spawn a sub-agent. Required for any agent with a non-empty `spawn_allowlist` (build error `spawn-tool-grant`). |
| `Skill` | Load and execute a named skill. Required for any agent with a non-empty `skills` list (build error `skill-tool-grant`). |
| `mcp__jcodemunch__get_blast_radius` | MCP tool: compute blast radius for a code change. Present on `architect-review` only. |
| `mcp__jcodemunch__get_dependency_graph` | MCP tool: fetch the dependency graph. Present on `architect-review` only. |

---

## Build Directives

Build directives are read by `build.py` and `template_compiler.py` during
template compilation. They are **stripped from the compiled output** and do not
appear in the deployed `.claude/agents/<name>.md` file.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `portable` | boolean | no | `true` | When `true` (default), the agent is domain-agnostic and compiled by `build.py` for all adopter projects. When `false`, the agent is domain-specific and excluded from package compilation. Domain agents appear in `agent_registry.json` with `"portable": false`. In practice, every agent in `templates/agents/` currently has `portable: true`. |
| `signoff` | boolean | no | `false` | When `true`, `template_compiler.compile_agent_template()` appends the canonical sign-off block (from `templates/agents/_signoff_block.md`) to the compiled body. Phase agents that invoke the `signoff` skill as their final action should set this to `true`. |
| `domain` | string or null | no | `null` | Domain tag for project-specific agents (e.g. `"billing"`). When `null` (the standard case), the agent is portable. Mirrors the `domain` field in `agent_registry.json`. |
| `config_keys` | map or `{}` | no | `{}` | Structured map of project-specific config keys the agent reads from `skills_config.json`. Each entry declares `required` (boolean) and `description` (string). An empty map (`{}`) means the agent needs no project-specific config. Used by the `onboard` wizard to prompt the user for values and by `build.py` to validate config completeness. |
| `adopter_notes` | string (block scalar) | no | — | Free-text notes for developers who adopt the leafcutter package. Describes invocation context, constraints, or installation prerequisites. Stripped from the compiled output; only visible in the template source. When absent, omit the field entirely (do not write `adopter_notes: ""`). |
| `requires_verification` | boolean | no | `false` | When `true`, `template_compiler.compile_agent_template()` appends the standard post-edit verification block before the sign-off block. The verification block prompts the agent to run `git diff --stat` after every Edit/Write batch. Phase agents that modify files should set this to `true`. |
| `inject_registry` | boolean | no | `false` | When `true`, the compiler resolves the `{{registry_phase_agents_table}}` placeholder in the agent body by building a formatted table of all `is_ticket_phase: true` agents from `agent_registry.json`. Used by `workflow-architect` to keep its internal registry summary current. |
| `skills` | list of entry | no | `[]` | The skills this agent is granted, the only place a grant is authored. Entry shape in [Granting Skills and Sub-Agents](#granting-skills-and-sub-agents). The build appends one `## Your Available Skills` section. Absent or empty means no grant. |
| `spawn_allowlist` | list of string | no | `[]` | Agent ids this agent may dispatch, the only place a sub-agent permission is authored. May contain `__ticket_phase_agents__`. The build appends one `## Your Available Sub-Agents` section. Absent or empty means no permission. |

### `config_keys` Structure

`config_keys` maps each dot-notation config path to an object with at least
`required` and `description`, for example:

```yaml
config_keys:
  frontend.test_command:
    required: false
    description: "Command to run the frontend test suite after changes"
```

Most agents use `config_keys: {}` and rely on globally-injected config.

### Granting Skills and Sub-Agents

An agent's skills and its permitted sub-agents are each declared in ONE place:
the template frontmatter, beside `tools:`. Nothing beyond the declaration is
needed for either to reach the agent: no registry edit, no body marker, no
hand-written table.

```yaml
tools: Bash, Read, Edit, Write, Agent, Skill
skills:
- skill_id: doc-enforcer
  mode: always
- skill_id: signoff
  mode: conditional
  condition: When invoked with a ticket_path, load signoff to record your sign-off.
spawn_allowlist:
- __ticket_phase_agents__
- brainstorm-lead
```

| Key | Entry | Rules |
|---|---|---|
| `skills` | `skill_id` (string, required); `mode`: `always` (default) or `conditional`; `condition` (string) | A bare string is an `always` grant. A `conditional` entry with no `condition` text refuses the build (`missing-condition`). |
| `spawn_allowlist` | agent id (string), or the literal `__ticket_phase_agents__` | The macro stays one entry and resolves on every build to each registry agent whose `is_ticket_phase` is `true` (that flag is still authored in the registry). A macro that resolves to no agent refuses the build. |

**What the build does.** Each non-empty declaration makes the build append one
generated section to the compiled prompt: `## Your Available Skills` (table of
skill, mode or condition, description) and `## Your Available Sub-Agents`
(table of agent, role, tier). An empty or absent declaration appends nothing.

**Tool pairing.** A non-empty `skills` list requires `Skill` in `tools:`; a
non-empty `spawn_allowlist` (macro included) requires `Agent`. The registry
validator reports `skill-tool-grant` / `spawn-tool-grant` and the build fails.
The fix is to add the tool, not to drop the declaration.

**Resolution.** A declared skill must exist as `templates/skills/<id>/SKILL.md`
or in the project's `<output_root>/skills/<id>/SKILL.md`; otherwise the build
refuses. A declared sub-agent must have a packaged `templates/agents/<id>.md`;
otherwise the build refuses. Project-local agent definitions are not yet
looked up (deferred: `docs/known-issues/agent-registry/open-low-ki-ar-005.md`,
KI-AR-005), and a registry row or an earlier compiled prompt does not count.

**The registry copy is derived.** `skills_used` / `skills_invoked` and
`spawn_allowlist` in `config/agent_registry.json` are regenerated from the
declarations by the `transform-agent-registry` pre-commit hook ("Transform agent
registry"), which re-stages the registry when it changes. Do not edit them by
hand. If the copy disagrees with a declaration, the build reports the
disagreement (`divergent`, `declaration-only` or `record-only`), the
declaration wins in the compiled prompt, and the next hook run overwrites the
hand edit. `spawned_by` and `is_ticket_phase` are not derived; they stay
hand-authored.

**Retired routes.** None of these grants anything: the `{{my_skills_used}}` and
`{{my_spawn_allowlist}}` body markers (stripped at compile time with a warning),
a registry-only grant, a template-level `skills_used` key, and a hand-written
skills or sub-agent table in the body. The compiler warns on a body section that
states its own skills or sub-agents (`duplicate` or `contradiction` against the
declaration); remove it.

---

## Agent Registry Cross-Reference

`config/agent_registry.json` is the single source of truth for agent
registration. It complements the template frontmatter: where frontmatter
describes how an agent behaves at runtime, the registry describes where it fits
in the ecosystem. Each entry in the `agents` array describes one agent.

The fields below are **registry fields**, not frontmatter fields.

| Registry Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | **yes** | Unique agent identifier. Must match the frontmatter `name` field and the filename stem under `templates/agents/`. |
| `name` | string | **yes** | Human-readable display name (Title Case). Used in documentation tables and the Claude Code sidebar. |
| `tier` | string | **yes** | Agent classification: `supervisor` (orchestrates others), `phase` (runs inside a ticket), or `utility` (general-purpose). |
| `role` | string | **yes** | Functional role: `orchestration`, `analysis`, `coding`, `documentation`, `commit`, `review`, or `utility`. |
| `portable` | boolean | **yes** | `true` = domain-agnostic; compiled for all projects. `false` = domain-specific; not distributed. Mirrors the frontmatter `portable` field. |
| `domain` | string or null | **yes** | Domain tag for domain-specific agents. `null` for portable agents. |
| `spawn_allowlist` | array of string | **yes** | **Derived** from the frontmatter `spawn_allowlist` by the transform hook; do not hand-edit. May contain the macro `__ticket_phase_agents__`. |
| `spawned_by` | array of string | **yes** | Agent IDs (or `"user"`) that are expected to spawn this agent. Used for documentation and validation. |
| `is_ticket_phase` | boolean | **yes** | When `true`, this agent appears in the `agents:` map of a ticket and is dispatched by `ticket-supervisor`. Business-analyst and refinement use this flag to populate new ticket `agents:` maps. |
| `selection_criteria` | object or null | **yes** | Structured criteria used by `business-analyst` to decide whether to include this agent in a ticket's `agents:` map. `null` when the agent is not ticket-phase or is always/never included. |
| `template_path` | string | for portable | Relative path from the leafcutter workspace root to the template file. Format: `templates/agents/<id>.md`. |
| `model` | string | **yes** | Default model, mirroring the frontmatter `model` field. |
| `skills_used` / `skills_invoked` | array of string / array of entry | no | **Derived** from the frontmatter `skills` by the transform hook; do not hand-edit. `descriptive_only` entries in `skills_invoked` describe behaviour and are not grants. |
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
| 1-6 | `status-checker`, `adr-author`, `architecture-diagram-author`, `architect-review`, `test-writer`, `python-coder` (in that order) |
| 7, 9 | `sql-coder` and `sql-query` (7), `test-runner` (9) |
| 10 | `change-scope-reviewer`, `documentation-expert`, `explanation-author`, `how-to-author`, `reference-author` |
| 11 - 11.7 | `pr-reviewer` (11), `ac-validator` and `user-surface-smoker` (11.5), `ac-fulfillment-gate` (11.7) |
| 12, 13 | `commit` (12), `pull-request` (13) |

Agents without a priority value run after all listed agents, in YAML
declaration order.

---

## Examples

### Template Frontmatter with All Fields

Required runtime keys are `name`, `description`, `model` and `tools`; every
other key is optional. A full-featured phase agent:

```yaml
---
description: |
  Full prose description. Mention what the agent does, when it is triggered,
  and any Stop-and-Ask rules. Include "(internal — invoked by X only)" when the
  agent is not user-facing.
model: sonnet
name: my-phase-agent
tools: Bash, Read, Edit, Write, Agent, Skill
skills:
  - skill_id: my-skill
    mode: always
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
spawn_allowlist: [...]   ── derives ──→  "spawn_allowlist": [...]
skills: [...]            ── derives ──→  "skills_used" / "skills_invoked"
```

The frontmatter is the human-editable source; `build.py` reads it and writes
the compiled output to `.claude/agents/`. The `skills` and `spawn_allowlist`
registry fields are derived copies (see
[Granting Skills and Sub-Agents](#granting-skills-and-sub-agents)); the other
registry fields are authored there. `registry_validator.py` cross-checks
template paths and tool pairing on every build. When the two diverge, run
`python scripts/build.py --validate` to surface errors.

---

## See Also

- `docs/reference/skill-frontmatter.md` — equivalent reference for SKILL.md frontmatter fields.
- `docs/reference/skills-config-fields.md` — reference for `skills_config.json` keys.
- `docs/agent-registry.md` — overview of the agent registry and its role in the build pipeline.
- `scripts/template_compiler.py` — compilation logic that reads these fields.
- `scripts/registry_validator.py` — validation logic that enforces registry-frontmatter consistency.
- `docs/how-to/creating-an-agent-template.md` — task guide for writing a new agent template.
