---
title: "How to deprecate or remove an artifact"
description: "Step-by-step guide for safely deprecating or deleting agents, skills, hooks, and scripts from the leafcutter package without breaking consumer builds."
type: how_to
status: active
created: 2026-05-28
last_updated: 2026-05-28
components:
  - build_pipeline
  - config_loader
related_docs:
  - docs/how-to/creating-an-agent-template.md
  - docs/how-to/creating-a-skill.md
  - docs/how-to/managing-pre-commit-hooks.md
  - docs/how-to/creating-a-claude-code-hook.md
  - docs/build-pipeline.md
  - docs/agent-registry.md
---

# How to deprecate or remove an artifact

This guide covers the full lifecycle of the four artifact types in leafcutter when
you need to either **soft-deprecate** them (keep the source but signal it is
end-of-life) or **hard-delete** them (remove source files and all references
entirely).

> **Artifact types covered**
>
> 1. Agent templates
> 2. Skills
> 3. Claude Code hooks
> 4. Pre-commit hooks

See the reference docs at `docs/reference/` for the authoritative field inventories
for each type once tickets 06–08 ship. This guide is the procedural complement; the
reference docs are the field-by-field lookup.

---

## Universal checklist (all types)

Run through this checklist before touching any source file, regardless of artifact
type.

- [ ] **Tag or commit the current state** — create a git tag or note the current
  `HEAD` SHA so you can recover if the removal goes wrong.
- [ ] **Search for cross-references** — find every file that names or imports the
  artifact before you delete anything:
  ```bash
  git grep -rn "<artifact-name>"
  ```
  Review every match before proceeding.
- [ ] **Decide: deprecate or delete?** — if active consumers exist, prefer soft
  deprecation first (see §Deprecation below). Only delete when consumers are
  confirmed removed or migrated.
- [ ] **Update related docs** — remove or redirect any prose in `docs/` that
  references the artifact.
- [ ] **Verify with `build.py --clean`** — after deletion, run the build in clean
  mode to confirm no orphaned compiled artifacts remain in `.claude/`:
  ```bash
  python scripts/build.py --clean
  ```
  > **Note:** the `--clean` flag is introduced by ticket 12 of
  > EPIC-ArtifactCRUDClarity. Until that ticket ships, use
  > `python scripts/build.py --migrate` to identify stale output files and
  > remove them manually.
- [ ] **Verify with `git status`** — confirm no stale files remain unstaged or
  untracked.

---

## Agent templates

Agent templates live at `templates/agents/<name>.md` and compile to
`.claude/agents/<name>.md` in the target project.

### Deleting an agent template

1. **Delete the source file.**
   ```bash
   git rm templates/agents/<name>.md
   ```

2. **Remove the registry entry** from `config/agent_registry.json`.
   Find the object with `"id": "<name>"` and delete the entire block,
   including its trailing comma.

3. **Remove `spawned_by` references.** Other agents that list `<name>` in
   their `spawn_allowlist` or `spawned_by` arrays must be updated.
   Run `git grep -rn '"<name>"'` in `templates/agents/` and remove the
   relevant lines.

4. **Remove the reference doc** (if one exists):
   ```bash
   git rm docs/reference/<name>.md
   ```

5. **Remove slash-command workflow templates** (if one exists):
   ```bash
   git rm templates/workflows/<name>.md   # or wherever it lives
   ```

6. **Re-run the build** to clear the compiled artifact:
   ```bash
   python scripts/build.py
   ```
   After the build, confirm `.claude/agents/<name>.md` no longer exists.

7. **Validate the registry:**
   ```bash
   python scripts/build.py --validate-only
   ```

### Checklist — agent template deletion

- [ ] Source template deleted (`templates/agents/<name>.md`)
- [ ] `config/agent_registry.json` entry removed
- [ ] `spawned_by` / `spawn_allowlist` back-references cleaned in sibling templates
- [ ] Reference doc removed (`docs/reference/<name>.md`)
- [ ] Slash-command template removed (if one existed)
- [ ] Build passes; `.claude/agents/<name>.md` absent from output

---

## Skills

Skills live at `templates/skills/<name>/` (a directory, not a single file) and
compile to `.claude/skills/<name>/` in the target project.

### Deleting a skill

1. **Delete the source directory.**
   ```bash
   git rm -r templates/skills/<name>/
   ```

