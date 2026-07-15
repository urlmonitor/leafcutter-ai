---
title: "How to upgrade from the frontend-coder + frontend-design split to the unified frontend-coder agent"
description: "Step-by-step guide for adopters migrating from the separate frontend-coder and frontend-design split to the unified frontend-coder agent — covers what build.py does automatically, verification steps, and rollback instructions."
type: how-to
status: active
created: 2026-06-18
last_updated: 2026-07-15
components:
  - build_pipeline
related_docs:
  - docs/architecture/adrs/ADR-005-frontend-coder-agent.md
  - docs/how-to/deprecating-or-removing-artifacts.md
  - docs/how-to/working-with-leafcutter.md
---

# How to upgrade from the frontend-coder + frontend-design split to the unified frontend-coder agent

This guide is for adopters who installed leafcutter-ai when the `frontend-design`
skill was a separate, optionally-loadable artifact alongside the `frontend-coder`
agent. As of the version that includes this guide, design principles are embedded
directly in `frontend-coder.md`. The separate `frontend-design` skill is deprecated
and no longer needed.

**If you re-run `build.py` with the new version, the migration happens automatically.
No manual steps are required.**

---

## What changed

The old arrangement had two separate artifacts:

| Artifact | Path after build | Role |
|----------|-----------------|------|
| `frontend-coder` agent | `.claude/agents/frontend-coder.md` | Orchestrated UI implementation |
| `frontend-design` skill | `.claude/skills/frontend-design/SKILL.md` | Provided design principles at runtime |

The `frontend-coder` agent detected whether the `frontend-design` skill directory
existed and, if so, loaded it before producing any UI output. This meant design
principles were applied only when the skill was explicitly installed via `/onboard`.

**After the upgrade:**

- `frontend-coder.md` contains the design principles directly. The agent always
  applies design principles; there is no "not installed" state for design.
- The `frontend-design` skill directory is no longer produced by `build.py`. The
  template is retained in `templates/skills/frontend-design/` with `deprecated: true`,
  so `build_skills()` skips it at deploy time and never writes it to
  `.claude/skills/frontend-design/` on a fresh build. (Separately, because
  `_build_source_manifests()` still lists the directory as managed,
  `clean_stale_artifacts()` does not prune it on a `--clean` run either.) If the
  directory exists from a previous installation it must be removed manually.
- `skills_config.json` no longer needs (or accepts) `"frontend-design"` under
  `frontend.optional_skills`. The migration removes it automatically.

See [ADR-005](../architecture/adrs/ADR-005-frontend-coder-agent.md) for the full
architectural rationale.

---

## What `build.py` does automatically

When you run `build.py` with the new version, it performs two automatic actions
before anything else:

### 1 — Config migration (`skills_config.json`)

`build.py` reads your `skills_config.json` (found under `.claude/`, `.gemini/`,
`.cursor/`, `.github/`, or `.cline/` — whichever exists) and removes
`"frontend-design"` from `frontend.optional_skills` if it is present.

Example: if your config previously contained:

```json
{
  "frontend": {
    "optional_skills": ["webapp-testing", "frontend-design"]
  }
}
```

After migration it becomes:

```json
{
  "frontend": {
    "optional_skills": ["webapp-testing"]
  }
}
```

The file is written in-place. If `"frontend-design"` was not listed, the file is
not touched. The migration is idempotent — running `build.py` multiple times
produces the same result.

### 2 — Agent template update (`.claude/agents/frontend-coder.md`)

`build.py` deploys the new unified `frontend-coder.md` template, which contains
embedded design principles. The old version, which called out to the
`frontend-design` skill, is replaced.

### What `build.py` does NOT do automatically

`build.py` does **not** delete the `.claude/skills/frontend-design/` directory
during a standard run or a `--clean` run. The template is retained in
`templates/skills/frontend-design/` with `deprecated: true`, so
`_build_source_manifests()` treats it as still-managed and
`clean_stale_artifacts()` never prunes it. If the directory already exists on
disk from a previous installation, remove it manually:

