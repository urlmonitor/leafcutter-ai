---
title: "How to create an agent template"
type: how_to
status: active
created: 2026-05-28
last_updated: 2026-05-28
components:
  - build_pipeline
related_docs:
  - docs/agent-registry.md
  - docs/build-pipeline.md
  - docs/reference/skills-config-fields.md
---

# How to create an agent template

This guide walks you through every step required to add a new agent to the
leafcutter package — from choosing a name to verifying the compiled output.
Following these steps produces an agent that passes `build.py`, appears in
`.claude/agents/` after a build, and has a valid entry in
`config/agent_registry.json`.

---

## Prerequisites

- You have cloned the leafcutter-ai repository and can run `python scripts/build.py`.
- Python 3.9+ is on your PATH (`python --version`).
- You understand the three agent tiers (`supervisor`, `phase`, `utility`) and the
  concept of ticket-phase agents (those that appear in ticket `agents:` maps and are
  driven by `ticket-supervisor`).
- You have read `docs/build-pipeline.md` for an overview of how `build.py` compiles
  templates into `.claude/agents/`.

---

## Steps

### Step 1: Choose a name, tier, and visibility

Before creating any file, answer three questions:

1. **Name** — lowercase, hyphen-separated, unique across `config/agent_registry.json`.
   Examples: `sql-query`, `frontend-coder`, `explanation-author`.

2. **Tier** — one of:
   - `supervisor` — orchestrates other agents (e.g. `epic-supervisor`,
     `ticket-supervisor`, `create-ticket`).
   - `phase` — appears in ticket `agents:` maps; driven by `ticket-supervisor`.
   - `utility` — helper spawned by another agent; never appears in ticket maps directly.

3. **Visibility** — set the `portable` field:
   - `true` — domain-agnostic; belongs in the leafcutter portable package.
   - `false` — domain-specific; set `domain: "<your-domain>"` alongside.

Keep the name short and verb-noun-ish for phase/utility agents, and noun-role-ish for
supervisors. A name that reads naturally in a sentence like "spawn `<name>` to…" is
usually right.

---

### Step 2: Create the template file

Create a Markdown file at:

```
leafcutter-ai/templates/agents/<name>.md
```

For example, `templates/agents/my-agent.md`.

The file has two parts: a YAML frontmatter block, and a body section. The build
pipeline reads the frontmatter, strips it from the compiled output, and writes the
body to `.claude/agents/<name>.md` in the target project.

---

### Step 3: Write all required runtime frontmatter keys

These fields are consumed by Claude Code at runtime (not by `build.py`):

```yaml
---
name: my-agent
description: |
  One-paragraph description of what this agent does and when to use it.
  Use when: <concrete trigger conditions for when a user should invoke this agent>.
model: sonnet
tools: Bash, Read, Edit, Write, Agent
---
```

| Key | Type | Notes |
|---|---|---|
| `name` | string | Must match the filename (without `.md`) and the `id` in `agent_registry.json`. |
| `description` | string | Multi-line YAML literal. Displayed in the Claude Code agent picker. Include `Use when:` guidance so the LLM can auto-route correctly. |
| `model` | string | `sonnet` for most agents. Use `opus` only for orchestrators that must reason over large contexts. |
| `tools` | string | Comma-separated list of allowed tools. Common set: `Bash, Read, Edit, Write, Agent`. |

Optional runtime keys:

| Key | Type | Notes |
|---|---|---|
| `memory` | list | Paths to persistent memory files the agent loads on each invocation. |

---

### Step 4: Write build-directive frontmatter keys

These fields are consumed by `build.py` and are stripped from the compiled output:

```yaml
portable: true
signoff: true
domain: null
config_keys:
  my_setting:
    required: false
    description: "Description of what this setting controls."
adopter_notes: |
  Instructions for developers who install this agent in a new project.
  Describe which config_keys to fill in and which references to update.
requires_verification: true
```

