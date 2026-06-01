# .claude/skills/

## Purpose

This directory contains skill definitions — reusable instruction sets that agents load via `Read` and then follow. A skill is a how-to document written for Claude agents, not for human developers. Skills encode repeatable procedures that multiple agents may need: the `signoff` skill, the `route-learning` decision tree, the `capture-learning` write executor, etc.

## SKILL.md Frontmatter Schema

Every skill is a folder with a `SKILL.md` inside:

```
.claude/skills/<name>/SKILL.md
```

The SKILL.md must have a YAML frontmatter block:

```yaml
---
name: skill-name
description: "One sentence describing what this skill does and when to use it."
allowed-tools: Read, Edit, Write   # Tools this skill's instructions use.
---
```

## Naming Conventions

- Skill folder names are **kebab-case**: `route-learning/`, `capture-learning/`, `signoff/`, `building-epics/`.
- The `name` frontmatter field should match the folder name.
- Supporting files (JSON configs, schema files) live alongside `SKILL.md` in the same folder.

## Invocation Pattern

Agents load a skill by reading the SKILL.md file and then following the instructions within it. Example:

```
Load `.claude/skills/route-learning/SKILL.md` and apply the decision tree to classify the learning.
```

Skills do NOT spawn sub-agents or use tools themselves — they are instruction documents. The invoking agent uses the allowed tools listed in `allowed-tools`.

## Cross-cutting vs. Module-local Skills

- **Cross-cutting skills** are used by multiple agents and encode project-wide procedures (`signoff`, `building-epics`, `route-learning`, `capture-learning`).
- **Module-local skills** are used only within a specific workflow (`feature`, `close-worktree`, `precommit-autofix`).

## How to add a new skill

1. Create `.claude/skills/<name>/` directory.
2. Create `.claude/skills/<name>/SKILL.md` with the frontmatter schema above.
3. Add any supporting config or schema files to the same folder.
4. Document the skill in `docs/agents/README.md` (or the relevant agent documentation).
5. Update this README if the skill introduces a new naming convention or pattern.

## Critical Context

- Do NOT list every skill in this README — the list has high churn. Browse the directory directly.
- The `readme_read_guard.py` hook enforces that this README is read before any Edit/Write in `.claude/skills/`.
- Skills are canonical: phase agents must NOT modify `SKILL.md` files. Only the skill author edits them.
- Agents are in `.claude/agents/` (separate directory with its own README).