```bash
rm -rf .claude/skills/frontend-design/
```

---

## Verifying the migration succeeded

After running `build.py`, check three things:

**1. The frontend-design skill directory is absent (or stale-removed):**

```bash
ls .claude/skills/frontend-design/
```

Expected result: `No such file or directory`. If the directory still exists, it
is a leftover from the previous build and can be safely deleted manually:
`rm -rf .claude/skills/frontend-design/`. Note that `build.py --clean` does NOT
remove this directory — `clean_stale_artifacts()` treats deprecated-but-still-managed
templates as in-scope and skips them.

**2. `skills_config.json` no longer lists `"frontend-design"`:**

```bash
grep frontend-design .claude/skills_config.json
```

Expected result: no output. If the grep returns a line, the config migration did
not run — re-run `build.py` and check for errors in the migration output.

**3. The new `frontend-coder.md` embeds design principles:**

```bash
grep -c "design" .claude/agents/frontend-coder.md
```

Expected result: a non-zero count. The embedded principles section is present in
the new template. If the count is zero, the template was not updated — re-run
`build.py`.

### Full verification in one pass

Run `build.py --clean` to simultaneously update the agent template and migrate the
config. Note that `--clean` does **not** remove the `frontend-design` directory —
the template carries `deprecated: true` so `_build_source_manifests()` treats it as
still-managed at deploy time and `clean_stale_artifacts()` skips it. Remove the
directory manually if it exists (see step 1 above).

```bash
python leafcutter-ai/scripts/build.py --target-dir . --clean
```

After a successful run, the output includes a "Config migration" heading confirming
the `frontend-design` entry was removed from `skills_config.json`.

---

## Rollback instructions

If you need to revert to the previous split temporarily (for example, to unblock
a pending PR that depends on the old `frontend-design` skill path), follow these
steps.

> **Important:** Rolling back requires checking out the old version of
> `scripts/build.py` and the old `frontend-coder.md` template from git. Do not
> edit these files by hand.

### Step 1 — Check out the old build.py and templates

Identify the git commit before the upgrade landed on your branch (use
`git log --oneline` to find it), then restore:

```bash
git checkout <old-commit> -- scripts/build.py templates/agents/frontend-coder.md templates/skills/frontend-design/
```

### Step 2 — Re-run build.py to restore the old artifacts

```bash
python scripts/build.py --target-dir .
```

This deploys the old `frontend-coder.md` (which loads the skill at runtime) and
the `frontend-design` skill directory.

### Step 3 — Restore `skills_config.json`

Add `"frontend-design"` back to `frontend.optional_skills`:

```json
{
  "frontend": {
    "optional_skills": ["frontend-design"]
  }
}
```

### Step 4 — Re-run build.py once more to confirm

```bash
python scripts/build.py --target-dir .
```

Confirm that `.claude/skills/frontend-design/SKILL.md` exists and that the agent
template at `.claude/agents/frontend-coder.md` does not contain the embedded
design principles block.

---

## Frequently asked questions

**Do I need to update any ticket frontmatter?**

No. Tickets that previously listed `frontend-coder: needed` continue to work
unchanged. The agent name has not changed; only the template body changed.

**Will the `frontend-coder` agent behave differently after the upgrade?**

Design principles are now always applied — there is no longer a conditional check
for whether the skill is installed. For most adopters this means no visible
difference: if you had the skill installed, the output was already design-principle-
aware. If you did not have the skill installed, your output will now include design
principles by default.

**Can I still use `webapp-testing` as an optional skill?**

Yes. The `webapp-testing` skill is unaffected by this migration. It continues to
be detected and loaded at runtime if `.claude/skills/webapp-testing/SKILL.md`
exists.

**The `/onboard` wizard offered me `frontend-design` previously. Will it offer it again?**

No. The wizard no longer offers `frontend-design` as an installable skill. When you
opt into frontend capabilities during `/onboard`, the agent template is deployed
with design principles already embedded. No separate skill selection is presented.
