---
name: add-skill-to-package
description: >
  Promote a project-local skill into the leafcutter package atomically.
  Copies the entire skill directory (SKILL.md + scripts/) to templates/skills/,
  verifies the skill frontmatter is portable, and runs build.py to confirm
  integration. Invoked by workflow-architect.
allowed-tools: Read, Edit, Write, Bash(git add *), Bash(python *), Bash(ls *), Bash(cp *)
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

## Step 4 — Register in skill_registry.json

Open `leafcutter/config/skill_registry.json` and append a new entry to the
`"skills"` array:

```json
{
  "id": "<skill-name>",
  "description": "<one-line description from SKILL.md frontmatter>",
  "path": "templates/skills/<skill-name>/SKILL.md",
  "internal": false
}
```

- `"id"` must match the `skill_name` input exactly (kebab-case).
- `"description"` must be a non-empty string copied from the `description:` field
  in the skill's SKILL.md frontmatter (single line, no trailing newline).
- `"path"` must be the relative path to the SKILL.md file inside the templates
  directory (always `templates/skills/<skill-name>/SKILL.md`).
- Set `"internal": true` if the skill is a leafcutter-internal workflow artifact
  that should NOT be copied into adopter projects during `build.py`. Set to
  `false` for user-facing skills that adopter projects need.

Use `Edit` (never `Write`) when modifying `skill_registry.json` — Write would
overwrite the entire file and erase all other entries.

## Step 5 — Update leafcutter/README.md

Use Edit (never Write) to add the new skill to the "Generic-Portable Skills" section
of `leafcutter/README.md`. Anchor on an adjacent row:

```
- Lifecycle: ... `<skill_name>`
```

Place it in the appropriate category (Lifecycle, Code quality, Commit, etc.).
If no category fits, add it to the most relevant existing category.

## Step 6 — Run build.py and validate

1. Run `python leafcutter/scripts/build.py --validate-only` — must pass.
2. Run `python leafcutter/scripts/build.py --target-dir . --force` to compile
   the template to `.claude/skills/<skill_name>/SKILL.md`.
3. Confirm `.claude/skills/<skill_name>/SKILL.md` was (re)generated from the template.

## Step 7 — Update workflow-architect skills_used (if applicable)

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
- Use Edit (not Write) for `skill_registry.json` — Write would erase all existing entries.
- ALWAYS verify `skill_registry.json` contains an entry for the promoted skill after Step 4.
- The skill bootstraps itself: once promoted, `add-skill-to-package` itself lives at
  `leafcutter/templates/skills/add-skill-to-package/SKILL.md`.
