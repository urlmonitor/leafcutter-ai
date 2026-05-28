---
title: "How to create a skill"
type: how-to
status: active
created: 2026-05-28
last_updated: 2026-05-28
components:
  - build_pipeline
related_docs:
  - templates/skills/README.md
  - config/skill_registry.json
  - scripts/build.py
  - templates/skills/add-skill-to-package/SKILL.md
---

# How to create a skill

A **skill** is a reusable instruction document that Claude agents load via `Read` and then follow. Skills encode repeatable procedures — the `signoff` skill, the `building-epics` runbook, the `precommit-autofix` loop — that many agents may share. This guide walks you through creating a new skill end-to-end: authoring, registering, deploying, and (optionally) promoting it into the package.

## Prerequisites

- The leafcutter package is installed in your project (`build.py` has run at least once).
- You have write access to `templates/skills/` and `config/skill_registry.json`.
- You know what procedure the skill will encode and which agents will use it.

---

## Step 1 — Choose a skill name

Skill names are **kebab-case**. Pick a name that reads as a verb phrase or a noun phrase describing the procedure:

| Good | Avoid |
|------|-------|
| `signoff` | `SignOff`, `sign_off` |
| `building-epics` | `buildEpics`, `build_epics` |
| `precommit-autofix` | `PrecommitAutofix` |
| `route-learning` | `routeLearning` |

The name must be unique across `templates/skills/`. Check before creating:

```bash
ls templates/skills/
```

---

## Step 2 — Create the skill directory

```bash
mkdir -p templates/skills/<skill-name>
```

Every skill lives at `templates/skills/<skill-name>/SKILL.md`. Supporting scripts may live alongside it (see Step 5).

---

## Step 3 — Write `SKILL.md` with required frontmatter

Create `templates/skills/<skill-name>/SKILL.md`. The file **must** open with a YAML frontmatter block:

```yaml
---
name: <skill-name>
description: >
  One sentence describing what this skill does and when an agent should
  load it. Keep it under 120 characters so it fits cleanly in registry
  listings and agent prompts.
allowed-tools: Read, Edit, Write, Bash(git add *)
---
```

### Frontmatter field reference

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `name` | yes | string | Must exactly match the folder name (kebab-case). |
| `description` | yes | string | One sentence; used in registry and agent discovery. |
| `allowed-tools` | yes | string | Comma-separated list of Claude tools the skill's instructions use. See below. |
| `internal` | no | boolean | Set `true` to prevent the skill from being copied to adopter projects during `build.py`. Defaults to `false` (portable). |

### `allowed-tools` values

List only the tools that the **agent following this skill** will actually call. Common values:

- `Read` — reading files
- `Edit` — in-place file edits
- `Write` — creating new files
- `Bash(git add *)` — git staging
- `Bash(python *)` — running Python scripts
- `Bash(ls *)` — directory listing
- `Glob`, `Grep` — file search (use sparingly; prefer dedicated tools)

**Example for a documentation-only skill:**

```yaml
allowed-tools: Read, Edit, Write
```

**Example for a skill that runs build scripts:**

```yaml
allowed-tools: Read, Edit, Write, Bash(python *), Bash(ls *)
```

### `internal: true` flag

Skills with `internal: true` are part of the package machinery itself (e.g. `build-single-ticket`, `building-epics`). They are **not** copied to adopter projects when `build.py` runs with `--target-dir <adopter>`. Use this for supervisor runbooks, internal orchestration skills, and any skill that references leafcutter-internal paths.

If your skill is meant to help developers in any project (e.g. `precommit-autofix`, `signoff`), leave `internal` absent or set it to `false`.

---

## Step 4 — Write the skill body

After the frontmatter, write the skill procedure in Markdown. A well-structured skill body contains:

1. **One-paragraph overview** — what the skill does and who calls it.
2. **Inputs** (if the skill accepts parameters) — a Markdown table of field → required → description.
3. **Numbered procedure steps** — each step is a heading (`## Step N`) with clear, imperative instructions.
4. **Code blocks** for every command or file excerpt the agent must use verbatim.
5. **Invariants / anti-patterns** section — things the agent must never do.

**Minimal example:**

```markdown
---
name: my-skill
description: Append a timestamped entry to a changelog file.
allowed-tools: Read, Edit
---

# my-skill

Appends one structured entry to `CHANGELOG.md` using a consistent format.
Called by `changelog-agent` after every commit.

## Inputs

| Field | Required | Description |
|-------|----------|-------------|
| `entry_text` | yes | One sentence describing the change. |
| `ticket_ref` | no | Ticket ID, e.g. `EPIC-Foo/03`. |

## Step 1 — Read the current changelog

Read `CHANGELOG.md`. Locate the `## Unreleased` section.

## Step 2 — Append the entry

Use `Edit` to append under `## Unreleased`:

    - <entry_text> (<ticket_ref if provided>)

## Invariants

- Never delete existing entries.
- Always place the new entry at the **top** of the `## Unreleased` list.
```

---

## Step 5 — Add an optional `scripts/` subdirectory

If your skill invokes helper scripts (Python utilities, shell tools), place them in a `scripts/` subdirectory next to `SKILL.md`:

```
templates/skills/<skill-name>/
    SKILL.md
    scripts/
        my_helper.py
        validate_something.sh
