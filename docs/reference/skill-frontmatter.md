---
title: 'Reference: SKILL.md Frontmatter Fields'
type: reference
status: active
created: 2026-05-28
last_updated: 2026-05-28
components:
- build_pipeline
- config_loader
related_docs:
- leafcutter-ai/config/skill_registry.json
- leafcutter-ai/config/skill_registry.schema.json
- leafcutter-ai/templates/skills/
description: 'Overview of Reference: SKILL.md Frontmatter Fields.'
---
# Reference: SKILL.md Frontmatter Fields

Every skill in the leafcutter ecosystem is defined by a `SKILL.md` file. The
file begins with a YAML frontmatter block that controls how the skill is
loaded, deployed, and presented to agents. This reference covers every valid
frontmatter field, its type, required/optional status, valid values, and its
effect on the build pipeline and agent runtime.

**Source of truth**: `config/skill_registry.json` (registry-side schema) and
`templates/skills/*/SKILL.md` (concrete examples). When the two diverge, the
registry wins for deploy decisions; the frontmatter wins for agent-runtime
behaviour.

---

## Frontmatter Fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | **yes** | — | Canonical skill identifier. Must match the directory name under `templates/skills/` and `.claude/skills/`. Used by agents to reference the skill and by `build.py` to locate its directory. Pattern: `^[a-z][a-z0-9-]*$`. |
| `description` | string | **yes** | — | Human-readable prose that tells an agent when to load this skill. Appears in `build.py`-generated summaries and agent auto-selection tables. Multi-line values must use the YAML block scalar (`>` or `|`). |
| `allowed-tools` | string or list | **yes** | — | Tool names the skill grants to the agent loading it. See [allowed-tools details](#allowed-tools-details) below. |
| `internal` | boolean | no | `false` | When `true`, the skill is for internal/runtime use only. `build.py` still copies it to `.claude/skills/` so agents can invoke it, but excludes it from user-facing skill listings and summary tables. When `false` (default), the skill is public and deployed to adopter projects. |
| `portable` | boolean | no | `true` | When `false`, marks the skill as domain-specific (not to be packaged for other projects). Rare: most skills should be portable. Set alongside `domain` in `skill_registry.json`. Note — this field is primarily a registry-side concern; it is not always present in the frontmatter itself. |
| `disable-model-invocation` | boolean | no | `false` | When `true`, signals that this skill drives only tool-call sequences (e.g. shell scripts) and should not trigger LLM generation. Used by the `ship` skill to prevent accidental model calls during a pure-scripted merge. |

---

## allowed-tools Details

The `allowed-tools` field declares which Claude tools the agent loading the skill
is permitted to use within that skill's context. Declaring a tool here grants
**permission** for that skill's use cases — it does not add capabilities the
model does not already have. Tools not listed are disallowed for that skill's
context.

### Valid tool name strings

| Tool | Description |
|---|---|
| `Read` | Read files from the filesystem. |
| `Edit` | Replace strings in existing files. |
| `Write` | Create or overwrite files. |
| `Bash` | Run arbitrary shell commands (broad; prefer constrained form). |
| `Bash(<pattern>)` | Run shell commands matching a glob/prefix pattern. Preferred over bare `Bash` — narrows the surface to only the commands the skill actually needs. |
| `Glob` | List files matching a pattern. |
| `Grep` | Search file contents. |
| `Agent` | Spawn a sub-agent. Required for any skill that dispatches phase agents (e.g. `building-epics`, `package-audit`). |

### Bash constrained forms (examples from the ecosystem)

| Declaration | Allows only |
|---|---|
| `Bash(git *)` | Any `git` subcommand. |
| `Bash(python *)` | Any `python` or `python3` invocation. |
| `Bash(ls *)` | Directory listings. |
| `Bash(cd *)` | Directory changes. |
| `Bash(cp *)` | File copies. |
| `Bash(mkdir *)` | Directory creation. |
| `Bash(poetry *)` | Poetry commands. |

### Format conventions for allowed-tools

**Flow style (single-line)** — use when the list is short and fits on one line:

```yaml
allowed-tools: Read, Edit, Bash(git *), Bash(python *)
```

**Block scalar list** — use when the list is long or requires one-per-line clarity:

```yaml
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
```

Both forms are accepted by the YAML parser. The flow style is more common in
this codebase; the block scalar form appears in skills that list many tools
(`security-scanner`, `sql-query-past-queries`). Choose whichever aids readability.

**Do not use** `allowed-tools: []` (empty list). If the skill requires no tools, it
should not exist as an agent-loadable skill. Omitting the field entirely is also
invalid — the field is required.

---

## The `internal` Flag

The `internal` flag controls visibility and deploy behaviour:

| Value | Effect on `build.py` | Effect on agent listings | Typical use cases |
|---|---|---|---|
| `false` (default) | Skill is copied to adopter projects under `.claude/skills/`. | Appears in user-facing skill summaries. | All general-purpose skills: `signoff`, `building-epics`, `create-hook`, etc. |
| `true` | Skill is still copied to `.claude/skills/` (agents need it at runtime). | **Excluded** from user-facing listings and generated summary tables. | Operational runbooks loaded by supervisors (`build-feature-ops-notes`, `build-single-ticket`) — they are internal implementation details, not user-invocable skills. |

**Effect on `add-skill-to-package`**: when you promote a skill from project-local
(`.claude/skills/`) to the leafcutter package (`templates/skills/`), `add-skill-to-package`
reads the `internal` flag to decide whether to add the skill to user-facing summaries
in `docs/skills/README.md`. Internal skills are registered in `skill_registry.json` but
not surfaced in the README.

---

## skill_registry.json Schema

`config/skill_registry.json` is the single source of truth for skill registration.
Each entry in the `skills` array describes one skill:

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | **yes** | Unique skill identifier. Must match `name` in the skill's frontmatter and the directory name under `templates/skills/`. Pattern: `^[a-z][a-z0-9-]*$`. |
| `name` | string | **yes** | Human-readable display name (Title Case). Used in documentation tables. |
| `portable` | boolean | **yes** | `true` = domain-agnostic; belongs in the package. `false` = domain-specific; stays in the originating project. |
| `domain` | string or null | **yes** | Domain tag (e.g. `"billing"`) for domain-specific skills. `null` for portable skills. |
| `template_path` | string | for portable | Relative path from the leafcutter workspace root to the skill's template directory. Format: `leafcutter/templates/skills/<id>/`. Present only when `portable: true`. |
| `dependencies` | array of string | **yes** | IDs of other skills this skill invokes at runtime. Used to build the skill dependency graph. May be `[]` when dependency mapping is non-trivial or when the skill has no runtime skill dependencies. |
| `internal` | boolean | no | Mirrors the frontmatter `internal` flag. When `true`, excludes the skill from user-facing summaries. |
| `description` | string | no | Optional human-readable description for use in summaries. When absent, `build.py` falls back to the frontmatter `description` field. |

### Relationship between frontmatter and registry

The frontmatter `name` field and the registry `id` field must be identical. The
frontmatter `internal` flag and the registry `internal` field should match — the
registry copy is the authoritative source for `build.py` deploy decisions; the
frontmatter copy is what the agent reads at runtime.

When you add a skill, update both the frontmatter and the registry entry together.
The `add-skill-to-package` skill handles this atomically when promoting a
project-local skill.

---

## Examples

### Minimal skill frontmatter

```yaml
---
name: my-skill
description: Use when doing X. Provides Y and Z.
allowed-tools: Read, Edit
---
```

Required fields only. `internal` defaults to `false` (public, deployed to adopters).

### Full skill frontmatter (all fields)

```yaml
---
name: my-internal-skill
description: >
  Operational runbook loaded by X and Y agents. Documents failure modes,
  recovery procedures, and the control-flow algorithm for the Z workflow.
  Not user-invocable directly.
allowed-tools: Read, Edit, Bash(git *), Bash(python *), Agent
internal: true
---
```

`internal: true` marks this as a runtime-only skill excluded from user-facing
summaries. The `>` YAML block scalar folds the multi-line description into a
single paragraph for display purposes.

---

## Format Conventions Summary

| Convention | Rule |
|---|---|
| `name` casing | Lowercase with hyphens. Never `CamelCase` or `snake_case`. |
| `description` quoting | Use `>` (fold) for multi-line prose that should display as one paragraph. Use `\|` (literal) for description text that contains intentional line breaks (e.g. bullet lists). Use inline string only for single-line descriptions under ~80 chars. |
| `allowed-tools` style | Flow (comma-separated) for short lists; block list for 5+ tools or when constrained `Bash(...)` forms need visual alignment. |
| `internal` | Omit the field entirely for public skills (the default is `false`). Only set explicitly when the value is `true`. |
| `portable` | This field belongs in `skill_registry.json`, not in the frontmatter. Do not duplicate it in frontmatter unless the skill explicitly opts out of packaging. |
| YAML delimiters | The frontmatter block MUST begin on line 1 with `---` and close with `---` before the first `#` heading. No blank line between the opening `---` and the first field. |
