---
title: How to create an agent template
type: how_to
status: active
created: 2026-05-28
last_updated: 2026-10-15
components:
- build_pipeline
related_docs:
- docs/reference/agent-template-frontmatter.md
- docs/agent-registry.md
- docs/build-pipeline.md
- docs/reference/skills-config-fields.md
description: Overview of How to create an agent template.
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
tools: Bash, Read, Edit, Write
---
```

| Key | Type | Notes |
|---|---|---|
| `name` | string | Must match the filename (without `.md`) and the `id` in `agent_registry.json`. |
| `description` | string | Multi-line YAML literal. Displayed in the Claude Code agent picker. Include `Use when:` guidance so the LLM can auto-route correctly. |
| `model` | string | `sonnet` for most agents. Use `opus` only for orchestrators that must reason over large contexts. |
| `tools` | string | Comma-separated list of allowed tools. Common set: `Bash, Read, Edit, Write`. Add `Skill` if you grant skills (Step 4) and `Agent` if you permit sub-agents (Step 5). |

Optional runtime keys: `memory` (list of persistent memory file paths loaded on each invocation).

---

### Step 4: Grant skills in the frontmatter (if the agent uses any)

The template's own frontmatter is the ONLY place a skill is granted. Declare a
`skills:` list beside `tools:`, and add `Skill` to `tools:`:

```yaml
tools: Bash, Read, Edit, Write, Skill
skills:
- skill_id: doc-enforcer
  mode: always
- skill_id: signoff
  mode: conditional
  condition: When invoked with a ticket_path, load signoff to record your sign-off.
```

`mode` is `always` or `conditional`; a `conditional` grant with no `condition`
refuses the build. The build appends a `## Your Available Skills` table to the
compiled prompt from this list, so nothing else is needed for the grant to arrive.

Do NOT:

- write a `{{my_skills_used}}` marker or a hand-written skills table in the body
  (the build warns about a duplicate table and strips a retired marker with a warning);
- hand-edit `skills_invoked` in `config/agent_registry.json` (a derived copy; the
  "Transform agent registry" pre-commit hook regenerates it from `skills:`, and the
  build reports a disagreeing copy while the declaration wins) or write the
  retired `skills_used` there (the validator and build refuse it);
- list a skill that is not installed (a missing skill id refuses the build) or
  a non-empty `skills:` without `Skill` in `tools:` (also refuses).

Skip this step if the agent loads no skills.

---

### Step 5: Permit sub-agents in the frontmatter (if the agent dispatches any)

The template's own frontmatter is the ONLY place a sub-agent is permitted. Declare
`spawn_allowlist:` beside `tools:`, and add `Agent` to `tools:`:

```yaml
tools: Bash, Read, Edit, Write, Agent
spawn_allowlist:
- research-agent
- test-runner
```

The entry `__ticket_phase_agents__` stays one entry and expands on every build to
every agent whose registry `is_ticket_phase` is `true` (that flag is still set in
`config/agent_registry.json`; if no agent has it, the build refuses). The build appends a `## Your Available Sub-Agents`
table from this list, so nothing else is needed for the permission to arrive.

Do NOT:

- write a hand-written "Available Sub-Agents" table or list, or a
  `{{my_spawn_allowlist}}` marker, in the body (the build warns about a
  contradicting list and strips a retired marker with a warning);
- hand-edit `spawn_allowlist` in the registry — it is a derived copy that the
  same pre-commit hook regenerates, and the build reports a disagreeing copy
  while the declaration wins;
- declare a sub-agent without `Agent` in `tools:`, or one with no packaged
  `templates/agents/<id>.md` — both refuse the build (project-local agent
  definitions are not supported yet, KI-AR-005).

What you DO still edit by hand: each target agent's `spawned_by` in
`config/agent_registry.json` must name your agent (Step 9), or the registry
validator rejects the one-sided edge.

Skip this step if the agent dispatches no sub-agents.

---