| Key | Type | Required | Notes |
|---|---|---|---|
| `portable` | boolean | Yes | `true` for domain-agnostic agents; `false` for domain-specific ones. |
| `signoff` | boolean | Yes for phase agents | Set `true` when this agent uses the `signoff` skill to mark tickets done. |
| `domain` | string or null | Yes | Set to `null` when `portable: true`; set to a domain tag (e.g. `"bybit-trader"`) otherwise. |
| `config_keys` | object | No | Map of `<key>: {required: bool, description: str}` pairs. Keys here are injected into the body from `skills_config.json` at build time. |
| `adopter_notes` | string | No | Free-text guidance for developers installing this agent in a new project. |
| `requires_verification` | boolean | No | When `true`, build.py emits a warning if the compiled output is not verified by a test. |

---

### Step 5: Write the agent body

The body is everything after the closing `---` of the frontmatter. It becomes the
compiled agent file that Claude Code reads. Recommended structure:

```markdown
## Pre-Flight Reads (required before any edit)

On every invocation, before doing any work, read:

1. The ticket file at the path supplied by your caller.
2. Any referenced ADR or spec files.

## Tool Allowlist Reminder

Your tools are: `Bash`, `Read`, `Edit`, `Write`, `Agent`.
`Grep`, `Glob`, and MCP search tools are NOT available.

## Behaviour

<Core logic — what the agent does, in what order, with what acceptance criteria.>

## Constraints

- Do NOT modify files outside your stated scope.
- Do NOT escalate to the user directly — return a structured payload.

## Response Payload

On success:
{ "status": "ok", ... }

On failure:
{ "status": "failed", "blocker_summary": "...", ... }
```

Key rules for the body:

- Keep implementation constraints explicit. Phase agents should state what they
  will NOT do as clearly as what they will do.
- Include the sign-off invocation if `signoff: true` in frontmatter. Add
  `## Sign-off` with the recipe from `.claude/skills/signoff/SKILL.md §2`.
- Template placeholders use `{{key}}` syntax. The `config_keys` values are
  injected at build time from `skills_config.json`.

---

### Step 6: Register the agent in `agent_registry.json`

Open `config/agent_registry.json` and add a new entry to the `"agents"` array.
Every entry must satisfy the schema in `config/agent_registry.schema.json`.

**Minimum required fields:**

```json
{
  "id": "my-agent",
  "name": "My Agent",
  "tier": "phase",
  "role": "documentation",
  "portable": true,
  "domain": null,
  "spawn_allowlist": [],
  "spawned_by": ["ticket-supervisor"],
  "is_ticket_phase": true,
  "template_path": "templates/agents/my-agent.md",
  "model": "sonnet",
  "skills_used": ["signoff"]
}
```

**Additional fields for ticket-phase agents:**

```json
{
  "selection_criteria": {
    "description": "Assign when the ticket requires X.",
    "trigger_conditions": [
      {
        "type": "dsl",
        "expression": "files_touched contains docs/*.md"
      },
      {
        "type": "llm",
        "expression": "ticket is a documentation-only change"
      }
    ],
    "default_status": "not_needed"
  },
  "priority": 10,
  "priority_rationale": "Runs after coders and before PR review.",
  "requires_ticket_section": false
}
```

**Field reference:**

| Field | Type | Notes |
|---|---|---|
| `id` | string | Matches filename (without `.md`) and template `name:` key. Pattern: `^[a-z][a-z0-9-]*$`. |
| `tier` | enum | `supervisor`, `phase`, or `utility`. |
| `role` | string | Functional role: `orchestration`, `coding`, `review`, `commit`, `documentation`, `analysis`, `quality`. |
| `spawn_allowlist` | array | Agent IDs this agent may spawn. Use `"__ticket_phase_agents__"` for orchestrators that spawn all phase agents. |
| `spawned_by` | array | Agent IDs (or `"user"`) that legitimately invoke this agent. Keep consistent with callers' `spawn_allowlist`. |
| `is_ticket_phase` | boolean | `true` if this agent appears in ticket `agents:` maps. |
| `selection_criteria` | object or null | How `business-analyst` decides to assign this agent. Null for non-ticket-phase agents. |
| `priority` | integer | Phase execution order. Lower runs first. See canonical ordering table in `ticket-supervisor`. Required for `is_ticket_phase: true` agents. |
| `requires_ticket_section` | boolean | When `true`, every ticket that marks this agent `needed` must include a `### <agent-id>` subheading under `## Implementation Tasks`. |
| `skills_used` | array | Skills this agent loads at runtime. Use `[]` when none. |
| `owns_file_extensions` | array | File extensions (e.g. `[".py"]`) this agent is primary implementer for. Consumed by commit-guardian hooks. |