```

`build.py` copies the entire skill directory — including `scripts/` — to `.claude/skills/<skill-name>/` in the target project. Reference scripts in `SKILL.md` using a path relative to the compiled location:

```bash
python .claude/skills/<skill-name>/scripts/my_helper.py
```

Scripts must be self-contained: no imports from project-specific modules, no hardcoded project paths. If a script must reference project context, accept it as a CLI argument.

---

## Step 6 — Register in `config/skill_registry.json`

Open `config/skill_registry.json` and add an entry to the `"skills"` array:

```json
{
  "id": "<skill-name>",
  "name": "<Human Readable Name>",
  "portable": true,
  "domain": null,
  "template_path": "leafcutter/templates/skills/<skill-name>/",
  "dependencies": []
}
```

### Registry field reference

| Field | Required | Notes |
|-------|----------|-------|
| `id` | yes | Must match the folder name exactly (kebab-case). |
| `name` | yes | Human-readable name shown in listings. |
| `portable` | yes | Always `true` for skills. |
| `domain` | no | Set to a domain string (e.g. `"sql"`) for domain-specific skills; `null` for cross-cutting ones. |
| `template_path` | yes | Path from the repo root to the skill folder, with trailing slash. |
| `internal` | no | Set `true` if the skill is internal (matches the `internal` flag in frontmatter). |
| `dependencies` | yes | Array of skill IDs this skill depends on. Use `[]` if none. |

**Important:** forgetting to add the registry entry is the most common mistake. The `build.py --validate-only` check will surface missing or malformed entries (see Step 7).

---

## Step 7 — Run `build.py` and verify deployment

### 7a — Validate the registry

```bash
python scripts/build.py --validate-only
```

This checks all entries in `skill_registry.json` for schema compliance. Fix any errors before proceeding.

### 7b — Deploy to `.claude/skills/`

```bash
python scripts/build.py --target-dir .
```

This copies `templates/skills/<skill-name>/` to `.claude/skills/<skill-name>/` in the current project.

### 7c — Verify the compiled skill exists

```bash
ls .claude/skills/<skill-name>/
# Expected: SKILL.md  (plus scripts/ if you added one)
```

If `.claude/skills/<skill-name>/SKILL.md` is absent, check that:

- The `template_path` in the registry points to the correct folder.
- You ran `build.py` without `--validate-only`.
- There were no errors in the `build.py` output.

---

## Step 8 — Promote to the package (optional)

If you want the skill to be available in **every project** that installs leafcutter (not just the current one), promote it using the `add-skill-to-package` skill. Invoke it from within an agent session:

```
Load .claude/skills/add-skill-to-package/SKILL.md
skill_name: <skill-name>
description: <same one-sentence description from frontmatter>
```

The skill will:

1. Check idempotency (fails if the template already exists).
2. Inspect the source for project-specific content and ask for confirmation.
3. Copy the directory to `leafcutter/templates/skills/<skill-name>/`.
4. Update `leafcutter/README.md` with the skill listing.
5. Run `build.py --validate-only` to confirm integration.

After promotion, other projects that run `build.py` will receive the skill automatically.

---

## Verification

After completing Steps 1–7, run this checklist to confirm everything is wired correctly:

```bash
# 1. Skill directory and SKILL.md exist in templates
ls templates/skills/<skill-name>/SKILL.md

# 2. Registry entry is present
python3 -c "
import json
data = json.load(open('config/skill_registry.json'))
ids = [s['id'] for s in data.get('skills', [])]
print('<skill-name> in registry:', '<skill-name>' in ids)
"

# 3. Compiled skill exists in .claude/skills/
ls .claude/skills/<skill-name>/SKILL.md

# 4. Validate registry schema
python scripts/build.py --validate-only
```

Expected output for each check:

1. `templates/skills/<skill-name>/SKILL.md` — file listed.
2. `<skill-name> in registry: True`
3. `.claude/skills/<skill-name>/SKILL.md` — file listed.
4. `validate-only` exits 0 with no errors.

If step 3 fails but step 1 and 2 pass, re-run `python scripts/build.py --target-dir .` to refresh the deployment.

---

## Common Mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Missing `allowed-tools` in frontmatter | Agent loads the skill but cannot call the tools it lists — hooks may reject tool calls | Add `allowed-tools:` to frontmatter with the correct tool list |
| Forgetting the registry entry | Skill deploys manually but is invisible to `build.py` automation and `business-analyst` agent selection | Add entry to `config/skill_registry.json` with correct `id` and `template_path` |
| Wrong `internal` value | Skill is either absent from adopter projects (set `true` when it should be `false`) or leaks package machinery into adopter projects (set `false` when it should be `true`) | Match the `internal` flag in both frontmatter and registry; omit it for portable cross-cutting skills |
| `name` frontmatter doesn't match folder name | `build.py --validate-only` reports a name mismatch error | Set `name:` in frontmatter to exactly match the folder name |
| Scripts outside `scripts/` subdirectory | Helper scripts are not copied to target project by `build.py` | Move helpers into `templates/skills/<skill-name>/scripts/` |
| Project-specific imports in `scripts/` | Skill breaks in adopter projects that don't have those modules | Remove project-specific imports; accept project context via CLI arguments |

---

## See Also

- [`templates/skills/README.md`](../../templates/skills/README.md) — SKILL.md frontmatter schema reference and naming conventions
- [`config/skill_registry.json`](../../config/skill_registry.json) — registry of all skills with `id`, `portable`, `internal`, and `dependencies`
- [`templates/skills/add-skill-to-package/SKILL.md`](../../templates/skills/add-skill-to-package/SKILL.md) — step-by-step promotion workflow
- [`scripts/build.py`](../../scripts/build.py) — deploys skill templates to `.claude/skills/`