### Step 6: Write build-directive frontmatter keys

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
| `domain` | string or null | Yes | Set to `null` when `portable: true`; set to a domain tag (e.g. `"billing"`) otherwise. |
| `config_keys` | object | No | Map of `<key>: {required: bool, description: str}` pairs. Keys here are injected into the body from `skills_config.json` at build time. |
| `adopter_notes` | string | No | Free-text guidance for developers installing this agent in a new project. |
| `requires_verification` | boolean | No | When `true`, build.py emits a warning if the compiled output is not verified by a test. |

---

### Step 7: Write the agent body

The body is everything after the closing `---` of the frontmatter. It becomes the
compiled agent file that Claude Code reads. Recommended structure:

```markdown
## Pre-Flight Reads (required before any edit)

On every invocation, before doing any work, read:

1. The ticket file at the path supplied by your caller.
2. Any referenced ADR or spec files.

## Tool Allowlist Reminder

Your tools are: `Bash`, `Read`, `Edit`, `Write`.
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
- Do not describe skills or sub-agents in the body: no skills table, no
  "Available Sub-Agents" table, no `{{my_skills_used}}` or `{{my_spawn_allowlist}}`
  marker. Steps 4 and 5 are the only place they are declared; the build appends
  both sections.
- Template placeholders use `{{key}}` syntax. The `config_keys` values are
  injected at build time from `skills_config.json`.

---

### Step 8: Register the agent in `agent_registry.json`

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
  "model": "sonnet"
}
```

`spawn_allowlist` and `skills_invoked` are derived from the template frontmatter
(Steps 4 and 5): do not write `skills_invoked` and leave `spawn_allowlist` empty
here. The `transform-agent-registry` pre-commit hook fills them when you commit.
Never add `skills_used`: it is retired and the validator and build refuse it.

**Additional fields for ticket-phase agents:**

```json
{
  "selection_criteria": {
    "description": "Assign when the ticket requires X.",
    "trigger_conditions": [
      {"type": "dsl", "expression": "files_touched contains docs/*.md"},
      {"type": "llm", "expression": "ticket is a documentation-only change"}
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
| `spawn_allowlist` | array | DERIVED from the template's `spawn_allowlist:` frontmatter (Step 5); do not hand-edit. |
| `spawned_by` | array | Hand-authored. Agent IDs (or `"user"`) that invoke this agent; must match the callers' declared `spawn_allowlist:` (Step 9). |
| `is_ticket_phase` | boolean | `true` if this agent appears in ticket `agents:` maps. |
| `selection_criteria` | object or null | How `business-analyst` decides to assign this agent. Null for non-ticket-phase agents. |
| `priority` | integer | Phase execution order. Lower runs first. See canonical ordering table in `ticket-supervisor`. Required for `is_ticket_phase: true` agents. |
| `requires_ticket_section` | boolean | When `true`, every ticket that marks this agent `needed` must include a `### <agent-id>` subheading under `## Implementation Tasks`. |
| `skills_invoked` | array | DERIVED from the template's `skills:` frontmatter (Step 4); do not hand-edit. (`skills_used` is retired and refused.) |
| `owns_file_extensions` | array | File extensions (e.g. `[".py"]`) this agent is primary implementer for. Consumed by commit-guardian hooks. |

---

### Step 9: Keep `spawned_by` consistent on both ends of every spawn edge

`spawned_by` is hand-authored (the hook never touches it), and the registry
validator rejects an edge recorded on one side only.

- **Your agent is spawned by others:** each caller must declare your `id` in its
  own template's `spawn_allowlist:` frontmatter (Step 5; never in the registry
  field), and your registry entry's `spawned_by` must list each caller.
- **Your agent spawns others:** in `config/agent_registry.json`, add your `id`
  to the `spawned_by` of every agent you declared in Step 5.

`ticket-supervisor` declares `__ticket_phase_agents__`, so any agent with
`"is_ticket_phase": true` is covered without editing its template; a non-phase
utility agent must be named explicitly in the caller's `spawn_allowlist:`.

