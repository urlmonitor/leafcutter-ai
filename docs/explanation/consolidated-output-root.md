---
title: "The Consolidated Output Root"
type: explanation
status: active
created: 2026-05-27
last_updated: 2026-05-27
components:
  - build_pipeline
related_docs:
  - "docs/architecture/adrs/ADR-004-consolidated-output-root.md"
  - "docs/how-to/output-layout/adopt-consolidated-output-root.md"
  - "docs/reference/skills-config-fields.md"
---

# The Consolidated Output Root

## Why It Exists

Before leafcutter introduced a single output directory, `build.py` scattered its
artifacts across the consumer project: `.claude/agents/`, `scripts/commit_guardian/`,
`.pre-commit-config.yaml`, `.gemini/`, `config/feedback_categories.yaml`, and
elsewhere. Leafcutter-owned files mixed silently with the project's own files.

A developer running `git status` could not tell at a glance which files were theirs
and which were generated. Upgrades could silently leave stale files in old locations.
There was no single place to gitignore, audit, or wipe when something went wrong.

The consolidated output root — `.leafcutter/` — solves all of this by giving every
`build.py` artifact a single, predictable home.

---

## Background

- `build.py` is the leafcutter build script that generates agents, skills, hooks,
  scripts, and configuration from templates, then installs them into a consumer
  project.
- Prior to ADR-004, outputs landed in at least six separate directories at the
  consumer root.
- ADR-001 established the self-hosting boundary (source in `leafcutter-ai/`, outputs
  at consumer root) but left the scattered layout as an accepted negative consequence.
- ADR-004 resolved that by introducing `.leafcutter/` as the unified output root
  and a shim layer to satisfy tools that hardcode canonical paths.
- The `output_root` key in `skills_config.json` controls the directory name
  (default: `.leafcutter`).

---

## Discussion

### The layout inside `.leafcutter/`

All `build.py` artifacts now land under one directory:

```text
.leafcutter/
├── agents/                    Claude Code agent definitions
├── skills/                    Claude Code skill definitions
├── commands/                  Claude Code slash commands
├── hooks/                     Claude Code hook scripts
├── settings.json              Claude Code settings
├── gemini/                    Gemini/Antigravity instructions
├── pre-commit-config.yaml     Pre-commit hook configuration
├── scripts/
│   ├── commit_guardian/       Pre-commit hook implementations
│   ├── doc_compliance/        Doc compliance checks
│   ├── feedback/              Feedback pipeline scripts
│   └── sync_platforms/        Platform sync tooling
├── config/
│   └── feedback_categories.yaml
└── rules/                     Agent rules
```

### Two categories of output: shimmed and non-shimmed

Not all outputs can simply live in `.leafcutter/` and be done with it. Some
external tools hardcode the paths they read from. Others are read only by
leafcutter's own code. This distinction drives two different integration strategies.

#### Shimmed outputs

Tools such as Claude Code, pre-commit, and Gemini expect files at fixed canonical
paths. They cannot be reconfigured. The shim layer runs after the main build phases
and creates a pointer — either a symlink (preferred) or a file copy (Windows fallback)
— at each canonical path, pointing into `.leafcutter/`:

| Canonical path | Points to | Why the shim is needed |
|---|---|---|
| `.claude/agents/` | `.leafcutter/agents/` | Claude Code discovers agents at this path |
| `.claude/skills/` | `.leafcutter/skills/` | Claude Code discovers skills at this path |
| `.claude/commands/` | `.leafcutter/commands/` | Claude Code discovers commands at this path |
| `.claude/hooks/` | `.leafcutter/hooks/` | Claude Code discovers hooks at this path |
| `.claude/workflows/` | `.leafcutter/workflows/` | Claude Code Workflows JS scripts (build-epic.js, build-ticket.js, create-ticket.js) |
| `.claude/settings.json` | `.leafcutter/settings.json` | Claude Code reads settings at this path |
| `.gemini/` | `.leafcutter/gemini/` | Gemini reads instructions at this path |
| `.pre-commit-config.yaml` | `.leafcutter/pre-commit-config.yaml` | pre-commit reads config at the project root |

The shim strategy is configurable via the `shim_strategy` key in `skills_config.json`:
`"symlink"` (default), `"copy"`, or `"auto"` (attempts symlinks, falls back to copies
on `PermissionError`).

The `.claude/workflows/` shim is a special case: its `.leafcutter/workflows/` target is
itself a *build output*. The `build_workflow_scripts` phase compiles the workflow JS
scripts from their source directory `templates/workflows-js/` into `.leafcutter/workflows/`,
which the shim then exposes at the canonical `.claude/workflows/` path Claude Code reads.

| Source | Output (shimmed) | Description |
|---|---|---|
| `templates/workflows-js/` | `.claude/workflows/` | Compiled workflow JS scripts (build-epic.js, build-ticket.js, create-ticket.js) |

#### Non-shimmed outputs

