---
name: add-agent-to-package
description: >
  Promote a project-local agent into the leafcutter package atomically.
  Moves the agent template, registers it in agent_registry.json, and updates
  docs/agents/README.md. Invoked by workflow-architect.
allowed-tools: Read, Edit, Write, Bash(git add *), Bash(python *)
---

# add-agent-to-package

Promote a project-local agent into the leafcutter package completely and
atomically. No partial promotions.

## Inputs

| Field | Required | Description |
|-------|----------|-------------|
| `agent_id` | yes | Agent identifier, e.g. `workflow-architect` (matches file basename without `.md`) |
| `tier` | yes | Agent tier: `supervisor`, `phase`, or `utility` |
| `role` | yes | Agent role: `orchestration`, `coding`, `documentation`, `git`, etc. |
| `description` | yes | One-sentence description of what the agent does |
| `model` | no | Model name (default: `sonnet`) |
| `source_path` | no | Override source path (default: `.claude/agents/<agent_id>.md`) |

## Step 1 — Idempotency check

Before writing anything:

1. Confirm `leafcutter/templates/agents/<agent_id>.md` does NOT exist.
   If it does, stop with: "Agent `<agent_id>` already has a template at that path. Delete it first if you intend to replace it."
2. Confirm `leafcutter/config/agent_registry.json` does not already have an entry with `id: "<agent_id>"`.
   If it does, stop with: "Agent `<agent_id>` already has a registry entry."

## Step 2 — Read source agent

Read the source agent file at `<source_path>` (default: `.claude/agents/<agent_id>.md`).
Extract its system prompt content (the body after the YAML frontmatter `---` block).

## Step 3 — Write the package template

Create `leafcutter/templates/agents/<agent_id>.md` with this structure:

```markdown
---
name: <agent_id>
description: |
  <description>
model: <model>
tools: <tools from source or reasonable defaults>
portable: true
signoff: false
domain: null
inject_registry: false
config_keys: {}
adopter_notes: |
  Add project-specific context here if needed.
---

<system prompt body from source agent, verbatim>
```

Key rules for the template:
- Set `portable: true` (required for package inclusion)
- Set `domain: null` (domain-specific value must be removed)
- Preserve the full system prompt body without modification
- If the source frontmatter already has `portable: true`, confirm and keep it

## Step 4 — Register in agent_registry.json

Append an entry to `leafcutter/config/agent_registry.json` inside the `agents` array:

```json
{
  "id": "<agent_id>",
  "name": "<Human-readable name from agent_id with title-case>",
  "tier": "<tier>",
  "role": "<role>",
  "portable": true,
  "domain": null,
  "spawn_allowlist": [],
  "spawned_by": [],
  "is_ticket_phase": false,
  "selection_criteria": {
    "trigger_conditions": [
      {
        "type": "llm",
        "expression": "<description>"
      }
    ]
  },
  "template_path": "templates/agents/<agent_id>.md",
  "model": "<model>",
  "skills_used": []
}
```

Adjust `spawn_allowlist`, `spawned_by`, `is_ticket_phase`, and `selection_criteria` to match
the agent's actual behaviour. The template above is the minimal starting point.

## Step 5 — Update docs/agents/README.md

Use Edit (never Write) to add a row to the appropriate role table in `docs/agents/README.md`.
Anchor the edit on an adjacent row in the same table:

```
| [`<agent_id>`](docs/agents/<role>/<agent_id>.md) | <description> |
```

If the role table does not yet have an individual reference doc, add the agent name without
a hyperlink and note that the reference doc is pending.

## Step 6 — Run build.py and validate

1. Run `python leafcutter/scripts/build.py --validate-only` — must pass.
2. Run `python leafcutter/scripts/build.py --target-dir . --force` to compile
   the template to `.claude/agents/<agent_id>.md`.
3. Confirm `.claude/agents/<agent_id>.md` was generated.

## Invariants

- NEVER overwrite an existing template (idempotency check in Step 1).
- `portable: true` is mandatory in the template frontmatter.
- `domain: null` is mandatory — domain-specific values must be stripped.
- ALWAYS run `build.py --validate-only` before `--force` to catch registry inconsistencies.
- Use Edit (not Write) for `docs/agents/README.md` to avoid overwriting the full file.