After the build, confirm the edge on the agent card (a build output, not
hand-written): `docs/agents/cards/<id>.card.md` must list the caller under
"Spawned By" and the diagram must show the edge.

---

### Step 10: Write a reference doc

Create a reference doc at:

```
docs/reference/<agent-name>.md
```

Use frontmatter `type: reference`, `status: active`, `components: [build_pipeline]`,
and these sections: one-sentence summary, `## Inputs`, `## Outputs`,
`## Behaviour`, `## Constraints`, `## See Also` (link the source template and
registry entry). Follow `docs/how-to/documentation/write-reference.md`.

---

### Step 11: Create a workflow template (if applicable)

If the agent is exposed to users as a slash command (e.g. `/my-agent`), create a
workflow template at:

```
templates/workflows/<name>.md
```

Model it on an existing file in `templates/workflows/`: a `description:`
frontmatter line, a `# /<name>` heading, one paragraph on what the command does,
and a `{% if platform == 'claude' %}` block that forwards `$ARGUMENTS` verbatim to
the `<name>` agent (with an `{% elif platform == 'antigravity' %}` variant).

Skip this step for purely internal agents (tier: `utility`, or phase agents that
are only ever spawned by `ticket-supervisor`).

---

### Step 12: Run `build.py` and verify no errors

From the leafcutter-ai directory, run:

```bash
python scripts/build.py --target-dir . --validate
```

Expected: `Registry OK: N agents, N valid.` and `[BUILD] Done.` with no errors.
A declared skill or sub-agent that does not exist, or a missing `Skill`/`Agent`
tool, refuses the build here. If registry validation fails, the error names the
offending field; fix it and re-run.

If `--validate` reports placeholder-detection warnings about `{{key}}` tokens
left in compiled output, add the missing key to `skills_config.json` or remove
the placeholder from the template.

---

### Step 13: Verify the compiled agent file

After a successful build, confirm:

```bash
ls .claude/agents/<name>.md
```

Open the file and verify:

1. The YAML frontmatter contains `name:`, `description:`, `model:`, and `tools:`.
2. Build-directive keys (`portable`, `signoff`, `domain`, `config_keys`, etc.) are
   **absent** from the compiled output — the build pipeline strips them.
3. Any `{{key}}` placeholders have been replaced with values from `skills_config.json`.
4. If you declared skills or sub-agents, the file ends with a
   `## Your Available Skills` and/or `## Your Available Sub-Agents` section.

Quick check for unresolved placeholders (no output means none):

```bash
grep -n "{{" .claude/agents/<name>.md
```

---

### Step 14: Commit and push following the standard ticket workflow

Stage the new files explicitly (never `git add .` or `git add -A`):

```bash
git add templates/agents/<name>.md config/agent_registry.json docs/reference/<name>.md
```

Add `templates/workflows/<name>.md` too if you created one. Commit through the
`commit` agent (direct `git commit` is blocked), then push and open a PR via
`/commit-push-pr` or the `pull-request` agent. The pre-commit hooks validate:

- `transform-agent-registry` — regenerates the derived registry fields from your
  frontmatter and re-stages `config/agent_registry.json`; review that diff.
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
but B's `spawned_by` does not include A (or vice versa). Add A to B's `spawned_by`
in the registry, or add B to A's frontmatter `spawn_allowlist:` (never to the
registry field: the hook regenerates it from the frontmatter).

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
| Spawn edge recorded on one side only | `registry_validator` rejects the one-sided edge | Declare the target in the caller's frontmatter `spawn_allowlist:` and list the caller in the target's registry `spawned_by` (Step 9) |
| Skills or sub-agents added by editing the registry or the body | The next commit's hook overwrites the registry edit; the build warns or reports, and the declaration wins | Declare them in frontmatter only (Steps 4 and 5) |
| `skills:` without `Skill`, or `spawn_allowlist:` without `Agent`, in `tools:` | Build refuses | Add the tool to `tools:` |
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