Files that only leafcutter's own code reads require no shim. They live directly
in `.leafcutter/` and are referenced at build time via `{{config.output_root}}`
placeholder injection. No pointer at the project root is needed:

- `.leafcutter/scripts/commit_guardian/` — pre-commit hook implementations
- `.leafcutter/scripts/doc_compliance/` — documentation compliance checks
- `.leafcutter/scripts/feedback/` — feedback pipeline scripts
- `.leafcutter/scripts/sync_platforms/` — platform sync tooling
- `.leafcutter/config/` — internal configuration files
- `.leafcutter/rules/` — agent rule files

Pre-commit hooks find these scripts because `build.py` injects the resolved path
directly into the generated `.pre-commit-config.yaml` at build time:

```yaml
entry: python .leafcutter/scripts/commit_guardian/run_hook.py .leafcutter/scripts/commit_guardian/check_file_size.py
```

There is no magic path resolution at hook-run time. The path is literal and was
written correctly during the build.

### User-curated files stay at the project root

Not everything that `build.py` touches is a build artifact. Some files are
created once and then owned by the user — they are meant to be edited, committed,
and evolved. These stay at their original locations and are never moved into
`.leafcutter/`:

- `docs/vision.md`, `docs/glossary.md`, `docs/roadmap.json`
- `tickets/` folder structure
- `changelogs/`
- `.claude/skills_config.json` (user configuration)
- `.claude/precommit-autofix.json` (user configuration)

The rule of thumb: if a file is regenerated on every `build.py` run, it belongs
in `.leafcutter/`. If it is scaffolded once and then edited by the user, it stays
at the project root.

### Git posture

The recommended posture is to gitignore `.leafcutter/` — it is a build artifact
and can be regenerated at any time by running `build.py`. The shim symlinks
(`.claude/agents/`, etc.) should also be gitignored because they are recreated
on every build:

```gitignore
# leafcutter build output — regenerate with: python leafcutter-ai/scripts/build.py
.leafcutter/
.claude/agents
.claude/skills
.claude/commands
.claude/hooks
.claude/settings.json
.gemini/
.pre-commit-config.yaml
```

Consumers who prefer to commit the generated config (for example, to pin a
specific set of agents in CI) can do so. Both approaches are documented in the
how-to linked under See Also.

### Windows: symlinks and the copy fallback

On Linux and macOS, symlinks are created by default. On Windows, creating
symlinks requires either Developer Mode or administrator privileges. Without
these, symlink creation fails with `PermissionError`.

When `shim_strategy` is `"auto"` (the default), `build.py` detects the failure
and falls back to copying files instead of creating symlinks. Copies are
functionally equivalent; the only difference is that changes to `.leafcutter/`
files are not automatically reflected at the canonical path — a rebuild is
required.

To force the copy strategy explicitly:

```json
{
  "shim_strategy": "copy"
}
```

Set this in `.claude/skills_config.json`. See the reference doc linked under
See Also for the full field table.

### Auto-cleanup on upgrade

When `build.py` runs after an upgrade, it compares the set of files it would
write against the set of files it wrote on the previous run (recorded in a
manifest). Files at old locations that are no longer part of the current build
are removed. This prevents stale artifacts from accumulating at locations that
a previous version of leafcutter wrote to.

---

## Trade-offs

### Rejected: keep outputs at their canonical paths, no `.leafcutter/`

The simplest alternative was to continue writing files at their canonical paths
(`.claude/agents/`, `scripts/`, `config/`, etc.) and document which files are
generated. This was rejected because:

- `git status` noise remains: leafcutter files and user files are indistinguishable
  by location.
- There is no single gitignore entry that covers all leafcutter outputs.
- Upgrades that move a file from one location to another leave orphaned stale
  files with no automated cleanup trigger.

The `.leafcutter/` boundary makes the separation structural rather than
documentary.

### The shim layer adds complexity

The main cost of the consolidated root is the shim layer. Two categories of
output (shimmed and non-shimmed) must be maintained, and the shim strategy adds
a conditional code path (symlink vs. copy). The `"auto"` strategy mitigates
the Windows corner case but does not eliminate it.

ADR-004 accepted this complexity because the alternative — keeping outputs
scattered — compounds in proportion to the number of tools leafcutter integrates
with. The shim layer is bounded complexity; the scattered-output approach is
unbounded.

---

## See Also

- [ADR-004: Consolidated Output Root](../architecture/adrs/ADR-004-consolidated-output-root.md) — the architectural decision record; covers context, rejected alternatives, and consequences in full.
- [How-to: Adopt the consolidated output root](../how-to/output-layout/adopt-consolidated-output-root.md) — step-by-step migration guide for projects upgrading from the scattered layout.
- [Reference: skills_config.json fields](../reference/skills-config-fields.md) — full table of configuration keys including `output_root` and `shim_strategy`.

<!-- DECISION HISTORY
- 2026-05-27 [explanation-author]: Initial publication. Rewrote stub to follow canonical explanation convention (frontmatter, genre sections, trade-offs, See Also).
-->