2. **Remove the registry entry** from `config/skill_registry.json`.
   Find the object with `"id": "<name>"` and delete the entire block.

3. **Search for references in agent templates and other skills.** Skills are
   referenced by agents via the `skills_used` field in
   `config/agent_registry.json` and by direct `# <name>` heading checks or
   `add-skill-to-package` mentions in skill bodies. Clean all of these:
   ```bash
   git grep -rn '"<name>"' config/
   git grep -rn '<name>'   templates/
   ```

4. **Re-run the build** to clear the compiled artifact:
   ```bash
   python scripts/build.py
   ```
   After the build, confirm `.claude/skills/<name>/` no longer exists.

5. **Validate the registry:**
   ```bash
   python scripts/build.py --validate-only
   ```

### Checklist — skill deletion

- [ ] Source directory deleted (`templates/skills/<name>/`)
- [ ] `config/skill_registry.json` entry removed
- [ ] `skills_used` references removed from `config/agent_registry.json`
- [ ] In-template `add-skill-to-package` or prose references cleaned
- [ ] Build passes; `.claude/skills/<name>/` absent from output

---

## Claude Code hooks

Claude Code hooks are Python scripts triggered by Claude tool events
(PreToolUse, PostToolUse, etc.). They live at `templates/hooks/<name>.py`
and are registered in `templates/settings.json`.

> **Do not confuse these with pre-commit hooks.** Claude Code hooks fire during
> Claude agent sessions; pre-commit hooks fire on `git commit`. See
> `docs/how-to/creating-a-claude-code-hook.md` for the full context.

### Deleting a Claude Code hook

1. **Delete the source file.**
   ```bash
   git rm templates/hooks/<name>.py
   ```

2. **Remove the registration entry** from `templates/settings.json`. Find the
   block in `hooks.PreToolUse` or `hooks.PostToolUse` (whichever applies) whose
   `command` field invokes `<name>.py` and delete the entire entry block.
   Example — remove this object from the relevant array:
   ```json
   {
     "type": "command",
     "command": "bash -c '... python \"$d/.claude/hooks/<name>.py\"'",
     "timeout": 10
   }
   ```

3. **Re-run the build** to clear the deployed hook:
   ```bash
   python scripts/build.py
   ```
   After the build, confirm `.claude/hooks/<name>.py` is absent and the
   relevant entry is gone from `.claude/settings.json`.

4. **Check that no agent template references the hook by name** in prose or
   in agent instructions:
   ```bash
   git grep -rn '<name>' templates/agents/
   ```

### Checklist — Claude Code hook deletion

- [ ] Source file deleted (`templates/hooks/<name>.py`)
- [ ] Registration entry removed from `templates/settings.json`
- [ ] Build passes; `.claude/hooks/<name>.py` and its `settings.json` entry absent
- [ ] No agent template prose references the hook by name

---

## Pre-commit hooks

Pre-commit hooks are Python scripts in
`templates/scripts/commit_guardian/<name>.py`, registered in
`templates/scripts/commit_guardian/commit_guardian.json` and wired up in
`.pre-commit-config.yaml`.

> **Historical note.** An earlier directory `templates/commit-guardian/` was
> deprecated in EPIC-PortableInstallHardening T03 (2026-05-18) and fully
> removed in TICKET-20260618-RemoveDeprecatedCommitGuardianTree. The canonical
> location is `templates/scripts/commit_guardian/`. This real-world deprecation
> is the motivating example for the deprecation pattern described in §Deprecation
> below.

### Deleting a pre-commit hook

1. **Delete the source file.**
   ```bash
   git rm templates/scripts/commit_guardian/<name>.py
   ```

2. **Remove the config block** from
   `templates/scripts/commit_guardian/commit_guardian.json`.
   Find the top-level key that governs this hook (e.g. `"my_check": { ... }`)
   and delete the entire block.

3. **Remove the `config.py` constants.** Open
   `templates/scripts/commit_guardian/config.py` and delete the constants that
   read from the removed JSON key.

4. **Remove the hook entry** from `.pre-commit-config.yaml`. Find the `id:
   check-<name>` entry under the `local` repo's `hooks:` list and delete the
   entire block. Append a `DECISION HISTORY` comment noting the removal date,
   author, and ticket.

5. **Re-run the build:**
   ```bash
   python scripts/build.py
   ```
   Confirm `scripts/commit_guardian/<name>.py` is absent in the target and
   the hook no longer appears in the installed `.pre-commit-config.yaml`.

