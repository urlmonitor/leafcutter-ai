---
title: "How to supply a project ability to a package specialist"
description: "Give a package specialist (for example sql-coder) an ability of your own by placing it under .leafcutter/skills/<id>/, when its grant is marked provided_by: project."
type: how-to
status: active
created: 2026-10-20
last_updated: 2026-10-20
components:
  - agent_registry
  - skills_system
related_docs:
  - docs/how-to/creating-a-skill.md
  - docs/reference/agent-template-frontmatter.md
  - docs/known-issues/build-pipeline/open-high-ki-bp-009.md
related_code:
  - scripts/project_ability_slots.py
  - scripts/agent_ability_verdict.py
  - scripts/agent_ability_gate.py
  - scripts/agent_skills_declaration.py
  - templates/agents/sql-coder.md
---

# How to supply a project ability to a package specialist

Put your own ability (a skill) where a package specialist expects to find it, so the specialist uses it, and the build stops telling you it is missing.

## Prerequisites

- The package is cloned at `leafcutter-ai/` in your project and you run commands from the project root.
- The specialist's grant is marked `provided_by: project` in its own frontmatter. The package's `sql-coder` marks `postgres` and `sql-test` this way, and the guide uses them:

  ```yaml
  skills:
  - skill_id: postgres
    mode: conditional
    condition: For every new SQL file or non-trivial edit (Step 2), apply the postgres skill before declaring the SQL ready.
    provided_by: project
  ```

  An unmarked grant is looked up only among the package's own skills. If the package does not ship that ability, the build stops with an error, and a copy under `.leafcutter/skills` is never consulted. Mark the grant first.

## Steps

### Step 1 - Build and read the line you will see

```bash
python leafcutter-ai/scripts/build.py --target-dir .
```

The build succeeds. For each marked grant nobody supplies it prints one informational line (no `[WARNING]` or `[ERROR]`, nothing fails). Each line carries the full path of the missing ability after the part quoted here:

```text
[abilities] agent 'sql-coder' is granted the project-supplied ability 'postgres': looked in the project's skills area
[abilities] agent 'sql-coder' is granted the project-supplied ability 'sql-test': looked in the project's skills area
```

Each continues with `<project>/.leafcutter/skills/<id> and it was not found there, so it is not installed in this project`. The compiled `sql-coder` prompt matches: no table row for the ability, and the line "The project-supplied ability `postgres` is not installed in this project."

### Step 2 - Add the ability under `.leafcutter/skills/<id>/`

Create `.leafcutter/skills/<id>/SKILL.md` for each ability, with `name` and `description` in its frontmatter. This is the only place the build looks. This command writes both:

```bash
python -c "import pathlib; [(pathlib.Path('.leafcutter/skills/' + i).mkdir(parents=True, exist_ok=True), pathlib.Path('.leafcutter/skills/' + i + '/SKILL.md').write_text('---\nname: ' + i + '\ndescription: Our ' + i + ' conventions\n---\n\nOur ' + i + ' conventions.\n', encoding='utf-8')) for i in ('postgres', 'sql-test')]"
```

For a real ability, write the body of your own conventions instead of the placeholder text (see [How to create a skill](creating-a-skill.md)).

### Step 3 - Rebuild

```bash
python leafcutter-ai/scripts/build.py --target-dir .
```

The two lines from Step 1 are gone. The compiled `sql-coder` prompt now lists each ability with your description followed by "(supplied by the project)".

## Verification

A cleaning build must leave your abilities alone:

```bash
python leafcutter-ai/scripts/build.py --target-dir . --clean
```

```bash
python -c "import pathlib; print(sorted(p.parent.name for p in pathlib.Path('.leafcutter/skills').glob('*/SKILL.md') if p.parent.name in ('postgres', 'sql-test')))"
```

Expected output: `['postgres', 'sql-test']`.

Once any package specialist marks an ability `provided_by: project`, the build never overwrites or removes your copy of it, including on `--clean`, and every specialist granting that ability uses your copy. The protection covers marked ids only. An unmarked ability you place under `.leafcutter/skills` is still exposed to [KI-BP-009](../known-issues/build-pipeline/open-high-ki-bp-009.md) while that issue is open.

## Overriding or falling back to a packaged ability

Marking an ability the package already ships (for example `signoff`) is a deliberate override. Each case prints one informational line, from real builds:

- Your copy exists: it is delivered to every specialist granting the ability, in place of the packaged one.

  ```text
  [abilities] agent 'probe-coder': ability 'signoff' is supplied by the project (<project>/.leafcutter/skills/signoff) and is used in place of the packaged one (<package>/templates/skills/signoff)
  ```

- Your copy is absent: the packaged copy is used.

  ```text
  [abilities] agent 'probe-coder': the project does not supply ability 'signoff' (looked in <project>/.leafcutter/skills/signoff); the packaged copy is used
  ```

  The build deploys that packaged copy into the empty slot with a `.packaged-fallback` marker. Edit the file and the project owns it from then on.

## Troubleshooting

1. **The build stops naming an unresolved ability.** The grant is not marked `provided_by: project` and the package does not ship the ability. Mark the grant, or ship the ability in the package.
2. **The "not found" line persists after Step 2.** The path is wrong. It must be exactly `.leafcutter/skills/<id>/SKILL.md`, with `<id>` equal to the grant's `skill_id`.

## See Also

- [How to create a skill](creating-a-skill.md) - authoring the skill itself.
- [Agent template frontmatter](../reference/agent-template-frontmatter.md) - the `skills:` grant fields.
- [KI-BP-009](../known-issues/build-pipeline/open-high-ki-bp-009.md) - the unmarked-placement hazard.
- [Documentation Index](../INDEX.md)
