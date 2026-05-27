# Why leafcutter puts all files in .leafcutter/

## The problem: mixed files

Before the consolidated output root, `build.py` scattered its artifacts across
the consumer project: `.claude/agents/`, `scripts/commit_guardian/`,
`.pre-commit-config.yaml`, `.gemini/`, `config/feedback_categories.yaml`, and
more. Leafcutter-owned files mixed with the project's own files. A developer
couldn't tell at a glance which files were "theirs" and which were generated.

## The solution: .leafcutter/

All `build.py` output artifacts now live under a single `.leafcutter/` directory.
Nothing touches the user's `scripts/`, `config/`, `docs/`, or any other folder.

```
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

## Two categories of output

### Shimmed outputs (external tools need fixed paths)

These files are written into `.leafcutter/` and then **symlinked back** to their
canonical locations because external tools hardcode those paths:

| Canonical path | Points to | Why |
|---|---|---|
| `.claude/agents/` | `.leafcutter/agents/` | Claude Code discovers agents here |
| `.claude/skills/` | `.leafcutter/skills/` | Claude Code discovers skills here |
| `.claude/commands/` | `.leafcutter/commands/` | Claude Code discovers commands here |
| `.claude/hooks/` | `.leafcutter/hooks/` | Claude Code discovers hooks here |
| `.claude/settings.json` | `.leafcutter/settings.json` | Claude Code reads settings here |
| `.gemini/` | `.leafcutter/gemini/` | Gemini reads instructions here |
| `.pre-commit-config.yaml` | `.leafcutter/pre-commit-config.yaml` | Pre-commit reads config at root |

### Non-shimmed outputs (only our code reads them)

These files live in `.leafcutter/` with **no symlink** back to the project root.
They are referenced via `{{config.output_root}}` placeholder injection at build
time, so hook entry paths resolve correctly:

- `.leafcutter/scripts/commit_guardian/` — hook implementations
- `.leafcutter/scripts/doc_compliance/` — doc checks
- `.leafcutter/scripts/feedback/` — feedback pipeline
- `.leafcutter/scripts/sync_platforms/` — platform sync
- `.leafcutter/config/` — internal configs
- `.leafcutter/rules/` — agent rules

Pre-commit hooks find their scripts because the generated `.pre-commit-config.yaml`
contains entries like:
```yaml
entry: python .leafcutter/scripts/commit_guardian/run_hook.py .leafcutter/scripts/commit_guardian/check_file_size.py
```

## User-curated files (not in .leafcutter/)

Files that `build.py` creates once but the user then edits stay at their
original locations. These are user-owned content, not build artifacts:

- `docs/vision.md`, `docs/glossary.md`, `docs/roadmap.json`
- `tickets/` folder structure
- `changelogs/`
- `.claude/skills_config.json` (user config)
- `.claude/precommit-autofix.json` (user config)

## Git posture

Configurable per consumer. Recommended: git-ignore `.leafcutter/` as a build
artifact.

```gitignore
# leafcutter build output — regenerate with: python leafcutter-ai/scripts/build.py
.leafcutter/
```

The shim symlinks (`.claude/agents/` etc.) should also be gitignored since
they're recreated on every build.

## Windows

Symlinks require Developer Mode or admin privileges. When unavailable, `build.py`
uses file copies as the shim strategy. Configure explicitly with
`"shim_strategy": "copy"` in `skills_config.json`.

## See also

- [ADR-004](../architecture/adrs/ADR-004-consolidated-output-root.md) — architectural decision record
- [How-to: Adopt the consolidated output root](../how-to/output-layout/adopt-consolidated-output-root.md) — migration guide
- [Reference: skills_config.json fields](../reference/skills-config-fields.md) — config field table
