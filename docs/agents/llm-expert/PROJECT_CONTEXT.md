---
title: Project Context — llm-expert
type: reference
status: active
created: 2026-06-04
last_updated: 2026-07-15
components:
- infrastructure
related_docs:
- docs/agents/conventions.md
- docs/agents/README.md
- templates/skills/signoff/SKILL.md
- CLAUDE.md
description: Overview of Project Context — llm-expert.
---
# Project Context — `llm-expert`

This file is read by the `llm-expert` agent at startup (runtime discovery) before any write operation. It provides project-specific rules that every LLM-instructions specialist must know: shell conventions, frontmatter schemas, signoff protocol, nesting/spawn-allowlist rules, and the expanded Prompt-Quality Checklist with concrete examples.

This file is **leafcutter-internal** — it lives in `docs/agents/llm-expert/` and is NOT deployed to consumer projects via `build.py`. Consumer deployments use the agent template at `templates/agents/llm-expert.md`.

Cross-reference: [docs/agents/README.md §PROJECT_CONTEXT Injection](../README.md#project_context-injection--runtime-discovery-convention) for the runtime-discovery contract.

---

## Section 1: Shell Convention

### Rule

Every Bash tool call in any agent template or skill body MUST be a **single, simple command**. This rule comes directly from `CLAUDE.md` and applies to every file the `llm-expert` agent writes or edits.

> Every Bash tool call MUST be a single, simple command. Never chain with `&&`, `;`, `||`, pipes to other commands, or multi-line scripts. Never use `cd` — use absolute paths or `git -C` instead.

### Why This Rule Exists

Claude Code auto-allows single-command Bash calls but prompts the user for confirmation on compound commands or chains. Compound commands in agent templates cause confirmation prompts during agent execution, interrupting the automation loop and breaking the "auto-run" contract that epics depend on.

### Detection Heuristics for Violations

Scan for these patterns in any agent template or skill body being reviewed or authored:

| Pattern | Violation type | Notes |
|---|---|---|
| `cmd1 && cmd2` | Chain with `&&` | Both commands must be separate Bash tool calls |
| `cmd1 ; cmd2` | Chain with `;` (semicolon outside a quoted string) | Note: semicolons inside YAML strings or quoted heredocs are NOT violations |
| `cmd1 \|\| cmd2` | Chain with `\|\|` | Must be split into two Bash calls |
| `cd /some/dir && python ...` | `cd` followed by another command | Replace with absolute path: `python /some/dir/script.py` |
| `cmd1 \| cmd2 \| cmd3` | Multi-stage pipe producing side effects | Acceptable for read-only pipes (e.g. `grep ... \| head`); disallowed when final stage writes a file or produces side effects |
| Multi-line heredoc scripts via `bash -c '...'` | Multi-line script | Split into individual Bash tool calls |

### Environment Variable Syntax (Allowed)

Setting an environment variable as a prefix to a single command is a **single command**, not a chain:

```bash
# CORRECT — single command with env var prefix
MY_ENV=value python /path/to/script.py --arg value
```

This is equivalent to `env MY_ENV=value python ...` — POSIX treats it as one command, not two.

### Examples

**Wrong (compound commands — triggers confirmation prompt):**

```bash
# Wrong: chained with &&
cd /home/user/project && python script.py --flag value

# Wrong: semicolon chain
git add file.py ; git commit -m "message"

# Wrong: multi-step pipe with side effect
find . -name "*.py" | xargs grep "import os" > /tmp/results.txt

# Wrong: multi-line script in single Bash call
bash -c 'cd /repo
git status
git diff'
```

**Right (single commands — auto-allowed):**

```bash
# Right: absolute path, no cd
python /home/user/project/script.py --flag value

# Right: each git call is its own Bash tool call
git -C /home/user/project add file.py
# (then a second Bash tool call:)
git -C /home/user/project commit -m "message"

# Right: pipe is acceptable for read-only search
find /home/user/project -name "*.py" | grep "import os"

# Right: stderr redirected to /tmp/ with absolute path
python /home/user/project/script.py 2>/tmp/script_err.txt
```

---

## Section 2: Agent Frontmatter Schema

Every file at `templates/agents/<agent>.md` opens with a YAML frontmatter block. The `llm-expert` agent must know which fields are required, which are build-injected, and what each field means.

### Required Fields (hand-authored)

| Field | Type | Allowed values | Purpose |
|---|---|---|---|
| `name` | string | kebab-case, matching the filename stem | Unique identifier. Drives auto-trigger matching. Must be unique across `templates/agents/`. |
| `description` | string (multi-line allowed) | Free text; must follow a visibility-class shape (see `docs/agents/conventions.md §3`) | Primary auto-trigger surface. Vague descriptions fail to fire. Use "Use when:" sentences at the end. |
| `model` | enum | `haiku`, `sonnet`, `opus` | Pins the model tier per ADR-006 §2.1. Default is `sonnet`. `opus` is reserved for escalation targets only. |
| `tools` | comma-separated list | See tier-floor table in `docs/agents/conventions.md §4` | Lists every tool the agent is permitted to call. Empty means NO tools. Sonnet floor is `Bash, Read, Write, Edit`. |
| `portable` | boolean | `true` or `false` | `true` means the agent has zero project-domain imports and can be deployed to any consumer project by `build.py`. |
| `signoff` | boolean | `true` or `false` | When `true`, the agent is a phase agent that invokes the `signoff` skill as its final action on every ticket invocation. A `## Sign-off` section MUST be present in the body. |
| `domain` | string or null | A project-specific domain string, or `null` for portable agents | Portable agents always use `null`. Domain agents use a string matching their project module (e.g. `"live_trader"`). |
| `config_keys` | YAML object | Key-value pairs or `{}` | Consumer-project configuration keys injected at deploy time. Use `{}` when none. |
| `adopter_notes` | string | Free text | Human-readable notes for consumers deploying this agent to their project. |
| `requires_verification` | boolean | `true` or `false` | When `true`, the agent's output requires human or automated verification before it is committed. Signals to ticket-supervisor that this phase has additional validation requirements. |
| `spawn_allowlist` | list of agent names | Agent IDs from `config/agent_registry.json` | Required whenever the agent body invokes the `Agent` tool. Every agent ID in this list must exist in the registry. Omitting it when the agent spawns sub-agents is a Prompt-Quality Checklist failure (Section 6, item 4). |

### Build-Injected Fields

These fields are populated by `build.py` or `build_phases.py` during the build pipeline. **Do NOT hand-author these fields in a new template** — `build.py` will overwrite them on the next build pass:

| Field | Injected by | What it contains |
|---|---|---|
| `inject_registry` | `build_phases.py` | Inlines a summary of the agent registry into the compiled agent at deploy time. |
| `config_keys.<key>` | `build.py --target-dir` | Consumer-project values resolved from `leafcutter/config/paths.json` or `consumer-config.json`. |

### Field: `domain` (null for portable agents)

- Portable agents always set `domain: null`. This signals to `build.py` that the agent has no project-domain dependencies and can be safely deployed to any consumer project.
- Domain-specific agents (those that import or reference project-specific modules) must set `domain` to the module name (e.g. `"live_trader"`, `"sql_functions"`). `build.py` will not deploy domain agents to consumers.
- The `llm-expert` agent is portable: `domain: null`.

### Example: Complete Frontmatter Block

```yaml
---
description: |
  Short summary line.
  Use when: <specific trigger 1>; <specific trigger 2>.
model: sonnet
name: my-new-agent
tools: Bash, Read, Edit, Write
portable: true
signoff: true
domain: null
config_keys: {}
adopter_notes: |
  Phase agent. Invoked by ticket-supervisor when <condition>.
requires_verification: false
default_artifact_checklist:
  - artifact_written
  - convention_check_passed
---
```

---

## Section 3: Skill Frontmatter Schema

Every file at `templates/skills/<name>/SKILL.md` opens with a YAML frontmatter block. This schema is simpler than the agent schema.

### Required Fields

| Field | Type | Purpose |
|---|---|---|
| `name` | string | The skill's identifier. Must match the directory name (`templates/skills/<name>/`). Used in agent `skills_used` lists and in `add-skill-to-package` invocations. |
| `description` | string | Human-readable summary of when to invoke this skill. Written in imperative voice: "Use when an agent needs to …". Also used by Claude Code to auto-load the skill on matching intent. |
| `allowed-tools` | comma-separated list | Whitelist of tools the skill code may call when loaded. This is a **capability declaration**, not an enforcement fence — the Claude Code harness does not mechanically block tool calls, but the llm-expert agent must ensure the skill body only calls tools in this list. |

### Field: `allowed-tools` (purpose and scope)

The `allowed-tools` list in a skill frontmatter is the **skill's tool contract**, analogous to `tools:` in an agent template. It declares which tool calls appear in the skill body.

- **Why it matters**: When an agent loads a skill (via `Read`), the skill body may instruct the agent to use additional tools. The `allowed-tools` list makes those tool calls visible to reviewers and to the `llm-expert` agent's Prompt-Quality Checklist.
- **Scope**: `allowed-tools` applies only to the skill body's direct tool calls, not to sub-agent calls. If a skill instructs "spawn a specialist via Agent tool", the `Agent` tool must appear in `allowed-tools`.
- **Validation rule**: During a Prompt-Quality audit, verify that every tool called in the skill body appears in `allowed-tools`, and that `allowed-tools` contains no tools absent from the body.

### Example: Skill Frontmatter

```yaml
---
allowed-tools: Read, Edit
description: Use when a phase agent finishes work on a ticket OR when a supervisor
  needs to validate ticket state. Provides the canonical status enum, atomic sign-off
  recipe, and comment-append recipe.
name: signoff
---
```

Cross-reference: `templates/skills/signoff/SKILL.md` (canonical example), `templates/skills/building-epics/SKILL.md` (example with broader allowed-tools).

---

## Section 4: Signoff Protocol

### Overview

The signoff protocol is the contract that ensures every phase agent (including `llm-expert`) updates ticket state correctly at the end of its invocation. It is defined in full at `templates/skills/signoff/SKILL.md`. This section summarises the protocol from the perspective of the `llm-expert` agent and explains why it matters for ticket-supervisor choreography.

### Reference: signoff SKILL.md §2 and §4

- **§2 (Atomic Sign-off Recipe)**: On success, the agent performs two `Edit` calls and one `Bash` call in this order:
  1. Flip `agents.<agent-name>: needed` → `agents.<agent-name>: signed_off` in frontmatter.
  2. Check the `- [ ] <agent-name>` box in `## Sign-offs`, adding the `— YYYY-MM-DD HH:MM` timestamp.
  3. Call `submit_feedback.py` and capture the `feedback_id`.
  4. Append a `## Comments` entry with the heading `### YYYY-MM-DD HH:MM — <agent-name> (status: ok)`.

- **§4 (Failed Path)**: On failure, the agent sets `agents.<agent-name>: failed`, leaves the Sign-offs checkbox unchecked with a `— failed YYYY-MM-DD HH:MM` suffix, and appends a `(status: blocker)` comment.

### The Parity Guard (Three-Place Parity Rule)

The pre-commit hook `check_ticket_signoff_parity.py` validates three locations simultaneously. All three must be updated before committing:

1. **Frontmatter `agents:` map** — `<agent-name>: signed_off`
2. **`## Sign-offs` checklist** — `- [x] <agent-name> — YYYY-MM-DD HH:MM`
3. **`## Implementation Tasks` checkboxes** — every `- [ ]` item under `### <agent-name>` must be flipped to `- [x]`

A common failure: updating frontmatter and Sign-offs but leaving implementation task checkboxes unchecked. This produces a parity-guard commit block.

### Timestamps and Ordering Enforcement

- Timestamp format is exactly `YYYY-MM-DD HH:MM` (24-hour, minute resolution, no seconds, no timezone).
- The timestamp in `## Sign-offs` and the timestamp in `## Comments` must match.
- The ticket-supervisor reads the **last** `## Comments` heading to determine the status tag. If two agents sign off in the same minute, declaration order in the YAML is the tiebreaker.
- `(status: ok)` → ticket-supervisor moves to next `needed` agent.
- `(status: blocker)` → ticket-supervisor enters failure adjudication (building-epics §3).
- `(status: question)` → ticket-supervisor halts the ticket and surfaces to the user.

### Why Signoff Matters for Ticket-Supervisor Choreography

The ticket-supervisor reads `agents:` map status and the last comment heading to know what happened and what to do next. If the parity guard fires at commit time, the commit fails and the entire ticket pipeline stalls until a human fixes the ticket file. Writing correct signoffs on the first attempt keeps the automation loop unblocked.

Cross-reference: `templates/skills/signoff/SKILL.md` §1 (Status Enum), §2 (Atomic Sign-off Recipe), §3 (Comment-Append Recipe), §4 (Failed Path), §5 (Validator Rules).

---

## Section 5: Nesting / Spawn-Allowlist Rules

### Depth Cap

The Claude Code harness enforces a hard depth limit for sub-agent spawning:

| Depth | Who runs at this depth |
|---|---|
| **Depth 0** | The user's direct session (e.g. `/build-feature`, `/create-ticket`) |
| **Depth 1** | First-level sub-agents (e.g. `ticket-supervisor`, `documentation-expert`) |
| **Depth 2** | Second-level sub-agents (e.g. `python-coder`, `reference-author` spawned by `documentation-expert`) |
| **Depth 3** | Third-level sub-agents (e.g. `research-agent` spawned by `python-coder`) |

**The hard limit is depth 3.** An agent running at depth 3 MUST NOT spawn further sub-agents. Attempts to do so will silently skip — the child agent will appear to complete but produce no output. This is the most common cause of "agent completed but nothing happened" failures in nested dispatch.

**Why depth is capped**: unbounded recursion is prevented so the harness can guarantee deterministic execution within a session. Depth-3 sub-agents also have very limited context because their parents' messages fill a significant portion of the window.

The `llm-expert` agent runs at depth 1 (spawned by ticket-supervisor at depth 0). It may therefore spawn sub-agents at depth 2. Those depth-2 agents (e.g. `research-agent`) may spawn depth-3 agents, which is the hard floor.

Cross-reference: `~/.claude/projects/<project-slug>/memory/agent_nesting_limit.md` — user-memory feedback entry capturing this constraint.

### spawn_allowlist

Every agent template that invokes the `Agent` tool MUST declare a `spawn_allowlist` in its frontmatter (registry source) or in a `## Your Available Sub-Agents` section in its body. The spawn_allowlist is the **contract** between the agent and its supervisor over which agents it is permitted to spawn.

**Contract rules:**

1. An agent that calls the `Agent` tool without a declared `spawn_allowlist` is a Prompt-Quality Checklist failure (Section 6, item 4).
2. The `spawn_allowlist` must contain only agent IDs that exist in `config/agent_registry.json`.
3. When ticket-supervisor spawns a phase agent from a ticket's `agents:` map, it validates the name against the registry's `is_ticket_phase: true` entries. Non-existent or non-phase agents are blocked with a structured payload.
4. The `llm-expert` agent's spawn_allowlist (as defined in `config/agent_registry.json`) is: `["research-agent"]` — the `llm-expert` agent may spawn `research-agent` for context-gathering during authoring tasks. An agent with no permitted sub-agents uses the empty allowlist `[]` as its `spawn_allowlist` value.

**Example: spawn_allowlist in registry JSON:**

```json
{
  "id": "documentation-expert",
  "spawn_allowlist": [
    "research-agent",
    "adr-author",
    "architecture-diagram-author",
    "explanation-author",
    "how-to-author",
    "reference-author",
    "glossary-triage"
  ]
}
```

### spawned_by

The `spawned_by` field in `config/agent_registry.json` is the inverse of `spawn_allowlist`. It declares which agents are permitted to spawn this agent.

**How ticket-supervisor uses spawned_by:**

When ticket-supervisor reads a ticket's `agents:` map and prepares to spawn `X`, it checks whether `ticket-supervisor` is in `X.spawned_by`. If not, the dispatch is blocked (registry validation failure).

**Example: spawned_by for a phase agent:**

```json
{
  "id": "python-coder",
  "spawned_by": ["ticket-supervisor", "sql-coder"]
}
```

This means `python-coder` can be spawned by `ticket-supervisor` (standard ticket dispatch) or by `sql-coder` (when sql-coder delegates Python work). Any other agent attempting to spawn `python-coder` would fail validation.

**The full contract:**

- If an agent spawns sub-agents → it MUST declare `spawn_allowlist` in its registry entry.
- If an agent can be spawned by another agent → it MUST list the spawning agent in `spawned_by`.
- Both fields are enforced by the registry validation logic in `ticket-supervisor` and by code review.

---

## Section 6: Prompt-Quality Checklist (Expanded)

This is the expanded version of the checklist from `templates/agents/llm-expert.md`. Each item includes detection heuristics and concrete violation examples.

The `llm-expert` agent MUST run every item before declaring any written or edited agent template or skill body complete. A failing item is a blocker — fix the violation, then re-run the checklist.

---

### Item 1: No Compound Bash Commands

**What to check:** Scan every instruction in the agent body that ends in a Bash tool call. Look for any of the violation patterns in Section 1 of this file.

**Detection heuristics:**

- Text like "run `cmd1 && cmd2`" or "execute `cmd1; cmd2`" in the body.
- A code block where a single line contains `&&`, `;` (outside a quoted string), `||`.
- A Bash call with `cd /path/to/dir` followed by another command on the same line.

**Violation example:**

```
## Step 3
Run the tests:
```bash
cd /home/user/project && python -m pytest unit_tests/ -v 2>&1 | tee /tmp/test.log
```
```

**Correct form:**

```
## Step 3
Run the tests:
```bash
python -m pytest /home/user/project/unit_tests/ -v 2>/tmp/test_err.log
```
```

---

### Item 2: Tool Allowlist Matches Body Usage

**What to check:** Extract the `tools:` value from the frontmatter. Then scan the body for every tool call (explicit `Read`, `Edit`, `Write`, `Bash`, `Agent`, `mcp__*` references). Verify the two sets are equal.

**Detection heuristics:**

- YAML frontmatter `tools:` field lists X tools.
- Body mentions or implies tool calls Y1, Y2, Y3.
- If Y not in X → violation (missing from allowlist).

**Violation example:**

```yaml
tools: Bash, Read, Edit
```

```markdown
## Step 4
Write the output file using the `Write` tool:
```
# → Violation: `Write` is used in the body but absent from `tools:`.
```

**Correct form:**

```yaml
tools: Bash, Read, Edit, Write
```

---

### Item 3: No Tools in Body Absent from Allowlist

**What to check:** The inverse of Item 2. Look for any tool reference in the body that does not appear in the `tools:` frontmatter line.

**Detection heuristics:**

- Search the body for `mcp__`, `Grep`, `Glob`, or any other tool name.
- If a tool name appears in the body but not in `tools:` → violation.

**Violation example:**

```yaml
tools: Bash, Read
```

```markdown
Use `mcp__jcodemunch__get_blast_radius` to check the impact.
```
# → Violation: `mcp__jcodemunch__get_blast_radius` is absent from `tools:`.
```

**Correct form (option A — add to tools):**

```yaml
tools: Bash, Read, mcp__jcodemunch__get_blast_radius
```

**Correct form (option B — remove the reference):**

Remove the `mcp__jcodemunch__get_blast_radius` instruction from the body and use an alternative tool that is already in the allowlist.

---

### Item 4: spawn_allowlist Declared for Agents Spawning Sub-Agents

**What to check:** If the agent body contains any instruction that invokes the `Agent` tool (i.e. spawns a sub-agent), the template MUST have a `spawn_allowlist` in its registry entry OR a `## Your Available Sub-Agents` (or `## Spawn Allowlist`) section in the body listing the permitted sub-agents.

**Detection heuristics:**

- Body contains text like "dispatch to X via the `Agent` tool", "spawn X", or "invoke the `Agent` tool with input `{...}`".
- Check `config/agent_registry.json` for the agent's `spawn_allowlist` field.
- If body invokes Agent tool AND spawn_allowlist is absent or empty → violation.

**Violation example:**

```markdown
## Dispatch
Dispatch `reference-author` via the `Agent` tool with the following spec block:
```
# Agent template has no ## Your Available Sub-Agents section and
# spawn_allowlist: [] in the registry → violation.
```

**Correct form:**

```yaml
# In config/agent_registry.json:
{
  "id": "my-agent",
  "spawn_allowlist": ["reference-author"]
}
```

```markdown
## Your Available Sub-Agents

| Agent | Role | When to dispatch |
|---|---|---|
| `reference-author` | Lookup doc author | When the request is a schema or API reference |
```

---

### Item 5: Signoff Protocol Section Present for `signoff: true` Agents

**What to check:** If the agent template has `signoff: true` in its frontmatter, the body MUST include a `## Sign-off` section (or equivalent heading) that references the signoff skill (`signoff` SKILL.md §2 and §4 for the success and failure paths respectively).

**Detection heuristics:**

- Frontmatter `signoff: true` is set.
- Search body for heading matching `## Sign-off` (case-insensitive, with or without hyphen).
- If `signoff: true` AND no `## Sign-off` heading → violation.

**Violation example:**

```yaml
# Frontmatter
signoff: true
```

```markdown
# Body (entire content)
## Pre-Flight Reads
...
## Implementation
...
## Constraints
...
```
# → Violation: signoff: true but no ## Sign-off section.
```

**Correct form:**

```markdown
## Sign-off (when ticket_path is provided)

If you were invoked with a `ticket_path` argument:
1. Load `.claude/skills/signoff/SKILL.md`.
2. On success: follow the atomic sign-off recipe for your agent name.
3. On failure: follow the failed-path recipe; set status to `failed` and append a `blocker` comment.
4. Skip this section entirely if no `ticket_path` was provided.
```

---

### Item 6: Stop-and-Ask Rules Present for Scope Boundaries

**What to check:** Every agent template MUST have a `## Stop-and-Ask Rule` (or equivalent: `## Constraints`, `## When to Stop`, `## Scope Boundaries`) section that explicitly names what work the agent must defer to another agent or to the user. This prevents the agent from autonomously editing files it should not touch.

**Detection heuristics:**

- Search body for any heading matching `## Stop-and-Ask`, `## Constraints`, `## When to Defer`, or `## Scope Boundaries`.
- If no such section is found → violation.
- If the section exists but is empty or only says "do not do bad things" without naming specific files or agents → weak violation (should be flagged with a warning).

**Violation example (no section at all):**

```markdown
## Pre-Flight Reads
...
## Implementation
...
## Sign-off
...
```
# → Violation: no Stop-and-Ask section. The agent has no defined scope boundary.
```

**Violation example (weak section):**

```markdown
## Constraints
- Be careful.
- Don't edit important files.
```
# → Weak violation: no specific files or agents named.
```

**Correct form:**

```markdown
## Stop-and-Ask Rule

The `my-agent` agent MUST defer certain work to other agents or to the user:

**Defer to `workflow-architect`:**
- Any edit to `config/agent_registry.json`
- Any edit to the build pipeline (`scripts/build.py`)

**Stop and ask the user when:**
- The ticket's acceptance criteria are ambiguous about the expected output format.
- You are about to delete an existing file (destructive write).
- The ticket requires a new MCP tool not in the project's approved tool set.
```

---

## Cross-References

| Document | Relevance |
|---|---|
| `CLAUDE.md` | Shell convention — mandatory single-command rule, absolute path rule, git -C rule |
| `docs/agents/conventions.md` | Full agent authoring conventions including frontmatter schema, tool tier floors, visibility classes |
| `templates/skills/signoff/SKILL.md` | Canonical signoff protocol (§1 status enum, §2 atomic recipe, §3 comment-append, §4 failed path, §5 validator rules) |
| `templates/skills/building-epics/SKILL.md` | Ticket-supervisor dispatch loop, failure adjudication, retry caps, commit-phase lock |
| `config/agent_registry.json` | Single source of truth for agent IDs, spawn_allowlist, spawned_by, is_ticket_phase |
| `docs/agents/README.md §PROJECT_CONTEXT Injection` | Runtime-discovery convention for PROJECT_CONTEXT.md files |
| `docs/architecture/adrs/ADR-006-agent-model-tiers.md` | Policy source for model tier selection, tool allowlists, nesting depth cap |