6. **Reinstall the pre-commit hooks** to propagate the removal to the git hook:
   ```bash
   pre-commit install
   pre-commit install --hook-type post-commit
   ```

### Checklist — pre-commit hook deletion

- [ ] Source script deleted (`templates/scripts/commit_guardian/<name>.py`)
- [ ] Config block removed from `commit_guardian.json`
- [ ] Constants removed from `config.py`
- [ ] `.pre-commit-config.yaml` entry removed and DECISION HISTORY updated
- [ ] Build passes; hook absent from target
- [ ] `pre-commit install` re-run to propagate to git hook

---

## Deprecation (soft removal — all types)

Deprecation signals that an artifact is end-of-life **without deleting it**. Use
deprecation when consumers still exist and you need a migration window.

### Step 1 — Add a registry flag

In the relevant registry file (`agent_registry.json` or `skill_registry.json`),
add a `"_deprecated": true` field to the artifact's entry and a
`"_deprecated_since"` field with the date and the replacing artifact (if any):

```json
{
  "id": "old-agent",
  "_deprecated": true,
  "_deprecated_since": "2026-05-28",
  "_replaced_by": "new-agent",
  ...
}
```

For Claude Code hooks and pre-commit hooks (which have no central registry JSON
entry per hook), add a `DEPRECATED` comment in the hook configuration file
(`settings.json` or `commit_guardian.json`) next to the entry.

### Step 2 — Add a deprecation comment to the source file

For agent templates and skills, add a YAML comment at the top of the source file
(inside the frontmatter or just below it) and a prose notice at the top of the
body:

```
<!-- DEPRECATED: This artifact is deprecated as of YYYY-MM-DD.
     Use <replacement-name> instead. This file will be removed in a future release. -->
```

For pre-commit hook scripts, add a module-level comment and a `DeprecationWarning`
to the script body that prints a warning when the hook runs:

```python
# DEPRECATED: This hook is deprecated as of YYYY-MM-DD. Use check_new_thing.py instead.
import warnings
warnings.warn("check_old_thing.py is deprecated; use check_new_thing.py.", DeprecationWarning)
```

### Step 3 — Update cross-references

Redirect any documentation or cross-reference that points to the deprecated
artifact:

- In agent templates: update `spawned_by` and `spawn_allowlist` to point to the
  replacement.
- In skill bodies: update `add-skill-to-package` or skills-used references.
- In docs: add a redirect note at the top of any existing doc:
  ```
  > **Redirected.** This page covers the deprecated `<name>` artifact. See
  > `docs/how-to/<new-name>.md` for the current guidance.
  ```

### Step 4 — Do NOT delete the source file yet

Leave the source file in place until all consumers have migrated. Track
outstanding consumers in a ticket or in the registry's `"_migration_notes"`
field. Only run the hard-delete checklist (see the relevant section above) once
all consumers are confirmed migrated.

### Real example — `templates/commit-guardian/` deprecation

This epic's own context provides a concrete illustration. The directory
`templates/commit-guardian/` was deprecated in favour of
`templates/scripts/commit_guardian/` during EPIC-PortableInstallHardening T03
(2026-05-18). The deprecation followed this exact pattern:

1. A `DEPRECATED.md` file was added to `templates/commit-guardian/` explaining the
   new canonical path.
2. The build pipeline was updated to read from the canonical path first, with a
   fallback for backward compatibility.
3. The old directory was left in place until all projects had re-run `build.py`.
4. A `create-hook` bug that still referenced the deprecated path was fixed in
   ticket 10 of this epic.

The lesson: a well-executed deprecation gives consumers time to migrate without
breaking their workflows.

---

## Verification quick-reference

| Action | Command |
|--------|---------|
| Find all references to an artifact | `git grep -rn '<artifact-name>'` |
| Validate registries after changes | `python scripts/build.py --validate-only` |
| Rebuild compiled output | `python scripts/build.py` |
| Identify stale output files (pre-ticket-12) | `python scripts/build.py --migrate` |
| Remove stale output files (ticket-12+) | `python scripts/build.py --clean` |
| Verify no orphaned `.claude/` files remain | `git status --short` |
| Reinstall pre-commit hooks after removal | `pre-commit install && pre-commit install --hook-type post-commit` |
| Run full hook suite manually | `pre-commit run --all-files` |
