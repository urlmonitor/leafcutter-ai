---
allowed-tools: Read, Edit, Write, Bash(git add *), Bash(python *), Bash(ls *), Bash(cp
  *)
description: 'Promote a project-local skill into the leafcutter package atomically.
  Copies the entire skill directory (SKILL.md + scripts/) to templates/skills/, verifies
  the skill frontmatter is portable, and runs build.py to confirm integration. Invoked
  by workflow-architect.

  '
name: add-skill-to-package
---

# add-skill-to-package

Promote a project-local skill into the leafcutter package completely and
atomically. No partial promotions.

## Inputs

| Field | Required | Description |
|-------|----------|-------------|
| `skill_name` | yes | Skill directory name, e.g. `create-ticket` (matches `.claude/skills/<skill_name>/`) |
| `description` | yes | One-sentence description of what the skill does |
| `source_path` | no | Override source path (default: `.claude/skills/<skill_name>/`) |

## Step 1 — Idempotency check

Before writing anything:

1. Confirm `leafcutter/templates/skills/<skill_name>/` does NOT exist.
   If it does, stop with: "Skill `<skill_name>` already has a template directory. Delete it first if you intend to replace it."

## Step 2 — Read and inspect the source skill

Read `.claude/skills/<skill_name>/SKILL.md` (or `<source_path>/SKILL.md`).

Check the YAML frontmatter for:
- `name:` field — must match `skill_name`
- Domain-specific content in the body — flag any references to project-specific paths,
  domain terminology, or hardcoded values that should be parameterised before promotion

Report any domain-specific content to the caller and ask for confirmation before proceeding.

## Step 3 — Copy the skill directory to templates

Create `leafcutter/templates/skills/<skill_name>/` and copy all files from
the source skill directory:

1. Copy `SKILL.md` with any required changes:
   - Ensure the `description:` in frontmatter matches the `description` input
   - Remove or parameterise any project-specific paths

2. If a `scripts/` subdirectory exists, copy it verbatim:
   ```
   leafcutter/templates/skills/<skill_name>/scripts/
   ```
   These scripts are copied as-is to the target project by `build.py`.

## Step 4 — Update leafcutter/README.md

Use Edit (never Write) to add the new skill to the "Generic-Portable Skills" section
of `leafcutter/README.md`. Anchor on an adjacent row:

```
- Lifecycle: ... `<skill_name>`
```

Place it in the appropriate category (Lifecycle, Code quality, Commit, etc.).
If no category fits, add it to the most relevant existing category.

## Step 5 — Run build.py and validate

1. Run `python leafcutter/scripts/build.py --validate-only` — must pass.
2. Run `python leafcutter/scripts/build.py --target-dir . --force` to compile
   the template to `.claude/skills/<skill_name>/SKILL.md`.
3. Confirm `.claude/skills/<skill_name>/SKILL.md` was (re)generated from the template.

## Step 6 — Update workflow-architect skills_used (if applicable)

If `workflow-architect` is the primary caller of this skill, update `skills_used` in
`leafcutter/config/agent_registry.json`:

```json
"skills_used": [..., "<skill_name>"]
```

Run `build.py --validate-only` again to confirm.

## Invariants

- NEVER overwrite an existing template directory (idempotency check in Step 1).
- Report domain-specific content before copying (Step 2) — never silently carry over
  project-specific paths into the portable package.
- ALWAYS run `build.py --validate-only` after editing templates.
- Use Edit (not Write) for `leafcutter/README.md`.
- The skill bootstraps itself: once promoted, `add-skill-to-package` itself lives at
  `leafcutter/templates/skills/add-skill-to-package/SKILL.md`.