---

### Step 7: Update `spawned_by` on parent agents

For every agent that will invoke your new agent, add your agent's `id` to that
parent's `spawn_allowlist` in `agent_registry.json`.

For every entry in your new agent's `spawned_by` list, verify the corresponding
parent's `spawn_allowlist` includes your agent's `id`.

Example: if `ticket-supervisor` spawns your agent, confirm:

```json
// ticket-supervisor entry
"spawn_allowlist": ["__ticket_phase_agents__"]
```

Because `ticket-supervisor` uses the `"__ticket_phase_agents__"` wildcard, any
agent with `"is_ticket_phase": true` is automatically included. For non-phase
utility agents, you must add the `id` explicitly to the parent's `spawn_allowlist`.

---

### Step 8: Write a reference doc

Create a reference doc at:

```
docs/reference/<agent-name>.md
```

Minimum frontmatter and structure:

```markdown
---
title: "<Agent Name> — Reference"
type: reference
status: active
created: 2026-05-28
last_updated: 2026-05-28
components:
  - build_pipeline
---

# <Agent Name>

One sentence: what this agent does and when it is used.

## Inputs

What the agent receives (ticket_path, structured payload, etc.).

## Outputs

What it returns (structured payload fields, files written, sign-off status).

## Behaviour

Summary of the agent's algorithm.

## Constraints

What the agent will not do.

## See Also

- `templates/agents/<name>.md` — source template
- `config/agent_registry.json` — registry entry
```

---

### Step 9: Create a workflow template (if applicable)

If the agent is exposed to users as a slash command (e.g. `/my-agent`), create a
workflow template at:

```
templates/workflows/<name>.md
```

Minimum structure:

```markdown
---
description: "Invoke the <name> agent for <one-line purpose>."
---

# /<name> — <Short Title>

This workflow is the slash-command surface for the `<name>` agent.

<One paragraph describing what running /name does.>

{% if platform == 'claude' %}
Forward `$ARGUMENTS` verbatim to the `<name>` agent.
{% elif platform == 'antigravity' %}
Invoke the `<name>` agent by running its script via the terminal tool:
```bash
python .agents/agents/<name>/scripts/run.py --args="$ARGUMENTS"
```
{% endif %}
```

Skip this step for purely internal agents (tier: `utility`, or phase agents that
are only ever spawned by `ticket-supervisor`).

---

### Step 10: Run `build.py` and verify no errors

From the leafcutter-ai directory, run:

```bash
python scripts/build.py --target-dir . --validate
```

Expected output (no errors):

```
[BUILD] Loading config from skills_config.json ... ok
[BUILD] Validating agent registry ...
[BUILD] Registry OK: N agents, N valid.
[BUILD] Building agents ... N written, N up-to-date.
...
[BUILD] Done.
```

If the registry validation fails, the error message names the offending field.
Fix it in `agent_registry.json` and re-run.

If `--validate` reports placeholder-detection warnings about `{{key}}` tokens
left in compiled output, add the missing key to `skills_config.json` or remove
the placeholder from the template.

---

### Step 11: Verify the compiled agent file

After a successful build, confirm:

```bash
ls .claude/agents/<name>.md
```

Open the file and verify:

1. The YAML frontmatter contains `name:`, `description:`, `model:`, and `tools:`.
2. Build-directive keys (`portable`, `signoff`, `domain`, `config_keys`, etc.) are
   **absent** from the compiled output — the build pipeline strips them.
3. Any `{{key}}` placeholders have been replaced with values from `skills_config.json`.

Quick check command:

```bash
python -c "
import re
content = open('.claude/agents/<name>.md').read()
placeholders = re.findall(r'\{\{[^}]+\}\}', content)
if placeholders:
    print('Unresolved placeholders:', placeholders)
else:
    print('OK — no unresolved placeholders')
"
```

---

### Step 12: Commit and push following the standard ticket workflow

Stage the new files explicitly (never `git add .` or `git add -A`):

```bash
git add templates/agents/<name>.md
git add config/agent_registry.json
git add docs/reference/<name>.md
# if you created a workflow template:
git add templates/workflows/<name>.md
```

Commit:

```bash
git commit -m "feat: add <name> agent template and registry entry"
```

Push and open a PR via the standard workflow (`/commit-push-pr` or the `pull-request`
agent). The pre-commit hooks will validate:

- `check_ticket_signoff_parity.py` — ticket sign-off parity.
- `check_referential_integrity.py` — no dangling references in `agent_registry.json`.

If a hook blocks the commit, read the error output; it names the exact field or
reference that is invalid.

---

## Verification

After completing all steps, run the full registry validation:

```bash
python scripts/build.py --validate-only
```

Expected: `Registry OK: N agents, N valid.` with no errors.

Also confirm the agent appears in the Claude Code agent picker by opening a session
and typing `/` — your agent's name and description should appear if `build.py` was
run against the target directory.

---

## Troubleshooting

**1. `build.py` fails with "Unknown field in agent registry"**

The entry in `agent_registry.json` contains a field not defined in
`agent_registry.schema.json`. Check the schema's `additionalProperties: false`
constraint. Remove the unknown field or add it to the schema if intentional.

**2. Compiled agent file still contains `{{key}}` placeholders**

The `config_keys` entry exists in frontmatter but the corresponding key is missing
from `skills_config.json`. Either add the key to `skills_config.json` or remove the
`{{key}}` reference from the template body.

**3. `spawn_allowlist` / `spawned_by` inconsistency warning**

The `registry_validator.py` reports that agent A's `spawn_allowlist` names agent B,
but B's `spawned_by` does not include A (or vice versa). Fix both sides to be
consistent: add A to B's `spawned_by`, or add B to A's `spawn_allowlist`.

**4. `requires_ticket_section: true` but the ticket is missing the `### <agent-id>` section**

The `check_ticket_signoff_parity.py` hook enforces this at commit time. Add a
`### <agent-id>` subheading under `## Implementation Tasks` in the ticket, or set
`requires_ticket_section: false` in `agent_registry.json` if the agent does not
need a dedicated task section.

---

## Common Mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| Wrong tier — set `phase` for an orchestration agent | Agent appears in ticket `agents:` maps when it should not | Change `tier` to `supervisor` and `is_ticket_phase` to `false` |
| Missing `spawned_by` update on the parent agent | `registry_validator` warns about inconsistent spawn relationships | Add your new agent's `id` to the parent's `spawn_allowlist` in `agent_registry.json` |
| Bad `config_keys` format — used a list instead of an object | `build.py` fails with a `TypeError` during template injection | Change `config_keys` from a list to an object: `{key: {required: bool, description: str}}` |
| Forgot `inject_registry` for supervisor agents that need the full agent list | Supervisor cannot read the registry at runtime | Not a standalone frontmatter key — the registry is available at `config/agent_registry.json`; confirm the agent reads it via `Read` or `Bash` in its body |
| `name:` in frontmatter doesn't match the filename | `build.py` writes the file correctly but the Claude Code agent picker shows the wrong name | Ensure `name: <agent-name>` matches `templates/agents/<agent-name>.md` and `"id": "<agent-name>"` in the registry |
| `is_ticket_phase: true` but no `priority` field | `ticket-supervisor` falls back to declaration order, breaking canonical phase ordering | Add a `priority` integer and `priority_rationale` string to the registry entry |
| `signoff: false` (or absent) for a phase agent | Agent finishes work but does not update the ticket's `agents:` map | Set `signoff: true` in frontmatter and implement the `signoff` skill recipe at the end of the agent body |

---

## See Also

- `docs/agent-registry.md` — full `agent_registry.json` schema reference
- `docs/build-pipeline.md` — how `build.py` compiles templates
- `docs/reference/skills-config-fields.md` — all `skills_config.json` fields
- `.claude/skills/signoff/SKILL.md` — sign-off recipe for phase agents
- `.claude/skills/building-epics/SKILL.md` — how `ticket-supervisor` dispatches agents
